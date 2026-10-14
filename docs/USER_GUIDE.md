# Display descriptor configuration guide

[Back to README](../README.md) |
[Implementation and API reference](./IMPLEMENTATION_GUIDE.md)

Use this guide to author graph-specific YAML for your organisation's resource
models and descriptor policies. The Monument recipes illustrate the approach;
they do not restrict it to that model or vocabulary. First complete the
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
its parent's nodegroup so values can be paired within one tile. Separate parent
fields can come from different cards/nodegroups and contribute to the same rule.
When two values must describe the same repeated row, declare one as a subfield
of the other rather than selecting them independently.
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

#### Resolving a card label that is not a node name

If a saved field declaration is marked `# unresolved`, first check spelling and
the selected graph. Then check whether the text is a card/widget label rather
than the graph node name.

In the supplied Monument graph, the widget label **Confidence of Interpretation
Metatype** belongs to the node named **Phase Certainty Metatype**. Declaring it
with `name: Confidence of Interpretation Metatype` will not find that node.
Instead, enter:

```yaml
fields:
  - c_name: Confidence of Interpretation Metatype
```

On **Save and continue editing**, normalisation produces:

```yaml
fields:
  - name: Phase Certainty Metatype  # c_name: Confidence of Interpretation Metatype | 77e90835-efdc-11eb-91d3-a87eeabdefba
    nodeid: 77e90835-efdc-11eb-91d3-a87eeabdefba
    alias: Confidence of Interpretation Metatype
```

When a resolved card label differs from the node name and no explicit YAML alias
was supplied, the normaliser adds that label as the alias. Rules and format
placeholders can therefore keep using `Confidence of Interpretation Metatype`.
An explicit `alias` takes precedence. The UUID above is specific to the supplied
graph; let normalisation resolve the node in your own graph.

#### Using two parent nodes with the same name

Distinct cards can contain nodes both named `Comment`. Give each declaration
the correct `nodeid` and a different YAML alias so extraction does not put both
values under the same key:

```yaml
fields:
  - name: Comment
    nodeid: a681260a-4288-11ef-a05d-0242ac120006
    alias: First Comment
  - name: Comment
    nodeid: a89c74c0-b530-11ee-99ce-0242ac120006
    alias: Second Comment
display_descriptor_rules:
  - rule:
      - name: First Comment
        default: "No first comment"
        operations:
          - first
      - name: Second Comment
        default: "No second comment"
        operations:
          - first
    format: "{First Comment}; {Second Comment}"
```

The two UUIDs are illustrative: replace them with the parent node IDs from your
graph. For values `"Survey note"` and `"Archive note"`, this renders
`"Survey note; Archive note"`. If a node is missing entirely from the graph,
`default` cannot repair that configuration error; defaults handle missing
resource values.

You can also resolve each parent using its unique graph alias through `n_name`
and assign a separate YAML alias. This example does not extend runtime
`nodeid` support to subfields.

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
Use `"|FIRST"` to select the first row without preferring a particular label;
`"FIRST"` without a pipe is an ordinary equality filter, not that fallback.
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

## Configuration recipes

Both recipes are complete single-section configs for the **Display name** admin
tab. Adapt field names, concept labels and selection policy to your graph, then
use the [admin test panel](#managing-configurations) before saving.

### Monument name example

Prefer an authoritative name regardless of its position in the tile list, and
keep a useful label when no name is available. These fields match the supplied
Monument test graph:

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
          NameUse: "Primary|Statutory|Original|FIRST"
        default: "Unnamed Monument"
        operations:
          - trim
          - titlecase
      - name: Primary Reference Number
        required: true
    format: "[{Primary Reference Number}] {Monument Name}"
  - format: "Unknown monument"
```

For reference number `149652`, consider these names in tile order:

1. `"church of st mary"` with use type Original.
2. `"old church"` with use type Primary.
3. `"parish church"` with use type Statutory.

| Resource data | Result |
| --- | --- |
| All three names above | `[149652] Old Church` |
| Primary name absent | `[149652] Parish Church` |
| Only the Original name remains | `[149652] Church Of St Mary` |
| Only `"local name"` with an unlisted use type remains | `[149652] Local Name` |
| No names | `[149652] Unnamed Monument` |
| Reference number missing | `Unknown monument` |

The `default` lets the required name rule continue when it cannot select a
value. The unconditional final block handles a missing reference number.
The name and reference number come from different nodegroups; the name-use
subfield stays in the name's nodegroup.

The
[Monument integration tests](./IMPLEMENTATION_GUIDE.md#offline-monument-fixtures)
exercise name persistence; their description-priority checks use inline service
configuration rather than the function's description path.

### Synthesising a name from period and functional type

For an unnamed monument, try a period/type label before resorting to
`"Unnamed Monument"`. This recipe uses the supplied graph's `Use Phase Period`
and `Functional Type` nodes, which share a nodegroup:

```yaml
fields:
  - name: Monument Name
    alias: Name
    subfields:
      - name: Monument Name Use Type
        alias: NameUse
  - name: Use Phase Period
    alias: Period
    subfields:
      - name: Functional Type
        alias: Type
  - name: Primary Reference Number
    alias: PRN
display_descriptor_rules:
  - rule:
      - name: Name
        required: true
        field_filters:
          NameUse: "Primary|Statutory|Original|FIRST"
        operations:
          - trim
          - titlecase
      - name: PRN
        required: true
    format: "[{PRN}] {Name}"
  - rule:
      - name: PRN
        required: true
      - name: Period
        required: true
        field_filters:
          Type: "|FIRST"
        operations:
          - first
          - trim
      - name: Type
        required: true
        operations:
          - first
          - trim
    format: "[{PRN}] {Period} {Type}"
  - rule:
      - name: PRN
        required: true
    format: "[{PRN}] Unnamed Monument"
  - format: "Unknown monument"
```

The second block selects the first period-bearing Use Phase row, retaining its
Functional Type subfield. `first` then chooses one period descriptor and one
type if either value is a list. It does not combine a period from one row with
a type from another. If the selected row has no type, the block fails rather
than searching later rows; adapt the selection policy if your graph needs that.

For reference number `149652`:

| Resource data | Result |
| --- | --- |
| Primary name `"old church"` present | `[149652] Old Church` |
| No name; period `"Uncertain"` and type `"Fishermens Fastener"` in the selected row | `[149652] Uncertain Fishermens Fastener` |
| No name; selected row has periods `["Medieval", "Post Medieval"]` and types `["Wreck", "Obstruction"]` | `[149652] Medieval Wreck` |
| No name; no usable period/type pair | `[149652] Unnamed Monument` |
| Reference number missing | `Unknown monument` |

`Use Phase Period` is a resource-instance field: the period text comes from the
related resource's stored name, with the
[related-resource fallback behaviour](./IMPLEMENTATION_GUIDE.md#database-extraction).
Functional types come from concept value labels. Those related resources and
concept values must exist in the destination environment.

These outputs demonstrate rendering with materialised data. The minimal offline
Monument resource loader does not populate Use Phase or create related period
resources, so this is not a claim of existing database-backed coverage for this
recipe. Also, many monuments can share a period/type label; retaining the PRN
helps distinguish them without making the descriptor itself a unique key.

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
