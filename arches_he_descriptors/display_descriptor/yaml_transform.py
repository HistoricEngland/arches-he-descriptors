import yaml
import json
import re
from typing import Any, Dict, List, Optional, Tuple

UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def _yaml_scalar(value: str) -> str:
    dumped = yaml.safe_dump(value, default_flow_style=True, allow_unicode=False).strip()
    if dumped.endswith("..."):
        dumped = dumped[:-3].rstrip()
    return dumped


def _normalize_label(value: Any) -> str:
    return str(value or "").strip()


def _resolve_as_graph_name(
    raw_name: str,
    node_name_index: Dict[str, List[Dict[str, str]]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    matches = node_name_index.get(raw_name, [])
    if len(matches) == 1:
        return matches, []
    if len(matches) > 1:
        return [], matches
    return [], []


def _resolve_as_card_label(
    raw_label: str,
    widget_label_index: Dict[str, List[Dict[str, str]]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    matches = widget_label_index.get(raw_label, [])
    if len(matches) == 1:
        return matches, []
    if len(matches) > 1:
        return [], matches
    return [], []


def _extract_uuid_from_comment(line: str) -> str:
    if "#" not in line:
        return ""
    comment = line.split("#", 1)[1]
    match = UUID_RE.search(comment)
    if not match:
        return ""
    return match.group(0)


def _extract_fields_uuid_hints(
    yaml_config: str, field_count: int
) -> List[Dict[str, Any]]:
    hints: List[Dict[str, Any]] = [
        {"preferred_nodeid": "", "subfields": []} for _ in range(field_count)
    ]
    if not yaml_config or field_count == 0:
        return hints

    lines = yaml_config.split("\n")
    in_fields = False
    current_field_index = -1
    in_subfields = False
    in_ambiguous_block = False

    for line in lines:
        stripped = line.strip()

        if not in_fields:
            if stripped == "fields:":
                in_fields = True
            continue

        # End of fields section when next top-level key is reached.
        if stripped and not line.startswith((" ", "\t")):
            break

        if stripped == "**":
            in_ambiguous_block = not in_ambiguous_block
            continue

        if line.startswith("    subfields:"):
            in_subfields = True
            continue

        if line.startswith("  - ") and not line.startswith("      - "):
            in_subfields = False
            if in_ambiguous_block:
                continue
            current_field_index += 1
            if current_field_index >= field_count:
                continue
            hints[current_field_index]["preferred_nodeid"] = _extract_uuid_from_comment(
                line
            )
            continue

        if line.startswith("      - ") and in_subfields:
            if current_field_index < 0 or current_field_index >= field_count:
                continue
            if in_ambiguous_block:
                continue
            hints[current_field_index]["subfields"].append(
                _extract_uuid_from_comment(line)
            )

    return hints


def _select_by_preferred_nodeid(
    single: List[Dict[str, str]],
    ambiguous: List[Dict[str, str]],
    preferred_nodeid: str,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    if single or not ambiguous or not preferred_nodeid:
        return single, ambiguous

    matched = [
        candidate for candidate in ambiguous if candidate["nodeid"] == preferred_nodeid
    ]
    if len(matched) == 1:
        return matched, []

    return single, ambiguous


def _render_field_lines(field_specs: List[Dict[str, Any]]) -> str:
    lines = ["fields:"]

    for field_spec in field_specs:
        ambiguous_parent = field_spec.get("ambiguous_parent", [])
        if ambiguous_parent:
            lines.append("  **")
            for candidate in ambiguous_parent:
                lines.append(
                    f"  - name: {_yaml_scalar(candidate['name'])}"
                    f"  # {candidate['match_key']}: {candidate['match_value']} | {candidate['nodeid']}"
                )
            lines.append("  **")
        else:
            line = f"  - name: {_yaml_scalar(field_spec['resolved_name'])}"
            if field_spec.get("comment"):
                line += f"  # {field_spec['comment']}"
            lines.append(line)
            if field_spec.get("nodeid"):
                lines.append(f"    nodeid: {field_spec['nodeid']}")
            if field_spec.get("alias"):
                lines.append(f"    alias: {_yaml_scalar(field_spec['alias'])}")

        subfields = field_spec.get("subfields", [])
        if subfields:
            lines.append("    subfields:")
            for subfield in subfields:
                ambiguous_subfield = subfield.get("ambiguous", [])
                if ambiguous_subfield:
                    lines.append("      **")
                    for candidate in ambiguous_subfield:
                        lines.append(
                            f"      - {_yaml_scalar(candidate['name'])}"
                            f"  # {candidate['match_key']}: {candidate['match_value']} | {candidate['nodeid']}"
                        )
                    lines.append("      **")
                else:
                    has_structured_keys = bool(
                        subfield.get("nodeid") or subfield.get("alias")
                    )
                    if has_structured_keys:
                        sub_line = (
                            f"      - name: {_yaml_scalar(subfield['resolved_name'])}"
                        )
                        if subfield.get("comment"):
                            sub_line += f"  # {subfield['comment']}"
                        lines.append(sub_line)
                        if subfield.get("nodeid"):
                            lines.append(f"        nodeid: {subfield['nodeid']}")
                        if subfield.get("alias"):
                            lines.append(
                                f"        alias: {_yaml_scalar(subfield['alias'])}"
                            )
                    else:
                        sub_line = f"      - {_yaml_scalar(subfield['resolved_name'])}"
                        if subfield.get("comment"):
                            sub_line += f"  # {subfield['comment']}"
                        lines.append(sub_line)

    return "\n".join(lines)


def _dump_key_value(key: str, value: Any) -> str:
    dumped = yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=False).rstrip()
    return dumped


def normalize_config_yaml_for_graph(yaml_config: str, graph_id) -> str:
    data = yaml.safe_load(yaml_config) if yaml_config else {}
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Display descriptor YAML must deserialize to an object")

    fields_data = data.get("fields")
    if not isinstance(fields_data, list):
        # Nothing to normalise — return the original string to preserve formatting and quotes
        return yaml_config or ""

    from arches.app.models.models import CardXNodeXWidget, Node

    node_rows = Node.objects.filter(graph_id=graph_id).values("name", "nodeid")
    node_name_index: Dict[str, List[Dict[str, str]]] = {}
    for row in node_rows:
        name = _normalize_label(row["name"])
        if not name:
            continue

        bucket = node_name_index.setdefault(name, [])
        candidate = {"name": row["name"], "nodeid": str(row["nodeid"])}
        if not any(existing["nodeid"] == candidate["nodeid"] for existing in bucket):
            bucket.append(candidate)

    label_rows = (
        CardXNodeXWidget.objects.filter(card__graph_id=graph_id)
        .select_related("node")
        .all()
    )

    widget_label_index: Dict[str, List[Dict[str, str]]] = {}
    for row in label_rows:
        label = _normalize_label(row.label)
        if not label:
            continue

        bucket = widget_label_index.setdefault(label, [])
        candidate = {
            "name": row.node.name,
            "nodeid": str(row.node.nodeid),
            "c_name": label,
        }
        if not any(existing["nodeid"] == candidate["nodeid"] for existing in bucket):
            bucket.append(candidate)

    field_specs: List[Dict[str, Any]] = []
    field_hints = _extract_fields_uuid_hints(yaml_config, len(fields_data))

    for field_index, field in enumerate(fields_data):
        field_name = ""
        subfields: List[Dict[str, str]] = []
        mode = "g"
        parent_match_key = "name"
        explicit_parent_nodeid = ""
        field_alias = ""

        if isinstance(field, str):
            field_name = field
        elif isinstance(field, dict):
            if "c_name" in field:
                mode = "c"
                parent_match_key = "c_name"
                field_name = _normalize_label(field.get("c_name"))
            elif "g_name" in field:
                parent_match_key = "g_name"
                field_name = _normalize_label(field.get("g_name"))
            else:
                field_name = _normalize_label(field.get("name"))

            explicit_parent_nodeid = _normalize_label(field.get("nodeid"))
            field_alias = _normalize_label(field.get("alias"))

            raw_subfields = field.get("subfields", [])
            if isinstance(raw_subfields, list):
                for s in raw_subfields:
                    if isinstance(s, dict):
                        subfields.append(
                            {
                                "name": _normalize_label(s.get("name")),
                                "nodeid": _normalize_label(s.get("nodeid")),
                                "alias": _normalize_label(s.get("alias")),
                            }
                        )
                    else:
                        subfields.append(
                            {
                                "name": _normalize_label(s),
                                "nodeid": "",
                                "alias": "",
                            }
                        )

        parent_preferred_nodeid = explicit_parent_nodeid or field_hints[
            field_index
        ].get("preferred_nodeid", "")

        spec: Dict[str, Any] = {
            "resolved_name": field_name,
            "nodeid": explicit_parent_nodeid,
            "alias": field_alias,
            "comment": "",
            "ambiguous_parent": [],
            "subfields": [],
        }

        if mode == "c":
            single, ambiguous = _resolve_as_card_label(field_name, widget_label_index)
            single, ambiguous = _select_by_preferred_nodeid(
                single,
                ambiguous,
                parent_preferred_nodeid,
            )
            if ambiguous:
                spec["ambiguous_parent"] = [
                    {
                        "name": candidate["name"],
                        "nodeid": candidate["nodeid"],
                        "match_key": "c_name",
                        "match_value": field_name,
                    }
                    for candidate in ambiguous
                ]
            elif single:
                spec["resolved_name"] = single[0]["name"]
                spec["nodeid"] = single[0]["nodeid"]
                spec["comment"] = f"c_name: {field_name} | {single[0]['nodeid']}"
                if not field_alias and field_name != single[0]["name"]:
                    spec["alias"] = field_name
            else:
                spec["comment"] = f"c_name: {field_name} | unresolved"
        else:
            single, ambiguous = _resolve_as_graph_name(field_name, node_name_index)
            single, ambiguous = _select_by_preferred_nodeid(
                single,
                ambiguous,
                parent_preferred_nodeid,
            )
            if ambiguous:
                spec["ambiguous_parent"] = [
                    {
                        "name": candidate["name"],
                        "nodeid": candidate["nodeid"],
                        "match_key": parent_match_key,
                        "match_value": field_name,
                    }
                    for candidate in ambiguous
                ]
            elif single:
                spec["resolved_name"] = single[0]["name"]
                spec["nodeid"] = single[0]["nodeid"]
                if mode == "g" and parent_match_key == "g_name":
                    spec["comment"] = f"g_name: {field_name}"
            elif field_name:
                spec["comment"] = "unresolved"

        subfield_hints = field_hints[field_index].get("subfields", [])
        for subfield_index, subfield_data in enumerate(subfields):
            subfield = subfield_data["name"]
            explicit_subfield_nodeid = subfield_data.get("nodeid", "")
            subfield_alias = subfield_data.get("alias", "")
            subfield_preferred_nodeid = explicit_subfield_nodeid or (
                subfield_hints[subfield_index]
                if subfield_index < len(subfield_hints)
                else ""
            )
            sub_spec = {
                "resolved_name": subfield,
                "nodeid": explicit_subfield_nodeid,
                "alias": subfield_alias,
                "comment": "",
                "ambiguous": [],
            }

            if mode == "c":
                single, ambiguous = _resolve_as_card_label(subfield, widget_label_index)
                single, ambiguous = _select_by_preferred_nodeid(
                    single,
                    ambiguous,
                    subfield_preferred_nodeid,
                )
                if ambiguous:
                    sub_spec["ambiguous"] = [
                        {
                            "name": candidate["name"],
                            "nodeid": candidate["nodeid"],
                            "match_key": "c_name",
                            "match_value": subfield,
                        }
                        for candidate in ambiguous
                    ]
                elif single:
                    sub_spec["resolved_name"] = single[0]["name"]
                    sub_spec["nodeid"] = single[0]["nodeid"]
                    sub_spec["comment"] = f"c_name: {subfield} | {single[0]['nodeid']}"
                    if not subfield_alias and subfield != single[0]["name"]:
                        sub_spec["alias"] = subfield
                else:
                    sub_spec["comment"] = f"c_name: {subfield} | unresolved"
            else:
                single, ambiguous = _resolve_as_graph_name(subfield, node_name_index)
                single, ambiguous = _select_by_preferred_nodeid(
                    single,
                    ambiguous,
                    subfield_preferred_nodeid,
                )
                if ambiguous:
                    sub_spec["ambiguous"] = [
                        {
                            "name": candidate["name"],
                            "nodeid": candidate["nodeid"],
                            "match_key": "name",
                            "match_value": subfield,
                        }
                        for candidate in ambiguous
                    ]
                elif single:
                    sub_spec["resolved_name"] = single[0]["name"]
                    sub_spec["nodeid"] = single[0]["nodeid"]
                elif subfield:
                    sub_spec["comment"] = "unresolved"

            spec["subfields"].append(sub_spec)

        field_specs.append(spec)

    # Build transformed YAML, preserving original blank lines outside fields section
    lines = []
    in_fields = False
    fields_section_start = None

    # Parse original input to find where fields section starts and preserve spacing before it
    original_lines = yaml_config.split("\n") if yaml_config else []
    for i, line in enumerate(original_lines):
        if line.strip().startswith("fields:"):
            in_fields = True
            fields_section_start = len(lines)
            break
        lines.append(line)

    # Remove trailing blank lines from pre-fields content
    while lines and not lines[-1].strip():
        lines.pop()

    # Add regenerated fields section
    if lines:
        lines.append("")  # blank line before fields

    field_lines = _render_field_lines(field_specs).split("\n")
    lines.extend(field_lines)

    # Find and preserve content after fields section from original
    if in_fields and fields_section_start is not None:
        # Skip to next top-level key in original
        in_original_fields = False
        for i, line in enumerate(
            original_lines[fields_section_start:], fields_section_start
        ):
            stripped = line.strip()
            if stripped.startswith("fields:"):
                in_original_fields = True
            elif (
                in_original_fields
                and stripped
                and not line.startswith(" ")
                and not line.startswith("\t")
                and not stripped.startswith("- ")  # unindented list items are still inside fields
            ):
                # Found next top-level key, add everything from here
                remaining = original_lines[i:]
                if remaining:
                    lines.append("")
                    lines.extend(remaining)
                break

    result = "\n".join(lines).rstrip() + "\n"
    return result


DESCRIPTOR_TYPES = ("display_name", "display_description", "map_popup")


def _load_json_sections(full_str: str) -> Optional[Dict[str, str]]:
    """Return the parsed JSON sections dict if full_str is in JSON-sections format, else None."""
    s = full_str.strip() if full_str else ""
    if not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return {k: v for k, v in parsed.items() if isinstance(v, str)}
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def extract_yaml_section(full_yaml_str: str, descriptor_type: str) -> Optional[str]:
    """Extract a single descriptor-type section from the combined config.

    Supports both the current JSON-sections format and the legacy YAML format.
    Returns the raw section YAML string or None if the section is absent.
    """
    if not full_yaml_str:
        return None

    # Current format: JSON dict of raw YAML strings
    sections = _load_json_sections(full_yaml_str)
    if sections is not None:
        return sections.get(descriptor_type)

    # Legacy YAML format (backward compat)
    try:
        data = yaml.safe_load(full_yaml_str)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None

    # Legacy flat format: top-level 'fields' key is a pre-migration single-section config
    if "fields" in data:
        return full_yaml_str if descriptor_type == "display_name" else None

    section = data.get(descriptor_type)
    if not isinstance(section, dict):
        return None
    # Unavoidable round-trip for old YAML multi-section format
    return yaml.safe_dump(section, sort_keys=False)


def merge_yaml_section(
    full_yaml_str: Optional[str], section_yaml_str: str, descriptor_type: str
) -> str:
    """Replace or insert a descriptor-type section in the combined config.

    Stores sections as a JSON dict of raw YAML strings to preserve user formatting.
    Migrates legacy YAML formats on first write.
    """
    sections: Dict[str, str] = {}

    if full_yaml_str:
        existing = _load_json_sections(full_yaml_str)
        if existing is not None:
            sections = existing
        else:
            # Migrate legacy YAML format
            try:
                data = yaml.safe_load(full_yaml_str)
                if isinstance(data, dict):
                    if "fields" in data:
                        sections["display_name"] = full_yaml_str
                    else:
                        for dt in DESCRIPTOR_TYPES:
                            if dt in data:
                                sections[dt] = yaml.safe_dump(data[dt], sort_keys=False)
            except yaml.YAMLError:
                pass

    sections[descriptor_type] = section_yaml_str
    return json.dumps(sections)

