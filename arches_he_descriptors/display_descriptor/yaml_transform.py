import yaml
from typing import Any, Dict, List, Tuple


def _yaml_scalar(value: str) -> str:
    dumped = yaml.safe_dump(value, default_flow_style=True, allow_unicode=False).strip()
    if dumped.endswith("..."):
        dumped = dumped[:-3].rstrip()
    return dumped


def _normalize_label(value: Any) -> str:
    return str(value or "").strip()


def _resolve_as_graph_name(
    raw_name: str,
    node_by_name: Dict[str, Dict[str, str]],
) -> Tuple[str, str]:
    node = node_by_name.get(raw_name)
    if not node:
        return raw_name, ""
    return node["name"], node["nodeid"]


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


def _render_field_lines(field_specs: List[Dict[str, Any]]) -> str:
    lines = ["fields:"]

    for field_spec in field_specs:
        ambiguous_parent = field_spec.get("ambiguous_parent", [])
        if ambiguous_parent:
            lines.append("  **")
            for candidate in ambiguous_parent:
                lines.append(
                    f"  - name: {_yaml_scalar(candidate['name'])}"
                    f"  # c_name: {candidate['c_name']} | {candidate['nodeid']}"
                )
            lines.append("  **")
        else:
            line = f"  - name: {_yaml_scalar(field_spec['resolved_name'])}"
            if field_spec.get("comment"):
                line += f"  # {field_spec['comment']}"
            lines.append(line)

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
                            f"  # c_name: {candidate['c_name']} | {candidate['nodeid']}"
                        )
                    lines.append("      **")
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
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)

    from arches.app.models.models import CardXNodeXWidget, Node

    node_rows = Node.objects.filter(graph_id=graph_id).values("name", "nodeid")
    node_by_name = {
        row["name"]: {"name": row["name"], "nodeid": str(row["nodeid"])}
        for row in node_rows
    }

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

    for field in fields_data:
        field_name = ""
        subfields = []
        mode = "g"

        if isinstance(field, str):
            field_name = field
        elif isinstance(field, dict):
            if "c_name" in field:
                mode = "c"
                field_name = _normalize_label(field.get("c_name"))
            elif "g_name" in field:
                field_name = _normalize_label(field.get("g_name"))
            else:
                field_name = _normalize_label(field.get("name"))

            raw_subfields = field.get("subfields", [])
            if isinstance(raw_subfields, list):
                subfields = [
                    _normalize_label(s.get("name") if isinstance(s, dict) else s)
                    for s in raw_subfields
                ]

        spec: Dict[str, Any] = {
            "resolved_name": field_name,
            "comment": "",
            "ambiguous_parent": [],
            "subfields": [],
        }

        if mode == "c":
            single, ambiguous = _resolve_as_card_label(field_name, widget_label_index)
            if ambiguous:
                spec["ambiguous_parent"] = ambiguous
            elif single:
                spec["resolved_name"] = single[0]["name"]
                spec["comment"] = f"c_name: {field_name} | {single[0]['nodeid']}"
            else:
                spec["comment"] = f"c_name: {field_name} | unresolved"
        else:
            resolved_name, nodeid = _resolve_as_graph_name(field_name, node_by_name)
            spec["resolved_name"] = resolved_name
            if nodeid:
                spec["comment"] = nodeid
            elif field_name:
                spec["comment"] = "unresolved"

        for subfield in subfields:
            sub_spec = {
                "resolved_name": subfield,
                "comment": "",
                "ambiguous": [],
            }

            if mode == "c":
                single, ambiguous = _resolve_as_card_label(subfield, widget_label_index)
                if ambiguous:
                    sub_spec["ambiguous"] = ambiguous
                elif single:
                    sub_spec["resolved_name"] = single[0]["name"]
                    sub_spec["comment"] = f"c_name: {subfield} | {single[0]['nodeid']}"
                else:
                    sub_spec["comment"] = f"c_name: {subfield} | unresolved"
            else:
                resolved_name, nodeid = _resolve_as_graph_name(subfield, node_by_name)
                sub_spec["resolved_name"] = resolved_name
                if nodeid:
                    sub_spec["comment"] = nodeid
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
            ):
                # Found next top-level key, add everything from here
                remaining = original_lines[i:]
                if remaining:
                    lines.append("")
                    lines.extend(remaining)
                break

    result = "\n".join(lines).rstrip() + "\n"
    return result
