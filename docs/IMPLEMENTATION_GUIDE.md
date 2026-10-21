# Display descriptor implementation guide

[Back to README](../README.md) |
[Configuration reference](./USER_GUIDE.md)

This guide describes the current source implementation, API and test setup.
Installation belongs in the [README](../README.md#integrating-into-an-existing-arches-project);
YAML syntax and authoring examples belong in the
[configuration guide](./USER_GUIDE.md#configuration-reference).

## Code map

| Source | Responsibility |
| --- | --- |
| [views.py](../arches_he_descriptors/display_descriptor/views.py) | HTTP handling, response shaping and SQL diagnostics |
| [service.py](../arches_he_descriptors/display_descriptor/service.py) | Parsing, graph config lookup and database extraction |
| [engine.py](../arches_he_descriptors/display_descriptor/engine.py) | Rule execution, filtering and operation dispatch |
| [schema.py](../arches_he_descriptors/display_descriptor/schema.py) | Configuration dataclasses |
| [yaml_transform.py](../arches_he_descriptors/display_descriptor/yaml_transform.py) | Graph-aware field normalisation and descriptor-section storage |
| [models.py](../arches_he_descriptors/models.py) | One configuration record per graph UUID |
| [admin.py](../arches_he_descriptors/admin.py) | Section editors and configuration validation |
| [arches_he_descriptors.py](../arches_he_descriptors/functions/arches_he_descriptors.py) | Arches primary descriptor function |
| [urls.py](../arches_he_descriptors/urls.py) | Registered routes and Arches core URL inclusion |

`graph_id` on `DisplayDescriptorGraphConfig` is a unique UUID field, not a Django
foreign key to `GraphModel`. The admin resolves graph names and limits its choices
to resource graphs with an ontology.

## Service and extraction

### Configuration resolution

For `DisplayDescriptorService.render_for_resource(...)`:

1. An explicit `config_data` dictionary takes precedence, including an empty
   dictionary. It is parsed as a single descriptor configuration.
2. Otherwise, the service looks up the resource's graph UUID, then that graph's
   `DisplayDescriptorGraphConfig`.
3. The requested `descriptor_type` selects a stored section. Current JSON-section
   storage defaults to `display_name` when no type is supplied.
4. A missing/blank configuration or absent section returns `None`.

There is no `_resolve_config()` method or default configuration file. Lookup is
implemented in `get_resource_data()` and `_load_graph_config()`. See
[descriptor sections](./USER_GUIDE.md#descriptor-sections) for legacy-format
behaviour.

An in-memory payload has no graph context. Use
`render_with_config(resource, config_data)` or
`render_with_parsed_config(resource, config)` to render it.
`render(resource)` and the convenience helper `render_display_descriptor(resource)`
always return `None`; previously loading a config does not change that behaviour.
See the [working Python example](./USER_GUIDE.md#rendering-in-python).

### Database extraction

`get_resource_data()` builds the engine's input dictionary:

1. Read `ResourceInstance.graph_id`; a missing resource raises `ValueError`.
2. Resolve configured parent nodes by graph name or explicit `nodeid`, checking
   that an explicit ID still has the configured name. Missing or ambiguous nodes
   raise `ValueError`.
3. Resolve subfields by name and verify each shares its parent's nodegroup.
   Subfield `nodeid` disambiguation is not implemented in the runtime schema.
4. Query `TileModel` per configured nodegroup, ordered by `sortorder`, then
   `tileid`. With `strict_sortorder=True`, **any** null sortorder raises
   `ValueError`, not just mixed null/non-null ordering.
5. Extract values according to datatype and resolve concept labels in one
   `Value` query for valid value UUIDs.
6. Collapse a one-item scalar list, except for a `concept-list` parent. Default
   missing simple fields to `None` and missing fields with subfields to `[]`.

Fields with subfields produce rows shaped like:

```json
{
  "value": "old church",
  "Monument Name Use Type": "Primary"
}
```

Extraction details:

- **string:** use the requested language's `value`, then the first available
  localised `value`; plain strings are also accepted.
- **concept / concept-list:** values reference Arches concept **value UUIDs**.
  Unresolved simple concept values are omitted from simple-field output;
  unresolved values in subfield rows and concept lists can remain as UUID text.
  Concept lists are normalised and deduplicated, not guaranteed to preserve
  source cardinality.
- **resource-instance / resource-instance-list:** extract related resource IDs,
  deduplicate them, and read their **stored** name descriptors. No recursive
  descriptor rendering occurs. Lookup tries the requested language, English,
  then an unlocalised name; absent/blank descriptors fall back to the resource ID.
  A per-extraction dictionary avoids repeated descriptor lookups.
- **other datatypes:** raw value passthrough.

### Parsing and rule execution

The parser builds the dataclasses in [schema.py](../arches_he_descriptors/display_descriptor/schema.py).
Operation names are validated against `OperationType`; unknown names raise
`ValueError`. Scalar filter specifications are normalised to one-item lists.
This is not comprehensive schema validation: malformed shapes or unsupported
operation options can still raise other exceptions.

The engine evaluates blocks in order and returns the first result that is not
`None`, including an empty string. A missing required value can fail a block;
`required` is not implicitly true. A missing block-format placeholder fails the
block and allows the next block to run. Operations execute in order, with
`format_operations` applied after block interpolation.

See the configuration guide for the authoritative descriptions of
[rules](./USER_GUIDE.md#rules-and-defaults),
[filters and subfield context](./USER_GUIDE.md#filters-and-subfield-context) and
[operations](./USER_GUIDE.md#operations).

### Parsed-config state

`_config_cache` holds the last config assigned by resource extraction or an
explicit render. It is not a keyed cache and does not avoid repeated parsing.
The `load_config_from_yaml/dict/json` methods return parsed configs without
setting it. `clear_cache()` resets it.

The convenience helpers use a lazily created **global service instance**.
HTTP POST/preview/admin-test paths create their own service instances.
There is no file cache or automatic cross-request parsed-config memoisation.

## Arches function behaviour

The function maps:

| Arches descriptor | Stored section |
| --- | --- |
| `name` | `display_name` |
| `description` | `display_description` |
| `map_popup` | `map_popup` |

It defaults to English, or uses `context["language"]` when provided.
An explicitly false `show_prn` in the descriptor's function config returns the
stored descriptor instead of rendering. The default name config sets this to
`False`; description and map popup do not have it in their default configs.
The Display Name **Enabled** switch controls this legacy-named flag.

Otherwise the function calls the DB-backed service with the mapped section.
Missing configuration, blank output or rendering errors produce the translated
`Undefined` string. Expected `ValueError`s are logged as warnings; unexpected
errors are logged with a traceback. This differs from the service's `None`
no-op result and the API's JSON `null`.

## API reference

All five routes below are registered in
[urls.py](../arches_he_descriptors/urls.py). They require a trailing slash;
graph and resource route parameters use Django's UUID converter.

### Resource rendering

`GET|POST /api/display-descriptor/<resource_id>/`

GET renders from stored graph configuration and returns:

```json
{"resource_id": "<uuid>", "display_descriptor": "Rendered descriptor or null"}
```

POST accepts `{"config": {...}}`, or an empty body to use stored config. It
extracts data for the resource even when an inline config is supplied. Its
default response is:

```json
{"display_descriptor": "Rendered descriptor or null"}
```

With `descriptor_only=false`, POST also includes `resource_id` and `input`.
Rendering does not persist the result to the resource.

Query parameters:

- `descriptor_type=display_name|display_description|map_popup`: select the stored
  section; an inline config remains a single-section override.
- `strict_sortorder=true`: require non-null sortorder on every queried tile.
- `include_yaml=true`: include `yaml_config` and `yaml_config_source`
  (`graph` or `request`). Inline dictionaries are serialised to YAML; without a
  requested section, graph echo returns the full stored text, which can be JSON.
  A missing config is echoed as `null`.
- `include_sql=true`: see [SQL diagnostics](#sql-diagnostics).

These HTTP views use the service's default English language; they do not expose a
language query parameter.

### In-memory preview

`POST /api/display-descriptor/preview/`

```json
{"resource": {"Field": "value"}, "config": {"fields": ["Field"], "display_descriptor_rules": [{"rule": [{"name": "Field"}], "format": "{Field}"}]}}
```

Returns `{"display_descriptor": "value"}`. Without `config`, the result is
`null`: preview does not look up graph config. `descriptor_only=false` adds
`input`. `include_sql=true` is supported; `strict_sortorder=true` is accepted but
has no effect because preview does not query tiles. There is no YAML echo option.

### Fetch stored configuration

`GET /api/display-descriptor/config/<graph_id>/`

Optional `descriptor_type` selects one section; without it, the full stored text
is returned. Response keys are `graph_id`, `descriptor_type`, `configured` and
`yaml_config`. An absent/blank config returns `configured: false` and
`yaml_config: null`, not a 404.

### Save one section

`PATCH /api/display-descriptor/config/<graph_id>/section/`

```json
{"descriptor_type": "display_name", "yaml_config": "fields:\n  - name: Field\n..."}
```

Both values are required and the YAML must be non-empty. The view normalises
fields against the graph, validates YAML parsing, and creates/updates the config,
preserving other sections. Legacy storage is migrated to JSON-section storage.
It returns `graph_id`, `descriptor_type` and `saved: true`. This is not a
full rendering validation or a resource descriptor regeneration operation.

### Admin test

`POST /api/display-descriptor/admin-test/`

```json
{
  "resource_id": "<uuid>",
  "graph_id": "<uuid>",
  "yaml_config": "fields:\n  - name: Field\n...",
  "descriptor_only": true,
  "include_sql": false
}
```

Both IDs are required. The admin UI sends the active tab's YAML as a single
configuration; the endpoint does not accept a descriptor-type selector.
If YAML is absent/empty, it fetches the **full stored text** for `graph_id`.
That fallback does not extract a section from current JSON-section storage;
send section YAML explicitly for reliable tests.

Success returns `{"display_descriptor": "...", "error": null}`.
`descriptor_only=false` adds `input`. The endpoint does not save anything.
It renders the supplied resource but does not check that it belongs to the
supplied `graph_id`; use a resource from the selected graph.

### SQL diagnostics

Resource rendering and preview use the `include_sql=true` query parameter;
admin-test uses the `include_sql` body property.
Diagnostics are allowed only with `DEBUG=True` and otherwise raise `ValueError`.
Successful diagnostic responses add `execution_time_ms`, `sql_query_count` and
`sql_queries`; each captured query includes `sql`, `params` (a repr string or
`null`), `many` and `duration_ms`.

Capture uses Django `connection.execute_wrapper`. Only calls inside capture
wrappers are included; for example YAML-echo lookups are outside them.
Endpoint timing is therefore not just the sum of captured SQL durations.

### Errors and deployment caveats

Unsupported methods return 405 and invalid JSON returns 400.
Resource rendering maps `ValueError` to 400 and unexpected exceptions to 500.
Preview maps inline rendering `ValueError` to 400, but other exceptions to 500.
Config fetch/save have explicit 400 validation responses, but no general
exception-to-JSON wrapper.

Admin-test has a different contract: missing IDs and invalid JSON return 400,
but YAML/config/rendering errors handled as `ValueError` generally return
**200 with an `error` field**. Unexpected errors return 500. A rejected SQL toggle
on admin-test also follows its 200/error path. Clients must inspect `error`, not
just HTTP status.

#### Deployment caveats

These views do not themselves enforce login, staff status or object-level
permissions. The name "admin-test" describes its caller, not an admin-only
permission check. POST/PATCH views are CSRF-exempt. Host middleware and deployment
controls must restrict access appropriately, especially section writes and SQL
diagnostics. `DEBUG=False` disables SQL tracing, not access to the API.
This is a statement of current behaviour, not a security audit.

## Running tests

### App suite

Run inside the application container:

```bash
docker exec archeshedescriptors sh -lc 'cd /web_root/arches_he_descriptors && python manage.py test --noinput --verbosity=2 --settings=arches_he_descriptors.tests.settings arches_he_descriptors.tests.test_display_descriptor_operations arches_he_descriptors.tests.test_display_descriptor_engine arches_he_descriptors.tests.test_display_descriptor_service arches_he_descriptors.tests.test_display_descriptor_graph'
```

[App test settings](../arches_he_descriptors/tests/settings.py) expect a sibling
Arches checkout (`../arches`, mounted at `/web_root/arches`) for core
`tests.base_test` helpers. Operation and engine tests do not require a database;
graph regressions require PostgreSQL/PostGIS.

For only operations, use the same command with just
`arches_he_descriptors.tests.test_display_descriptor_operations`.

### Project function suite

```bash
docker exec archeshedescriptors sh -lc 'cd /web_root/arches_he_descriptors && python manage.py test --noinput --verbosity=2 --settings=tests.test_settings_for_docker tests.function_tests'
```

This suite uses the project's own `tests` package. Do not combine it with the app
suite under one settings module: the package can collide with core Arches
`tests`. Run suites **sequentially**, since their DB-backed tests use the same
default test database name.

PostgreSQL/PostGIS and Elasticsearch must be available for the Monument runner,
which creates/deletes test search indices. The non-Docker
[test settings](../tests/test_settings.py) explicitly use Elasticsearch on
`localhost`, rather than the separate container.

Fixture preparation alone can run without Django or a database:

```bash
python -m unittest tests.function_tests.test_graph_fixture
```

### Test inventory and boundaries

The current source contains 64 test methods (not counting `subTest` cases):

| Module | Methods |
| --- | ---: |
| [Operations](../arches_he_descriptors/tests/test_display_descriptor_operations.py) | 13 |
| [Engine](../arches_he_descriptors/tests/test_display_descriptor_engine.py) | 13 |
| [Service](../arches_he_descriptors/tests/test_display_descriptor_service.py) | 6 |
| [Graph regressions](../arches_he_descriptors/tests/test_display_descriptor_graph.py) | 3 |
| [Graph fixture preparation](../tests/function_tests/test_graph_fixture.py) | 7 |
| [Monument graph setup](../tests/function_tests/test_monument_graph_setup.py) | 3 |
| [Monument resource/function integration](../tests/function_tests/test_monument_resource_setup.py) | 19 |
| **Total** | **64** |

This is an inventory, not a measured coverage percentage. Operation tests check
every `OperationType` against examples and dispatch handlers, plus option,
missing-value and length boundaries. Engine tests cover defaults, subfield
agreement/ambiguity, priority fallback and combined filters.

Graph tests are designed to import the core Resource Test Model, assign the HE
function, create tiles and verify stored descriptors. Monument tests exercise name persistence via
`Resource.save_descriptors`, ordered rule fallbacks, subfield aliases and
transformations. Description priority `Summary|Full|FIRST` is tested through the
service with inline config, not the function's description path.

There are no dedicated HTTP endpoint tests for routing, status codes or response
contracts. The excluded spatial functions and Generate Unique References are not
tested by the Monument suite.

#### Known stored-config mismatch

The graph regression and Monument resource test setups currently store a flat
configuration with `json.dumps(config)`. The current section detector treats
that JSON object as section storage, discards its non-string values and finds
no `display_name` section. Consequently those stored-config paths cannot render
the intended descriptor with the current loader.

Use flat **YAML** for legacy display-name configuration, or a JSON mapping from
`display_name` to a **YAML string**, as described in
[descriptor sections](./USER_GUIDE.md#descriptor-sections).
The test inventory above is not evidence that these integration tests currently
pass. Fixing the test setup or adding loader compatibility is a separate code
change; this documentation consolidation does not alter runtime behaviour.

### Offline Monument fixtures

The [shared setup](../tests/function_tests/base_test.py) loads CIDOC CRM, an offline
concept fixture and the photo widget, registers the HE function, and imports and
publishes a descriptor-only copy of the Arches 6.2 Monument export for Arches 7.6.

[Graph preparation](../tests/function_tests/graph_fixture.py) converts graph/card
text and widget labels to language-keyed objects, preserving translations and
nulls; node names remain strings. It excludes three source-specific
non-descriptor functions and the unsupported `bngcentrepoint` nodegroup, card,
widget and incident edges. It replaces the source report template/config with
the default report template and empty config, and replaces the primary
descriptor assignment with HE Descriptors. Remaining descriptor nodegroups,
templates and triggering nodegroups are preserved; name rendering is enabled.
The source JSON is not modified.

The [resource loader](../tests/function_tests/resource_fixture.py) reads the saved
[St Bernard's API response](../tests/fixtures/pkg/business_data/st_bernards_monument.bulk_disambiguated.json).
It creates one resource with 13 names, four descriptions and system identifiers.
Strings become Arches 7.6 English tile values
(`{"en": {"value": "...", "direction": "ltr"}}`), and the primary reference number
is numeric. Source resource/tile IDs and legacy ID are retained. Tile sortorder
comes from saved array order, starting at zero per section; this is deterministic
test ordering, not recovered source sortorder.

The [concept fixture](../tests/fixtures/pkg/reference_data/st_bernards_concepts.json)
contains the 11 concept values used by these sections and their five collections:
Name Use Type, Currency Type, Description Type, Languages and Metatypes.
It retains source concept/value/collection UUIDs and English preferred labels.
Relation IDs are test-local; legacy concept identifiers use concept UUIDs rather
than unknown source legacy IDs. This is a minimal subset, not a full vocabulary.

The loader validates value metadata and collection membership, writes
ResourceInstance/TileModel records atomically, and rejects duplicate loads.
Unpopulated concept fields remain null. Other sections are omitted and reported;
no related resources are created. It does not run Resource/Tile save hooks,
index the resource or copy source descriptors. It is test scaffolding, not a
general API importer. Tests use saved fixtures without contacting the source
instance, but database/search-backed tests still need their local services.

## Extending the implementation

- **Operation:** add an `OperationType`, implementation and `OPERATION_HANDLERS`
  entry; add its example to the operation tests and update the
  [operation reference](./USER_GUIDE.md#operations).
- **Datatype:** extend `DisplayDescriptorService._extract_value()` and test the
  resulting engine input shape.
- **HTTP diagnostics:** update the views and document their precise response
  contract and capture scope.
