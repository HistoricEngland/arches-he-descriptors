# Display descriptor configuration guide

[Back to README](../README.md) |
[Implementation and API reference](./IMPLEMENTATION_GUIDE.md)

Use this guide to author graph-specific YAML. First complete the
[installation and function assignment](../README.md#integrating-into-an-existing-arches-project).

## Managing configurations

1. Open Django admin's **Display descriptor graph configs** page.
2. Add a record or select the existing record for your graph. The graph dropdown
   includes resource graphs with an ontology.
3. Choose the **Display name**, **Display description** or **Map popup** tab and
   enter YAML for that descriptor.
4. Enter one or more resource UUIDs, separated by commas, in **Test Display
   Descriptor**, then click **Check**. Use resources belonging to the selected
   graph. The test uses the active tab's unsaved YAML.
5. Inspect the descriptor, error or "No descriptor" result. **Show data** reveals
   extracted input; **Show SQL** requires `DEBUG=True`.
6. Save the configuration. Blank sections are removed when the admin form saves.

The list shows graph UUID/name and creation/update timestamps, and supports
search by graph UUID or name. Timestamps are read-only.
The function editor displays saved YAML read-only; edit it in Django admin.
Testing does not save configuration, and saving does not regenerate stored
resource descriptors. See the [README](../README.md#5-assign-and-configure-descriptors)
for enabling rendering and applying changes to existing resources.

## Configuration reference

### Descriptor sections

Each graph has at most one `DisplayDescriptorGraphConfig` record, containing
independent sections for `display_name`, `display_description` and `map_popup`.
The admin presents YAML editors, but stores the sections internally as a JSON
object whose values are raw YAML strings, preserving their formatting:

```json
{
  "display_name": "fields: []\ndisplay_descriptor_rules:\n  - format: Unknown name\n",
  "display_description": "fields: []\ndisplay_descriptor_rules:\n  - format: No description\n",
  "map_popup": "fields: []\ndisplay_descriptor_rules:\n  - format: No popup\n"
}
```

Do not paste this wrapper into an individual section editor or an inline
`config` override: those expect a single configuration.

Legacy flat YAML containing `fields` is treated as the **display name** when a
descriptor type is selected; it is not shared across all three types.
Legacy YAML with top-level per-type mappings is also readable. Admin saves and
section API writes migrate legacy storage to JSON sections.
For programmatic lookup without a type, current JSON sections default to
`display_name`; specify the type explicitly rather than relying on legacy
untyped behaviour.

### Fields and aliases

Declare the fields to extract and optional sibling subfields:

```yaml
fields:
  - name: Monument Name
    alias: Name
    subfields:
      - name: Monument Name Use Type
        alias: NameUse
  - name: Primary Reference Number
    alias: PRN
```

Parent aliases become keys in the extracted payload, rules and format strings.
Subfield aliases can be used in filters, subfield rules and format placeholders.
Without an alias, use the graph node name. Simple fields and subfields can also
be declared as strings.

All extracted nodes must exist in the selected graph. Each subfield must share
its parent's nodegroup so values can be paired within one tile.
Concept tile values must reference concept **value UUIDs**, not concept UUIDs;
filters normally compare their resolved text labels.

#### Graph-aware field normalisation

Admin saves and section API writes support these authoring keys:

| Key | Resolves against |
| --- | --- |
| `name` or `g_name` | Graph node name |
| `c_name` | Card/widget label |
| `n_name` | Node alias |

```yaml
fields:
  - g_name: Monument Name
  - c_name: Site Name (preferred)
  - n_name: primary_reference_number
```

These are alternative declarations illustrating the three lookup modes, not a
suggestion to declare the same node repeatedly. Normalisation writes canonical
`name` entries with provenance comments and explicit parent `nodeid` values.
Arches enforces node alias uniqueness across the entire graph, making `n_name`
an unambiguous lookup for a populated alias. The same alias can be used in a
different graph. Graph node names and card/widget labels can still be ambiguous
and require disambiguation. Graph node aliases are distinct from the YAML
`alias` keys used to name descriptor fields and subfields.

Inline API/service configs bypass normalisation. Use canonical `name`, optional
`alias`, and optional parent `nodeid` there, not `g_name/c_name/n_name`.
Runtime parent `nodeid` resolution still checks the configured node name, so a
node rename requires a configuration update. Subfields must have unambiguous
names: runtime subfield `nodeid` disambiguation is not supported even though
normalisation can emit that key.

If the normaliser marks ambiguous candidates with `**`, retain the intended
candidate using its UUID comment, remove unwanted candidates and the markers,
then save again.

### Rules and defaults

```yaml
display_descriptor_rules:
  - rule:
      - name: Name
        required: true
        field_filters:
          NameUse: "Primary|Statutory|Original|FIRST"
        operations:
          - type: titlecase
      - name: PRN
        default: "No reference"
        format_when_present: "[{PRN}]"
        format_when_default: "({PRN})"
    format: "{PRN} {Name}"
    format_operations:
      - trim
  - format: "Unknown monument"
```

- Blocks are tried in order; the first result other than `None` wins.
- `required: true` rejects a missing value without a default before field
  operations run. `required` is optional and is not true by default.
- `default` replaces a missing value before operations. Missing means `None`,
  blank text, an empty list, or a `{"value": ...}` entry with a missing value.
- `format_when_present` and `format_when_default` format one rule value.
  Their placeholders refer to that rule's name; the block's `format` can refer
  to all populated rule keys and available subfields.
- Operations run sequentially. String operation names such as `trim` are
  shorthand for `{"type": "trim"}`.
- `format_operations` transforms the final interpolated block string.
- An omitted `rule` is equivalent to `rule: []`, useful for unconditional
  fallbacks. An empty rendered string is still a successful engine result.

The Arches function treats blank/no result differently from the engine; see
[function behaviour](./IMPLEMENTATION_GUIDE.md#arches-function-behaviour).

### Filters and subfield context

Filters act on fields containing lists of row dictionaries:

```yaml
field_filters:
  NameUse: "Primary|Statutory|Original|FIRST"
```

A single pipe-delimited specification tries options in order, returning the
first candidate matching the first available option. `FIRST` falls back to the
first remaining candidate. A bare `"|"` leaves candidates unchanged.
Matching is exact and case-sensitive; avoid spaces around pipe tokens.

A list such as `Status: ["Active", "Pending"]` accepts either label and may
return several rows. Multiple filter keys are applied sequentially, with an AND
effect; priority selection may reduce candidates to one before the next key is
checked. Filters do not reject scalar input: they are designed for row lists.

For a single selected row, its subfields are available in the block's format
context under canonical names and aliases. For multiple rows, a subfield is
still exposed if all available values agree; differing values are exposed as
`None`, and a subfield with no available values is omitted. Do not assume
`first` on the parent also chooses corresponding subfield context: use a
priority filter to select one row when the pairing matters.

Example:

```yaml
display_descriptor_rules:
  - rule:
      - name: Name
        required: true
        field_filters:
          NameUse: "Primary|FIRST"
    format: "{Name} ({NameUse})"
```

### Monument name example

This single-section config matches the supplied Monument test graph:

```yaml
fields:
  - name: Monument Name
    subfields:
      - name: Monument Name Use Type
        alias: NameUse
  - name: Primary Reference Number
display_descriptor_rules:
  - rule:
      - name: Monument Name
        required: true
        field_filters:
          NameUse: "Primary|FIRST"
        operations:
          - first
      - name: Primary Reference Number
        required: true
    format: "[{Primary Reference Number}] {Monument Name}"
  - format: "Unknown monument"
```

Adapt names and labels to your graph. The
[Monument integration tests](./IMPLEMENTATION_GUIDE.md#offline-monument-fixtures)
cover name persistence; their description-priority checks use inline service
configuration rather than the function's description path.

## Rendering in Python

For already-materialised data, pass an explicit config:

```python
from arches_he_descriptors.display_descriptor.service import DisplayDescriptorService

config = {
    "fields": ["Primary Reference Number", "Monument Name"],
    "display_descriptor_rules": [{
        "rule": [
            {"name": "Primary Reference Number", "required": True},
            {
                "name": "Monument Name",
                "required": True,
                "field_filters": {"Monument Name Use Type": "Primary|FIRST"},
                "operations": ["titlecase"],
            },
        ],
        "format": "[{Primary Reference Number}] {Monument Name}",
    }],
}
resource = {
    "Primary Reference Number": "ABC123",
    "Monument Name": [
        {"value": "old church", "Monument Name Use Type": "Primary"},
        {"value": "st mary's church", "Monument Name Use Type": "Original"},
    ],
}
descriptor = DisplayDescriptorService().render_with_config(resource, config)
print(descriptor)  # [ABC123] Old Church
```

For a stored **Arches resource instance UUID**, use
`render_display_descriptor_for_resource(resource_id, descriptor_type="display_name")`.
It is not a helper for arbitrary Django model primary keys, and there is no
built-in descriptor mixin. See the [service reference](./IMPLEMENTATION_GUIDE.md#service-and-extraction)
and [HTTP API](./IMPLEMENTATION_GUIDE.md#api-reference) for other entry points.

## Operations

Operations generally leave unsupported input types unchanged. Text operations
apply recursively to list elements, but do not clean values inside dictionaries.
A filtered single-row value is unpacked by rule execution before its operations;
unfiltered row lists remain dictionaries unless an operation extracts values.

| Operation | Behaviour and options |
| --- | --- |
| `trim`, `ltrim`, `rtrim` | Strip whitespace at both ends, left or right |
| `lpad`, `rpad` | Pad text or numbers to `pad_length`; `pad_char` defaults to space and only its first character is used; no effect without a length |
| `normalize_whitespace` | Collapse whitespace to single spaces and strip ends |
| `replace` | Literal `replace_from` to `replace_to` (default empty); `ignore_case` defaults to false |
| `coalesce`, `fallback_text` | Replace null, blank text or an empty list with `coalesce_value` or `fallback_text`; recurse over non-empty lists |
| `remove_diacritics` | Remove combining marks after Unicode decomposition |
| `remove_special_chars` | Keep ASCII letters, digits and whitespace only; remove diacritics first if you want to retain their base letters |
| `titlecase` | Capitalise the first alphabetic character of each whitespace-separated word and lowercase the rest; normalise spacing |
| `uppercase`, `lowercase` | Convert text case |
| `capitalize` | Uppercase the first character and lowercase the rest by default |
| `unique` | List only: deduplicate by stringified value, preserving order; use a row's `value` when present |
| `sort` | List only: sort case-insensitively by stringified value; use a row's `value` when present |
| `reverse` | List only: reverse order |
| `first` | Return the first list element, or `None` for an empty list; leave scalars unchanged |
| `abbreviate` | Concatenate the first `length_per_word` characters of each whitespace-separated word (default 1); case-insensitive `skip_words` (default empty); `uppercase` defaults to true |
| `prefix`, `suffix` | Add `prefix_value` or `suffix_value` to text |
| `truncate` | Limit text to `max_length`, **including** `overflow_indicator` (default `"..."`); no effect without a length |
| `combine` | List to text: join values using `separator` (default `", "`); optional `max_items`, `max_length`, `overflow_indicator` (default `"..."`) |

`titlecase` and `capitalize` also accept `preserve_acronyms: true` to retain
tokens with at least two uppercase letters. The default is false.

Important boundaries:

- List-only operations are no-ops on strings. Put `unique`, `sort` and `reverse`
  **before** `combine`.
- `combine.max_items` silently limits items; it does not append an indicator.
  `combine.max_length` slices the joined text and **then appends** the indicator,
  so the result can exceed that length. Use a final `truncate` for a hard limit.
- `coalesce` cannot rescue a required missing value rejected before operations.
  Use `default`, or make the rule optional when relying on `coalesce`.
- Abbreviation splits on whitespace, not punctuation. For `"St. Mary's Church"`,
  skipping `"st"` does not skip `"St."`.

### Verified example chains

```yaml
operations:
  - remove_diacritics
  - remove_special_chars
  - trim
  - titlecase
  - type: abbreviate
    length_per_word: 2
    skip_words: ["of", "the"]
```

Input `"  St. Mary's Church  "` produces `"STMACH"`.

For a list of strings:

```yaml
operations:
  - unique
  - sort
  - type: combine
    separator: " | "
    max_items: 2
    max_length: 80
    overflow_indicator: " ..."
```

Input `["Church", "Church", "Abbey", "Priory"]` produces `"Abbey | Church"`;
no indicator is added solely because `max_items` excluded `"Priory"`.

To add context:

```yaml
operations:
  - trim
  - titlecase
  - type: prefix
    prefix_value: "[LISTED] "
  - type: suffix
    suffix_value: " - Grade I"
```

Input `"  old church  "` produces `"[LISTED] Old Church - Grade I"`.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No descriptor from preview or a Python payload | Supply an explicit single-section config; there is no default file or graph lookup for in-memory data |
| Stored name unchanged | Enable the function's Display Name switch, publish its assignment and regenerate descriptors |
| `Undefined` from the Arches function | Check that the section exists, output is non-blank, fields resolve and server logs show no rendering errors |
| Missing or ambiguous field | Use the correct graph name; disambiguate parent fields with `nodeid`; use unique subfield names |
| Subfield/nodegroup error | Parent and subfield must be stored in the same nodegroup |
| Filters select nothing | Compare exact resolved labels, not concept UUIDs; check spelling, case and pipe-token whitespace |
| Subfield placeholder is missing or ambiguous | Select one row with a priority filter, or ensure candidates agree; see [subfield context](#filters-and-subfield-context) |
| `unique` or `sort` has no effect | Input may already be a scalar or have passed through `combine` |
| Raw dictionaries appear in output | Filter to a row, or use `combine` to extract row `value` keys; text cleanup does not unpack dictionaries |
| Abbreviation is empty | Check whether `skip_words` excludes every word and whether the input contains usable text |
| Text cuts mid-word | `truncate` is character-based; increase the limit or use `combine.max_items` |
| Admin test reports success HTTP status but an error | Inspect the JSON `error` field; see [API error semantics](./IMPLEMENTATION_GUIDE.md#errors-and-deployment-caveats) |
