# Display Descriptor Engine

This module provides a flexible system for generating display descriptors (human-readable labels) for resources in your Django application.

For a developer-focused explanation of the actual runtime implementation, see `IMPLEMENTATION_GUIDE.md`.

## Overview

The display descriptor system uses a configuration-driven approach to format resource data into readable strings. Configurations are:

- **API Override** - Inline config provided in request body
- **Database-backed** (via Django admin) - Per-graph management without code deployment
- **No-op** - Default behavior if no config provided

Key features:

- Field filtering and prioritization
- Data transformations (titlecase, combine, etc.)
- Fallback rules and defaults
- Complex nested data structures

## Quick Start

### 1. Configuration

Configurations are stored in the database and managed via Django admin interfaces.

#### YAML Configuration Format

Configurations use YAML format:

```yaml
fields:
  - name: Primary Reference Number
  - name: Monument Name
    subfields:
      - Monument Name Use Type

display_descriptor_rules:
  - rule:
      - name: Primary Reference Number
        required: true
      - name: Monument Name
        field_filters:
          "Monument Name Use Type": "Primary|Statutory|Original"
        operations:
          - type: titlecase
        required: true
    format: "[{Primary Reference Number}] {Monument Name}"

  - rule:
      - name: Primary Reference Number
        required: true
      - name: Monument Name
        operations:
          - type: unique
          - type: sort
          - type: combine
            separator: ", "
            max_items: 3
          - type: titlecase
        required: true
    format: "[{Primary Reference Number}] {Monument Name}"

  - rule:
      - name: Primary Reference Number
        required: true
      - name: Monument Name
        default: "Unnamed Monument"
    format: "[{Primary Reference Number}] {Monument Name}"
```

#### Storing Configurations

Store configurations per graph via Django admin:

1. Go to **Django Admin** → **Display Descriptor Graph Configs**
2. Click **Add Display Descriptor Graph Config**
3. Select a graph from the dropdown
4. Paste your YAML configuration
5. Use the built-in **Test Display Descriptor** panel to validate against a real resource UUID
6. Save

For detailed admin interface information, see [Managing Configurations via Django Admin](#5-managing-configurations-via-django-admin).

### 2. Usage in Code

```python
from arches_he_descriptors.display_descriptor.service import render_display_descriptor

# Your resource data
resource = {
    "Primary Reference Number": "ABC123",
    "Monument Name": [
        {"value": "old church", "Monument Name Use Type": "Primary"},
        {"value": "st mary's church", "Monument Name Use Type": "Statutory"},
        {"value": "church of st mary", "Monument Name Use Type": "Original"}
    ]
}

descriptor = render_display_descriptor(resource)
print(descriptor)  # Output: "[ABC123] Old Church"
```

The engine uses the first rule that successfully renders. If a field has filters like `Primary|Statutory|Original`, it returns the **first matching value only**, not an array.

### 3. Usage in Django Models

```python
from django.db import models
from arches_he_descriptors.display_descriptor.service import render_display_descriptor_for_resource

class Monument(models.Model):
    primary_reference_number = models.CharField(max_length=100)

    def get_display_descriptor(self, language="en"):
        return render_display_descriptor_for_resource(
            resource_id=str(self.pk),
            language=language,
        )
```

There is no built-in `DisplayDescriptorMixin` in this package; use the service helpers directly.

### 4. API Endpoints

All endpoints require a trailing slash:

- `GET /api/display-descriptor/config/<graph_id>/` - Fetch graph-scoped YAML config for the function editor
- `POST /api/display-descriptor/admin-test/` - Test YAML against a resource UUID from the admin form

The following view functions exist in `display_descriptor/views.py` but are not mapped in this project's `urls.py` by default:

- `GET|POST /api/display-descriptor/<resource_id>/`
- `POST /api/display-descriptor/preview/`

If you wire these routes in your project, they support:

- `?descriptor_only=false` to include input payload
- `?include_sql=true` to include SQL trace metadata when `DEBUG=True`
- `?include_yaml=true` to include the resolved YAML config string in the JSON response
- `?strict_sortorder=true` for DB-backed extraction consistency checks

### 5. Managing Configurations via Django Admin

Display descriptor configurations can be managed through the Django admin interface, allowing non-developers to create and edit configurations per graph without code deployment.

#### Database-Backed Configurations

Configurations are stored in the `DisplayDescriptorGraphConfig` model (one config per resource graph via `graph_id` foreign key). This enables:

- **Graph-scoped storage**: Each resource graph can have its own display descriptor configuration
- **Easy editing**: Non-technical users can update configurations via admin UI
- **Testing before save**: In-admin test panel validates configurations without saving

#### Admin Interface Features

Navigate to **Django Admin** → **Display Descriptor Graph Configs**:

- **List View**:
  - Shows all configured graphs with their names, update timestamps, and creation timestamps
  - Search by graph ID or graph name
  - Sort by graph name, updated date, or created date
  - Icons indicate recently modified configurations

- **Add/Edit Form**:
  - **Graph ID**: Dropdown selector (auto-populated with resource graphs only)
  - **YAML Config**: Large textarea with monospace font for easier editing
  - **Timestamps**: Auto-populated read-only fields (created_at, updated_at)

#### In-Admin Test Panel

The admin change form includes a built-in test panel to validate your configuration against a real resource **without saving first**:

1. Enter a **Resource UUID** in the test section
2. Click the **Check** button
3. The panel immediately shows:
   - ✅ **Green** - The rendered display descriptor (success)
   - ❌ **Red** - Error message explaining what went wrong (e.g., invalid YAML, missing fields)
   - ⚠️ **Orange** - "No descriptor" message (expected for no-op configs)

This allows you to iterate on your YAML configuration and test each change without saving or reloading the form.

#### Configuration Precedence Chain

The display descriptor system resolves configurations in this order:

1. **API Override** (if provided in request body as `config`)
  - Programmatic call with `config_data` (for example via `DisplayDescriptorService.render_for_resource(...)`)
  - Or `POST /api/display-descriptor/<resource_id>/` if you wire that route
   - Highest priority; used for one-off custom renders

2. **Graph Database Lookup** (if graph has a stored config)
   - Looks up `DisplayDescriptorGraphConfig.objects.filter(graph_id=...)`
   - Used for production display descriptors
   - Managed via Django admin

3. **No-op** (no config found)
   - Returns `None` (no descriptor generated)
   - Default behavior if neither API override nor DB config exists

**Example flow for a resource:**

```python
from arches_he_descriptors.display_descriptor.service import DisplayDescriptorService

service = DisplayDescriptorService()

# 1. Programmatic render with inline config
service.render_for_resource(resource_id, config_data={"fields": [...], "display_descriptor_rules": [...]})
# → Uses inline config (API override)

# 2. Programmatic render without inline config
service.render_for_resource(resource_id)
# → Looks up the resource's graph_id
# → Searches DisplayDescriptorGraphConfig for that graph
# → Uses stored DB config if found, returns None otherwise

# 3. User tests config in admin without saving
# → Reads current form values (textarea + dropdown)
# → Sends to /api/display-descriptor/admin-test/
# → Returns result immediately (no DB save needed)
```

#### Admin-Test Endpoint

**Endpoint**: `POST /api/display-descriptor/admin-test/`

Used by the in-admin test panel to validate configurations.

**Request body**:
```json
{
  "resource_id": "<uuid>",
  "graph_id": "<uuid>",
  "yaml_config": "fields:\n  - name: Field1\n..."
}
```

**Response**:
```json
{
  "display_descriptor": "Rendered descriptor string or null",
  "error": null
}
```

If testing fails:
```json
{
  "display_descriptor": null,
  "error": "Error description (e.g., 'Invalid YAML', 'Field not found')"
}
```

This endpoint is primarily for admin UI use but can be called programmatically for testing.

## Configuration Format

### Per-Descriptor-Type Sections

When you need different configurations for the display name, display description, and map popup, store the config as a JSON object with three top-level keys:

```json
{
  "display_name": "fields:\n  - name: Primary Reference Number\n...",
  "display_description": "fields:\n  - name: Monument Name\n...",
  "map_popup": "fields:\n  - name: Monument Type\n..."
}
```

Each value is a complete YAML string for that descriptor type. Sections can be edited independently via the admin interface — the section picker in the editor lets you switch between `display_name`, `display_description`, and `map_popup`.

If no per-type format is used (i.e. the config is plain YAML rather than a JSON object), the same config is used for all three descriptor types.

### Fields

Define the fields your resources have:

```yaml
fields:
  - name: Simple Field
  - name: Complex Field
    subfields:
      - Subfield 1
      - Subfield 2
```

#### Field Name Resolution

By default, field names are matched against the **graph node name** (the label shown in the graph designer). Three alternative keys let you control how the name is resolved:

| Key | Resolves against | Use when |
|-----|-----------------|----------|
| `name` or `g_name` | Graph node name | Node name is unique in the graph (default) |
| `c_name` | Card/widget label | Multiple nodes share the same graph name but have distinct card labels |
| `n_name` | Node alias | You want a stable, slug-style identifier that is guaranteed unique (e.g. `primary_reference_number`) |

```yaml
fields:
  # Default: match by graph node name
  - name: Primary Reference Number

  # Explicit graph name (same as name:)
  - g_name: Monument Name

  # Match by card/widget label
  - c_name: Site Name (preferred)

  # Match by node alias — most stable, immune to label changes
  - n_name: primary_reference_number
```

When the admin normalisation tool runs, it resolves these to the canonical node name and records the resolved nodeid in a comment so the config remains stable even if labels change later:

```yaml
fields:
  - name: Primary Reference Number  # n_name: primary_reference_number | <uuid>
    nodeid: <uuid>
```

### Rules

Each rule block defines how to format the descriptor:

```yaml
display_descriptor_rules:
  - rule:
      - name: Field Name
        required: true/false
        default: "Default Value"
        field_filters:
          "Filter Field": ["Allowed", "Values"]
        operations:
          - type: titlecase
          - type: combine
            separator: ", "
            max_items: 3
        format_when_present: "Custom format for present values"
        format_when_default: "Custom format for defaults"
    format: "Overall format string: {Field Name}"
    format_operations:
      - type: trim   # optional post-format operation(s) for final descriptor
```

### Subfields in format strings

You can reference subfields in a block format when the parent field is declared with subfields.

Example:

```yaml
fields:
  - name: Monument Name
    subfields:
      - Monument Name Use Type

display_descriptor_rules:
  - rule:
      - name: Monument Name
        field_filters:
          Monument Name Use Type:
            - Primary|Original|FIRST
    format: "{Monument Name} ({Monument Name Use Type})"
```

Important: subfield placeholders in format only work when the selected rule value resolves to a single entry.

If field_filters return multiple matches, the engine returns a list of parent values and does not expose subfield values to the format context.

To make subfield placeholders available reliably, use filters that collapse to one match (for example, an ordered priority ending with FIRST).

Fallback/default rule blocks can omit `rule` entirely and provide only `format`:

```yaml
display_descriptor_rules:
  - format: "Unknown"
```

This is treated the same as `rule: []`.

## Advanced Examples

### Example 1: Clean and Format Names

```yaml
operations:
  - type: remove_special_chars    # Remove punctuation
  - type: trim                    # Remove whitespace
  - type: titlecase               # Proper case
  - type: abbreviate              # Create acronym
    skip_words: ["of", "the"]
    length_per_word: 2            # Use first 2 chars per word
```

Input: "  St. Mary's Church  " → Output: "StMaCh" (or "ST MAR CH" depending on settings)

### Example 2: Combine Multiple with Limits

```yaml
operations:
  - type: unique                  # Remove duplicate names
  - type: sort                    # Sort alphabetically
  - type: combine
    separator: " | "
    max_items: 2                  # Show max 2 items
    max_length: 80                # Truncate combined string
    overflow_indicator: " ..."
```

Input: `["Church", "Church", "Abbey", "Priory"]` → Output: "Abbey | Church ..."

### Example 3: Abbreviation with Context

```yaml
operations:
  - type: abbreviate
    length_per_word: 1
    skip_words: ["of", "the", "at"]
    uppercase: true
```

Input: "The Church of St Mary" → Output: "CSM"
Input: "Abbey at Westminster" → Output: "AW"

### Example 4: Add Metadata

```yaml
operations:
  - type: trim
  - type: titlecase
  - type: prefix
    prefix_value: "[LISTED] "
  - type: suffix
    suffix_value: " - Grade I"
```

Input: "  old church  " → Output: "[LISTED] Old Church - Grade I"

## Operations

All operations process strings and/or lists and chain together sequentially in the order defined.

### Operation Scope

Understanding which operations work on strings, lists, or both is critical for avoiding errors:

| Operation | Input Type | Output Type | Notes |
|-----------|-----------|-----------|-------|
| `trim` | String or List | Same as input | Applies to each string in list |
| `ltrim` | String or List | Same as input | Left trim only |
| `rtrim` | String or List | Same as input | Right trim only |
| `lpad` | String or List | Same as input | Left pad to `pad_length` |
| `rpad` | String or List | Same as input | Right pad to `pad_length` |
| `normalize_whitespace` | String or List | Same as input | Collapses whitespace and trims ends |
| `replace` | String or List | Same as input | Literal string replacement (case-sensitive by default) |
| `coalesce` | String/List/None | Usually String | Replaces empty/null with fallback |
| `fallback_text` | String/List/None | Usually String | Alias of `coalesce` for non-technical configs |
| `remove_diacritics` | String or List | Same as input | Applies to each string in list |
| `remove_special_chars` | String or List | Same as input | Applies to each string in list |
| `titlecase` | String or List | Same as input | Applies to each string in list |
| `uppercase` | String or List | Same as input | Applies to each string in list |
| `lowercase` | String or List | Same as input | Applies to each string in list |
| `capitalize` | String or List | Same as input | Applies to each string in list |
| `unique` | List only | List | No effect on strings |
| `sort` | List only | List | No effect on strings |
| `reverse` | List only | List | No effect on strings |
| `abbreviate` | String or List | Same as input | Applies to each string in list |
| `prefix` | String or List | Same as input | Applies to each string in list |
| `suffix` | String or List | Same as input | Applies to each string in list |
| `truncate` | String or List | Same as input | Applies to each string in list |
| `combine` | List only | String | Joins list into single string |

**Critical Point:** After `combine`, you have a **string**, not a list. List operations (`unique`, `sort`, `reverse`) won't work after combining.

Use `format_operations` on a rule block to transform the **final descriptor string** after `format` interpolation (for example `trim`, `ltrim`, or `rtrim`).

### Text Cleaning

- **`trim`** — Remove leading/trailing whitespace
  ```yaml
  - type: trim
  ```

- **`remove_diacritics`** — Strip accents (e.g., "Château" → "Chateau")
  ```yaml
  - type: remove_diacritics
  ```

- **`remove_special_chars`** — Remove punctuation, keep alphanumerics and spaces
  ```yaml
  - type: remove_special_chars
  ```

- **`lpad`** — Left-pad to a fixed length
  ```yaml
  - type: lpad
    pad_length: 12
    pad_char: "0"    # optional, defaults to space
  ```

- **`rpad`** — Right-pad to a fixed length
  ```yaml
  - type: rpad
    pad_length: 20
    pad_char: "."    # optional, defaults to space
  ```

- **`normalize_whitespace`** — Collapse repeated whitespace to single spaces and trim ends
  ```yaml
  - type: normalize_whitespace
  ```

- **`replace`** — Literal text replacement
  ```yaml
  - type: replace
    replace_from: "Church Of"
    replace_to: "Church of"
    ignore_case: true      # optional, default: false
  ```

- **`coalesce`** — Fallback when value is null/empty
  ```yaml
  - type: coalesce
    coalesce_value: "Unknown"
  ```

- **`fallback_text`** — Alias of `coalesce` with friendlier naming
  ```yaml
  - type: fallback_text
    fallback_text: "Unknown"
  ```

### Case Transformations

- **`titlecase`** — Capitalize first letter of each word, rest lowercase
  ```yaml
  - type: titlecase
  ```

- **`uppercase`** — Convert to uppercase
  ```yaml
  - type: uppercase
  ```

- **`lowercase`** — Convert to lowercase
  ```yaml
  - type: lowercase
  ```

- **`capitalize`** — Capitalize only first character, rest lowercase
  ```yaml
  - type: capitalize
  ```

### List Operations

- **`unique`** — Remove duplicates, preserve order
  ```yaml
  - type: unique
  ```

- **`sort`** — Sort alphabetically (case-insensitive)
  ```yaml
  - type: sort
  ```

- **`reverse`** — Reverse list order
  ```yaml
  - type: reverse
  ```

### Length Control

- **`truncate`** — Limit string to max length with optional indicator
  ```yaml
  - type: truncate
    max_length: 50
    overflow_indicator: "..."  # Default: "..."
  ```

### Text Formatting

- **`abbreviate`** — Create acronym from first letters of words
  ```yaml
  - type: abbreviate
    length_per_word: 1          # Chars per word (default: 1)
    skip_words: ["of", "the"]   # Words to skip (default: [])
    uppercase: true             # Uppercase output (default: true)
  ```
  
  **Examples:**
  - "Church Of Saint Mary" (no skip_words) → "COSM"
  - "Church Of Saint Mary" (skip_words: ["of"]) → "CSM"
  - "Church Of Saint Mary" (length_per_word: 2, skip_words: ["of"]) → "CHSAMA"
  - "The Old Church" (skip_words: ["the"]) → "OC"
  - "The Old Church" (uppercase: false) → "oc"

- **`prefix`** — Add prefix to value
  ```yaml
  - type: prefix
    prefix_value: "[SITE] "
  ```
  
  **Examples:**
  - "Church" with prefix "[LISTED] " → "[LISTED] Church"
  - List ["Church", "Abbey"] with prefix "**" → ["**Church", "**Abbey"]

- **`suffix`** — Add suffix to value
  ```yaml
  - type: suffix
    suffix_value: " (Historic)"
  ```
  
  **Examples:**
  - "Church" with suffix " (Grade I)" → "Church (Grade I)"
  - List ["Church", "Abbey"] with suffix " - Listed" → ["Church - Listed", "Abbey - Listed"]

### Data Combining

- **`combine`** — Join list items with separator
  ```yaml
  - type: combine
    separator: ", "             # String to join with (default: ", ")
    max_items: 3                # Limit number of items
    max_length: 100             # Limit combined string length
    overflow_indicator: "..."   # Appended when truncated (default: "...")
  ```

## Operation Order Matters

The sequence of operations dramatically affects output. Consider these examples:

### Example: `sort` BEFORE vs AFTER `combine`

**Input:** `["zebra", "apple", "cherry"]`

**Chain 1: `sort → combine` (CORRECT)**
```yaml
operations:
  - type: sort
  - type: combine
    separator: ", "
```
Output: `"apple, cherry, zebra"` ✓ Sorted list then joined

**Chain 2: `combine → sort` (WRONG - unexpected behavior)**
```yaml
operations:
  - type: combine
    separator: ", "
  - type: sort
```
Output: `"zebra, apple, cherry"` ✗ After combine, value is a string and `sort` does nothing.

### Example: `remove_special_chars` Position Changes Abbreviate Result

**Input:** `"St. Mary's Church"`

**Chain 1: `remove_special_chars → abbreviate`**
```yaml
operations:
  - type: remove_special_chars  # "St Marys Church"
  - type: abbreviate
    skip_words: []
```
Output: `"SMC"` ✓ 3-word abbreviation

**Chain 2: Different skip_words affects output**
```yaml
operations:
  - type: abbreviate
    skip_words: ["st", "s"]
```
Output: `"MC"` ⚠️ "St" and possessive "s" are skipped

### Example: List Operations Must Come BEFORE `combine`

**Input:** `["Church", "Church", "Abbey"]`

**Correct: `unique → sort → combine`**
```yaml
operations:
  - type: unique        # ["Church", "Abbey"]
  - type: sort          # ["Abbey", "Church"]
  - type: combine       # "Abbey, Church"
```
Output: `"Abbey, Church"` ✓ Cleaned and readable

**Wrong: `combine` first**
```yaml
operations:
  - type: combine      # String now, not a list
  - type: unique       # Can't use unique on strings!
```
Result: No effect or error ✗

## Common Patterns

Recommended operation sequences for typical use cases:

### Pattern 1: Clean & Format Single Value (from field_filters)

Use when field_filters gives you a single value that needs cleanup:

```yaml
operations:
  - type: remove_special_chars
  - type: trim
  - type: titlecase
```

**Best for:** Monument names after priority filtering

### Pattern 2: Process & Combine Multiple Values

Use when you have a list of values to clean and join:

```yaml
operations:
  - type: remove_special_chars  # Clean each item
  - type: trim                  # Clean each item
  - type: uppercase             # Format each item
  - type: unique                # Remove duplicates (list op)
  - type: sort                  # Sort alphabetically (list op)
  - type: combine               # Join into string
    separator: " | "
    max_items: 3
```

**Best for:** Multiple names, categories, or tags

### Pattern 3: Create Compact Representation

Use to generate short codes or abbreviations:

```yaml
operations:
  - type: remove_special_chars
  - type: trim
  - type: abbreviate
    length_per_word: 1
    skip_words: ["the", "of", "a"]
    uppercase: true
  - type: prefix
    prefix_value: "["
  - type: suffix
    suffix_value: "]"
```

**Best for:** Generating IDs, codes, or short references

### Pattern 4: Add Context & Metadata

Use to enrich the descriptor with classification info:

```yaml
operations:
  - type: titlecase
  - type: suffix
    suffix_value: " (Grade I Listed)"
```

**Best for:** Adding legal status, classification, or categorization

### Pattern 5: Truncate with Care

Use truncate AFTER all cleaning and combining:

```yaml
operations:
  - type: remove_special_chars
  - type: trim
  - type: unique
  - type: sort
  - type: combine
    separator: ", "
    max_items: 5
  - type: truncate               # Apply last
    max_length: 100
    overflow_indicator: " ..."
```

**Best for:** Ensuring output fits UI constraints (database field, display width, etc.)

## Operation Chaining

Operations execute sequentially — output of one becomes input to the next. Order matters:

```yaml
operations:
  - type: remove_special_chars
  - type: trim
  - type: remove_diacritics
  - type: titlecase
  - type: unique
  - type: sort
  - type: combine
    separator: " | "
  - type: truncate
    max_length: 100
```

## Field Filters

Filter complex fields (lists of dicts) and apply priority selection:

```yaml
field_filters:
  "Monument Name Use Type": "Primary|Statutory|Original"
```

For priority syntax (single pipe-delimited string), the engine tries values in order and returns the **first match only**:
1. Try "Primary" - use if found
2. If not found, try "Statutory" - use if found
3. If not found, try "Original" - use if found

For non-priority filter lists (for example `{"Status": ["Active", "Pending"]}`), multiple matches can be returned.

### Examples

```yaml
# Single filter value
field_filters:
  "Status": ["Active"]

# Priority-based selection (tries in order)
field_filters:
  "Monument Name Use Type": "Primary|Statutory|Original"

# Multiple filters (AND condition)
field_filters:
  "Status": ["Active"]
  "Type": ["Statutory"]
```

## FAQ & Troubleshooting

### Q: I applied `unique` but nothing changed. Why?

**A:** `unique` only works on lists. If your field has field_filters like `Primary|Statutory|Original`, it returns a **single string**, not a list. `unique` is a no-op on strings.

**Solution:** Use `unique` only on fields that genuinely return arrays (e.g., before calling `combine`).

### Q: My abbreviation is empty or wrong

**A:** Likely causes:
1. **`skip_words` included all words** — If you `skip_words: ["church", "chapel", "abbey"]` and input is only those words, abbreviate returns empty.
2. **Applied abbreviate to wrong data** — Make sure input is a string (or list of strings), not already abbreviated.

**Solution:** 
- Don't skip words that will definitely appear
- Check skip_words are lowercase (matching is case-insensitive)
- Test with simpler inputs first

### Q: Why is my `truncate` cutting off mid-word?

**A:** `truncate` is character-based, not word-based. `max_length: 20` cuts exactly at 20 characters, even mid-word.

**Solution:** 
- Increase `max_length` to accommodate longer words
- Consider using `combine` with `max_items` to limit items instead of characters
- Pair truncate with `overflow_indicator` to show it was truncated

### Q: Field filters with priority (e.g., `Primary|Statutory|Original`) — when do I use `combine`?

**A:** 
- **WITHOUT `combine`**: Priority filters return the **first matching single value**. Use this when you want ONE choice.
  ```yaml
  field_filters:
    "Monument Name Use Type": "Primary|Statutory|Original"
  ```
  Result: Single string (e.g., "Old Church"), not an array

- **WITH `combine`**: Skip field_filters; pass the raw list and let combine join them:
  ```yaml
  operations:
    - type: unique
    - type: combine
      separator: ", "
  ```
  Result: Joined string (e.g., "Old Church, St Mary's Church, Church of St Mary")

**When to use each:**
- Use **field_filters + priority** when you want ONE authoritative name
- Use **combine** when you want to show multiple names merged into a readable list

### Q: `combine` is joining incorrectly. I see dict objects like `{'value': '...'}` in output

**A:** `combine` expects either strings or dicts with a `'value'` key. If your dicts don't have `'value'`, or if extraction isn't working, dicts get converted to strings.

**Solution:**
- Ensure your input data has properly formatted dicts: `{"value": "...", "type": "..."}`
- Use `remove_special_chars` or other cleaning operations that handle dicts correctly

### Q: Can I use conditional logic in operations?

**A:** Not directly. Operations chain sequentially without conditionals.

**Solution:** Use **multiple rule blocks** instead; each rule is tried in order, and the first that succeeds is used. Customize per rule:

```yaml
display_descriptor_rules:
  - rule:  # Rule 1: For Primary monuments
      - name: Monument Name
        field_filters:
          "Monument Name Use Type": "Primary"  # Only matches Primary
        operations:
          - type: uppercase
    format: "[PRIMARY] {Monument Name}"
  
  - rule:  # Rule 2: For non-Primary monuments
      - name: Monument Name
        operations:
          - type: titlecase
    format: "[OTHER] {Monument Name}"
```

### Q: What exactly happens when operations apply to a list?

**A:** For operations marked `String or List`:
- **Input is string** → Operation applied to string → Output is string
- **Input is list** → Operation applied to each item → Output is list of same length

Example with `titlecase` on a list:
```
Input:  ["old church", "st marys"]
Output: ["Old Church", "St Marys"]
```

But `combine` is special:
- **Input is list** → All items joined → Output is **single string**
- After `combine`, you cannot use list operations like `unique` or `sort`