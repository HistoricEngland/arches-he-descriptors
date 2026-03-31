# Display Descriptor Implementation Guide (Developers)

This document explains what the code currently does at runtime, from API request through data extraction and descriptor rendering.

## TL;DR

The display descriptor system resolves configurations via a three-tier precedence chain:

**Configuration resolution precedence:**

1. **API override** - Request body includes `config` parameter (highest priority)
2. **Graph lookup** - Query `DisplayDescriptorGraphConfig.objects.filter(graph_id=...)` 
3. **No-op** - No config found; return `None` (lowest priority)

**Resource data resolution:**

- Either from supplied JSON (`preview` endpoint)
- Or dynamically built from Arches tables (`resource_instances`, `nodes`, `tiles`, `values`)

**Rendering pipeline:**

1. Resolve config via precedence chain
2. Validate config operations and field topology
3. Resolve field values (from JSON or DB)
4. Apply rule blocks in order; first successful block wins
5. Return descriptor (optionally with SQL trace metadata in DEBUG)

---

## Code Map

- `display_descriptor/views.py`
  - API request handling
  - Config resolution with precedence chain
  - Response shaping (`descriptor_only`, SQL tracing)
- `display_descriptor/service.py`
  - Config loading/parsing (YAML strings, JSON, or database via `DisplayDescriptorGraphConfig`)
  - Precedence resolution for config sources
  - Dynamic DB extraction for resource fields
  - Validation (missing fields, subfield/parent nodegroup mismatch)
- `display_descriptor/engine.py`
  - Rule execution engine
  - Field filter logic
  - Operation chain logic
- `display_descriptor/schema.py`
  - Dataclasses representing config schema
- `models.py` (project root)
  - `DisplayDescriptorGraphConfig` model (stores graph→config mappings)

---

## Config Resolution Chain

The `_resolve_config()` method in `service.py` implements the precedence chain:

```python
def _resolve_config(self, resource_id: str, config_data: Optional[Dict] = None):
    # Step 1: Check for API override
    if config_data is not None:
        return self._parse_config_data(config_data)  # Highest priority
    
    # Step 2: Look up from database
    graph_id = self._get_resource_graph_id(resource_id)
    return self._load_graph_config(graph_id)  # Queries DisplayDescriptorGraphConfig
    
    # Step 3: No config found (implicit)
    # Returns None, triggering no-op behavior
```

**Call stack:**

1. API endpoint receives request with optional `config` parameter
2. `POST /api/display-descriptor/<resource_id>/` (if routed) calls `service.get_resource_data(..., config_data=config, return_config=True)`
3. Service calls `_resolve_config(resource_id, config_data)`
4. Returns resolved config or None

**Database lookup details** (`_load_graph_config`):

```python
def _load_graph_config(self, graph_id):
    row = DisplayDescriptorGraphConfig.objects.filter(graph_id=graph_id).first()
    if not row:
        return None  # No config stored for this graph
    
    yaml_config = row.yaml_config
    return self.load_config_from_yaml(yaml_config)  # Parse YAML
```

The database lookup queries the `DisplayDescriptorGraphConfig` table using the resource's graph_id as the foreign key. This table is managed via Django admin and allows non-code config updates.

---

## API Runtime Behavior

Route registration note:

- This project's `urls.py` registers `GET /api/display-descriptor/config/<graph_id>/` and `POST /api/display-descriptor/admin-test/`.
- `get_display_descriptor` and `preview_display_descriptor` exist in `display_descriptor/views.py` but are not mapped in this project's URL patterns by default.
- The sections below describe their runtime behavior if your project wires those endpoints.

### 1) `GET /api/display-descriptor/<resource_id>/`

Flow:

1. Calls `render_display_descriptor_for_resource(resource_id)`
2. Service resolves config (API override not used in GET) and resolves resource data from DB
3. Engine evaluates rule blocks and returns first successful descriptor

Response (default):

```json
{
  "resource_id": "...",
  "display_descriptor": "..."
}
```

Query params:

- `strict_sortorder=true` enforces sortorder consistency checks during DB extraction.

### 2) `POST /api/display-descriptor/<resource_id>/`

Body:

```json
{
  "config": {
    "fields": [...],
    "display_descriptor_rules": [...]
  }
}
```

Flow:

1. If `config` present, service parses that config (no file-cache dependency for schema)
2. Service builds resource data for `<resource_id>` and returns both payload + resolved config (`return_config=True`)
3. Rendering path:
  - with inline `config`: `render_with_config(resource_data, config)`
  - without inline config but with DB config: `render_with_parsed_config(resource_data, resolved_config)`
  - without any resolved config: no-op (`display_descriptor: null`)

Response defaults to descriptor-only, unless `descriptor_only=false`.

Query params:

- `strict_sortorder=true` enforces sortorder consistency checks during DB extraction.

### 3) `POST /api/display-descriptor/preview/`

Body:

```json
{
  "resource": {...},
  "config": {...}
}
```

This mode does **not** pull from DB; it renders directly from provided resource JSON.

`strict_sortorder` is accepted for API consistency but has no effect in preview mode.

### 4) `POST /api/display-descriptor/admin-test/`

**Admin-only endpoint for testing configurations before saving.**

Body:

```json
{
  "resource_id": "<uuid>",
  "graph_id": "<uuid>",
  "yaml_config": "fields:\n  - name: ...\n..."
}
```

Flow:

1. Validates `resource_id` and `graph_id` are provided
2. If `yaml_config` provided in body, uses it directly (for testing unsaved edits)
3. Otherwise looks up stored config from `DisplayDescriptorGraphConfig` table
4. Parses YAML config
5. Calls `service.render_for_resource(resource_id=..., config_data=...)`
6. Returns descriptor or error

Response:

```json
{
  "display_descriptor": "Rendered descriptor or null",
  "error": null
}
```

Error response:

```json
{
  "display_descriptor": null,
  "error": "Error description (e.g., 'Invalid YAML', 'Resource not found')"
}
```

**Usage context:**

This endpoint is called by the Django admin change form when a user:

1. Types/edits YAML in the config textarea
2. Enters a resource UUID in the test panel
3. Clicks the "Check" button

The admin template calls this endpoint via JavaScript fetch, allowing users to validate configurations without saving to the database first. All errors are surfaced to the user in the admin UI.

---

## SQL Trace Mode (`include_sql`)

Query param: `include_sql=true`

When enabled:

- SQL is captured via Django `connection.execute_wrapper`
- Each query includes `sql`, `params`, `many`, `duration_ms`
- Response includes:
  - `execution_time_ms` (total endpoint time)
  - `sql_query_count`
  - `sql_queries`

Security/operational guard:

- `include_sql` is only allowed when `DEBUG=True`
- Otherwise request returns `400`

---

## Config Parsing and Validation

`DisplayDescriptorService._parse_config_data` transforms raw YAML/JSON into dataclasses:

- `DisplayDescriptorConfig`
- `FieldDefinition`
- `DisplayDescriptorRuleBlock`
- `RuleDefinition`
- `Operation`

`display_descriptor_rules` blocks may omit `rule`; omitted `rule` is normalized to an empty list (`[]`), enabling unconditional fallback blocks such as `{"format": "Unknown"}`.
Each rule block may also include `format_operations` (same operation schema as rule operations) to post-process the final rendered descriptor string.

### Operation validation

- Each operation type is validated against `OperationType` enum
- Unknown operations raise `ValueError`
- Includes trim variants (`trim`, `ltrim`, `rtrim`) and padding variants (`lpad`, `rpad`)
- `lpad`/`rpad` support `pad_length` (required for effect) and optional `pad_char` (defaults to space)
- Includes `normalize_whitespace` (collapse whitespace), `replace` (`replace_from`/`replace_to` with optional `ignore_case`, default `false`) and `coalesce` (`coalesce_value`) for fallback cleanup behavior
- `fallback_text` is an alias of `coalesce` and can use either `fallback_text` or `coalesce_value` as the fallback parameter

### Field filter normalization

- `field_filters` values are normalized to lists
- Example: `"Primary|Statutory|Original"` becomes `["Primary|Statutory|Original"]`

---

## DB-backed Resource Data Extraction

Primary entrypoint: `DisplayDescriptorService.get_resource_data(...)`

### Step 1: Resolve graph for resource

- Query `resource_instances` by `resourceinstanceid`
- Read `graph_id`
- If not found: `ValueError("Resource instance not found...")`

### Step 2: Resolve configured field nodes

- Collect field names + subfield names from config
- Query `nodes` for matching names within `graph_id`
- Build `node_map`

Validation at this stage:

1. **All configured field names must exist** in `nodes`
2. **Each subfield must share parent nodegroup**

If either fails: `ValueError` is raised and processing stops.

### Step 3: Group by nodegroup and query tiles

- Fields are grouped by `nodegroup_id`
- For each group, query `tiles` by:
  - `resourceinstance_id`
  - `nodegroup_id`
- Order: `sortorder`, then `tileid`

### Step 4: Extract node values from `tiledata`

Datatype-specific extraction:

- `string`: expects i18n object (`{ "en": {"value": ...} }`), with fallback to first localized value
- `concept`: returns UUID string placeholder initially
- other types: raw value passthrough

Subfield structure handling:

- If field has subfields, each row becomes an object:

```json
{
  "value": "<parent_value>",
  "<Subfield Name>": "<subfield_value>"
}
```

### Step 5: Concept label resolution

- Collect all concept UUIDs found during extraction
- Query `values` once using `valueid__in`
- Replace UUID placeholders with `values.value` labels

### Step 6: Shape result for engine

- Scalar lists with one item are collapsed to scalar
- Fields missing in DB output are defaulted:
  - `None` for simple fields
  - `[]` for fields with subfields

Output is a dictionary keyed by config field names, suitable for the engine.

---

## Rule Engine Behavior

Engine entrypoint: `DisplayDescriptorEngine.render(resource)`

### Rule block execution model

- Iterate `display_descriptor_rules` in order
- For each block, execute each `rule` item
- If required value missing and no default, block fails
- First block that formats successfully wins

### Field filtering behavior

`select_field_value` supports list-of-dict fields with `field_filters`.

Priority filters:

- If filter value contains pipe (`"A|B|C"`), it behaves as ordered priority
- Returns first matching candidate

Simple filters:

- Equality match against allowed values list

Subfield format-context caveat:

- Subfield placeholders are only added to format context when the rule resolves to a single dict candidate.
- If filtering resolves to multiple matches, the engine returns a list of parent values and does not merge subfield keys into the format context.
- In practice, use priority filters that reduce to one value (for example, ordered options ending with FIRST) when a format string references subfields.

### Operation chains

- Operations execute sequentially
- Some operations are string-or-list, some list-only (`unique`, `sort`, `reverse`)
- `combine` converts list to string, affecting downstream operations

---

## Error Handling Semantics

Service raises `ValueError` for predictable user/config/data issues:

- Invalid config operation
- Missing fields in graph
- Subfield nodegroup mismatch
- Missing resource instance
- Sortorder consistency issue when `strict_sortorder=True`

API layer maps these to HTTP `400` responses.

Unexpected runtime errors are returned as HTTP `500`.

---

## Config Caching Behavior

Service maintains an internal `_config_cache` for parsed config objects:

- Set when configs are loaded via `load_config_from_yaml()`, `load_config_from_dict()`, or `load_config_from_json()`
- Used to avoid re-parsing identical configs on subsequent requests
- Cache is per-service-instance; no global/cross-request caching

No file-based caching exists; all configs come from:
  1. Request bodies (API override)
  2. Database lookups (`DisplayDescriptorGraphConfig`)

---

## Extensibility Notes

Common extension points:

1. Add operation type:
   - Add enum member in `OperationType`
   - Implement operation function
   - Register handler in `OPERATION_HANDLERS`

2. Add datatype extraction strategy:
   - Extend `_extract_value` in `DisplayDescriptorService`

3. Add stronger ordering policy:
   - Use `strict_sortorder=True`
   - Extend sort validation rules if needed

4. Add additional API-level diagnostics:
   - Extend `_add_sql_metadata` in `views.py`

---

## Practical Adoption Guidance

For teams integrating this feature:

1. Start with `preview` endpoint and static resource payloads.
2. Validate rule behavior and operation ordering.
3. Move to DB-backed endpoint with real `resource_id`.
4. Enable `include_sql=true` in DEBUG to verify query behavior.
5. Lock down production behavior (DEBUG false, no SQL diagnostics).

This approach minimizes risk and makes failures easier to interpret while adopting the system.
