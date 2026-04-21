import yaml
import json
from collections import defaultdict
from typing import Optional, Dict, Any, List
from uuid import UUID
from .engine import DisplayDescriptorEngine, OperationType
from .schema import (
    DisplayDescriptorConfig,
    FieldDefinition,
    Operation,
    RuleDefinition,
    DisplayDescriptorRuleBlock,
)


class DisplayDescriptorService:
    """Service for managing display descriptor configurations and rendering."""

    def __init__(self):
        self._config_cache: Optional[DisplayDescriptorConfig] = None

    def load_config_from_yaml(self, yaml_str: str) -> DisplayDescriptorConfig:
        """Load configuration from a YAML string."""
        try:
            data = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")

        if not isinstance(data, dict):
            raise ValueError("Display descriptor YAML must deserialize to an object")

        return self._parse_config_data(data)

    def load_config_from_dict(self, data: Dict[str, Any]) -> DisplayDescriptorConfig:
        """Load configuration from a dictionary."""
        return self._parse_config_data(data)

    def load_config_from_json(self, json_str: str) -> DisplayDescriptorConfig:
        """Load configuration from a JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        return self._parse_config_data(data)

    def _parse_config_data(self, data: Dict[str, Any]) -> DisplayDescriptorConfig:
        """Parse raw config data into DisplayDescriptorConfig."""
        fields_data = data.get("fields", [])
        rules_data = data.get("display_descriptor_rules", [])

        fields = []
        for field_data in fields_data:
            if isinstance(field_data, str):
                fields.append(FieldDefinition(name=field_data))
            elif isinstance(field_data, dict):
                name = field_data.get("name", "")
                subfields = field_data.get("subfields", [])
                fields.append(FieldDefinition(name=name, subfields=subfields))

        rule_blocks = []
        for block_data in rules_data:
            rules = []
            for rule_data in block_data.get("rule") or []:
                operations = []
                for op_data in rule_data.get("operations", []):
                    if isinstance(op_data, str):
                        _validate_operation_type(op_data)
                        operations.append(Operation(type=op_data))
                    elif isinstance(op_data, dict):
                        op_type = op_data.get("type")
                        _validate_operation_type(op_type)
                        operations.append(Operation(**op_data))

                rule = RuleDefinition(
                    name=rule_data["name"],
                    required=rule_data.get("required"),
                    default=rule_data.get("default"),
                    format_when_present=rule_data.get("format_when_present"),
                    format_when_default=rule_data.get("format_when_default"),
                    operations=operations,
                    field_filters=_normalize_field_filters(
                        rule_data.get("field_filters", {})
                    ),
                )
                rules.append(rule)

            format_str = block_data.get("format", "")
            format_operations = []
            for op_data in block_data.get("format_operations", []):
                if isinstance(op_data, str):
                    _validate_operation_type(op_data)
                    format_operations.append(Operation(type=op_data))
                elif isinstance(op_data, dict):
                    op_type = op_data.get("type")
                    _validate_operation_type(op_type)
                    format_operations.append(Operation(**op_data))

            rule_blocks.append(
                DisplayDescriptorRuleBlock(
                    rule=rules,
                    format=format_str,
                    format_operations=format_operations,
                )
            )

        return DisplayDescriptorConfig(
            fields=fields, display_descriptor_rules=rule_blocks
        )

    def _load_graph_config(self, graph_id) -> Optional[DisplayDescriptorConfig]:
        """Load graph-scoped descriptor configuration from the database."""
        from ..models import DisplayDescriptorGraphConfig

        row = (
            DisplayDescriptorGraphConfig.objects.filter(graph_id=graph_id)
            .values("yaml_config")
            .first()
        )
        if not row:
            return None

        yaml_config = row.get("yaml_config")
        if not isinstance(yaml_config, str) or yaml_config.strip() == "":
            return None

        try:
            return self.load_config_from_yaml(yaml_config)
        except ValueError as exc:
            raise ValueError(
                f"Invalid display descriptor config for graph {graph_id}: {exc}"
            )

    def _resolve_config(
        self,
        resource_id: str,
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[DisplayDescriptorConfig]:
        """Resolve config with API override precedence, then graph DB lookup."""
        if config_data is not None:
            return self._parse_config_data(config_data)

        graph_id = self._get_resource_graph_id(resource_id)
        return self._load_graph_config(graph_id)

    def render_with_config(
        self, resource: Dict[str, Any], config_data: Dict[str, Any]
    ) -> Optional[str]:
        """Render with an inline config (bypasses file caching)."""
        config = self._parse_config_data(config_data)
        self._config_cache = config
        engine = DisplayDescriptorEngine(config)
        return engine.render(resource)

    def render_with_parsed_config(
        self, resource: Dict[str, Any], config: DisplayDescriptorConfig
    ) -> Optional[str]:
        """Render with a pre-parsed DisplayDescriptorConfig."""
        self._config_cache = config
        engine = DisplayDescriptorEngine(config)
        return engine.render(resource)

    def render(self, resource: Dict[str, Any]) -> Optional[str]:
        """Render a display descriptor for a pre-materialized resource payload.

        This path has no graph context, so it cannot resolve DB-backed config.
        Returning None is the expected no-op behavior unless explicit config is provided.
        """
        return None

    def get_resource_data(
        self,
        resource_id: str,
        language: str = "en",
        strict_sortorder: bool = False,
        config_data: Optional[Dict[str, Any]] = None,
        return_config: bool = False,
    ) -> Any:
        """Build descriptor input data for a resource using resolved config.

        Validates that all configured fields exist in the resource graph and that all
        configured subfields share nodegroup with their parent field.
        """
        config = self._resolve_config(resource_id=resource_id, config_data=config_data)
        if config is None:
            return ({}, None) if return_config else {}

        self._config_cache = config
        node_map = self._resolve_nodes_for_configured_fields(resource_id, config=config)

        grouped_fields: Dict[str, List[FieldDefinition]] = defaultdict(list)
        for field in config.fields:
            grouped_fields[str(node_map[field.name]["nodegroup_id"])].append(field)

        from arches.app.models.models import TileModel

        result: Dict[str, Any] = {}
        concept_ids = set()
        concept_placeholders = []

        for nodegroup_id, fields in grouped_fields.items():
            tile_rows = (
                TileModel.objects.filter(
                    resourceinstance_id=resource_id,
                    nodegroup_id=nodegroup_id,
                )
                .values("tileid", "sortorder", "data")
                .order_by("sortorder", "tileid")
            )

            has_null_sortorder = False
            has_non_null_sortorder = False

            for tile in tile_rows:
                tile_data = tile.get("data") or {}
                sortorder = tile.get("sortorder")

                if sortorder is None:
                    has_null_sortorder = True
                else:
                    has_non_null_sortorder = True

                for field in fields:
                    parent_meta = node_map[field.name]
                    parent_val = self._extract_value(
                        tile_data=tile_data,
                        node_id=parent_meta["nodeid"],
                        datatype=parent_meta["datatype"],
                        language=language,
                        strict_sortorder=strict_sortorder,
                    )

                    if field.subfields:
                        if parent_val is None:
                            continue

                        entry = {"value": parent_val}
                        for subfield_name in field.subfields:
                            sub_meta = node_map[subfield_name]
                            sub_val = self._extract_value(
                                tile_data=tile_data,
                                node_id=sub_meta["nodeid"],
                                datatype=sub_meta["datatype"],
                                language=language,
                                strict_sortorder=strict_sortorder,
                            )
                            entry[subfield_name] = sub_val

                            if sub_meta["datatype"] in {"concept", "concept-list"}:
                                self._collect_concept_ids(
                                    sub_meta["datatype"], sub_val, concept_ids
                                )
                                concept_placeholders.append(
                                    (
                                        entry,
                                        subfield_name,
                                        sub_meta["datatype"],
                                        sub_val,
                                    )
                                )

                        if parent_meta["datatype"] in {"concept", "concept-list"}:
                            self._collect_concept_ids(
                                parent_meta["datatype"], entry.get("value"), concept_ids
                            )
                            concept_placeholders.append(
                                (
                                    entry,
                                    "value",
                                    parent_meta["datatype"],
                                    entry.get("value"),
                                )
                            )

                        result.setdefault(field.name, []).append(entry)
                    else:
                        if parent_val is None:
                            continue

                        if parent_meta["datatype"] in {"concept", "concept-list"}:
                            self._collect_concept_ids(
                                parent_meta["datatype"], parent_val, concept_ids
                            )

                        result.setdefault(field.name, []).append(parent_val)

            if strict_sortorder and has_null_sortorder:
                raise ValueError(
                    "sortorder validation failed for nodegroup "
                    f"{nodegroup_id}: all tiles must have sortorder set when strict_sortorder=true."
                )

        concept_label_map = self._get_concept_label_map(concept_ids)

        for field_name, values in list(result.items()):
            parent_meta = node_map[field_name]
            if parent_meta["datatype"] == "concept":
                result[field_name] = [
                    concept_label_map.get(v) for v in values if v in concept_label_map
                ]
            elif parent_meta["datatype"] == "concept-list":
                resolved_values = []
                for value in values:
                    resolved_values.extend(
                        self._resolve_concept_value(
                            datatype="concept-list",
                            value=value,
                            concept_label_map=concept_label_map,
                        )
                    )
                result[field_name] = resolved_values

        for entry, key, datatype, concept_value in concept_placeholders:
            entry[key] = self._resolve_concept_value(
                datatype=datatype,
                value=concept_value,
                concept_label_map=concept_label_map,
            )

        for field_name, values in list(result.items()):
            parent_meta = node_map[field_name]
            if parent_meta["datatype"] == "concept-list":
                continue
            if isinstance(values, list) and all(
                not isinstance(v, dict) for v in values
            ):
                if len(values) == 1:
                    result[field_name] = values[0]

        for field in config.fields:
            result.setdefault(field.name, None if not field.subfields else [])

        return (result, config) if return_config else result

    def render_for_resource(
        self,
        resource_id: str,
        language: str = "en",
        strict_sortorder: bool = False,
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Build resource data from the DB and render the configured descriptor."""
        resource_data, config = self.get_resource_data(
            resource_id=resource_id,
            language=language,
            strict_sortorder=strict_sortorder,
            config_data=config_data,
            return_config=True,
        )
        if config is None:
            return None

        engine = DisplayDescriptorEngine(config)
        return engine.render(resource_data)

    def _resolve_nodes_for_configured_fields(
        self, resource_id: str, config: Optional[DisplayDescriptorConfig] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Resolve node metadata for configured fields using the resource's graph."""
        graph_id = self._get_resource_graph_id(resource_id)
        config = config or self._config_cache
        if config is None:
            return {}

        requested_names = []
        for field in config.fields:
            requested_names.append(field.name)
            requested_names.extend(field.subfields)

        requested_names = list(dict.fromkeys(requested_names))

        from arches.app.models.models import Node

        nodes = Node.objects.filter(graph_id=graph_id, name__in=requested_names).values(
            "name", "nodeid", "datatype", "nodegroup_id"
        )

        node_map = {n["name"]: n for n in nodes}

        missing = [name for name in requested_names if name not in node_map]
        if missing:
            raise ValueError(
                "Configured fields are missing from graph "
                f"{graph_id}: {', '.join(sorted(missing))}"
            )

        nodegroup_errors = []
        for field in config.fields:
            parent = node_map[field.name]
            parent_nodegroup = (
                str(parent["nodegroup_id"]) if parent["nodegroup_id"] else None
            )
            for subfield in field.subfields:
                child = node_map[subfield]
                child_nodegroup = (
                    str(child["nodegroup_id"]) if child["nodegroup_id"] else None
                )
                if parent_nodegroup != child_nodegroup:
                    nodegroup_errors.append(
                        f"{field.name} -> {subfield} (parent={parent_nodegroup}, subfield={child_nodegroup})"
                    )

        if nodegroup_errors:
            raise ValueError(
                "Subfield nodegroup validation failed: " + "; ".join(nodegroup_errors)
            )

        return node_map

    def _get_resource_graph_id(self, resource_id: str):
        """Get graph id for a resource instance."""
        from arches.app.models.models import ResourceInstance

        resource = (
            ResourceInstance.objects.filter(resourceinstanceid=resource_id)
            .values("graph_id")
            .first()
        )
        if not resource:
            raise ValueError(f"Resource instance not found: {resource_id}")
        return resource["graph_id"]

    def _extract_value(
        self,
        tile_data: Dict[str, Any],
        node_id,
        datatype: str,
        language: str,
        strict_sortorder: bool = False,
    ) -> Any:
        """Extract a node value from tiledata according to datatype."""
        raw = tile_data.get(str(node_id))
        if raw is None:
            return None

        if datatype == "string":
            if isinstance(raw, dict):
                localized = raw.get(language)
                if isinstance(localized, dict):
                    return localized.get("value")

                for localized_candidate in raw.values():
                    if (
                        isinstance(localized_candidate, dict)
                        and "value" in localized_candidate
                    ):
                        return localized_candidate.get("value")
            if isinstance(raw, str):
                return raw
            return str(raw)

        if datatype == "concept":
            if isinstance(raw, str):
                return raw.strip() or None
            return str(raw)

        if datatype == "concept-list":
            concept_values = self._normalize_concept_values(raw)
            return concept_values or None

        if datatype in {"resource-instance", "resource-instance-list"}:
            related_resource_ids = self._extract_related_resource_ids(raw)
            if not related_resource_ids:
                return None

            descriptors = []
            for related_resource_id in related_resource_ids:
                descriptor = self._get_related_resource_descriptor(
                    resource_id=related_resource_id,
                    language=language,
                )
                if descriptor:
                    descriptors.append(descriptor)

            if not descriptors:
                return None

            if datatype == "resource-instance" and len(descriptors) == 1:
                return descriptors[0]

            return descriptors

        return raw

    def _extract_related_resource_ids(self, raw: Any) -> List[str]:
        """Normalize resource-instance tile payloads into related resource IDs."""
        entries = raw if isinstance(raw, list) else [raw]
        resource_ids: List[str] = []

        for entry in entries:
            if isinstance(entry, dict):
                resource_id = entry.get("resourceId")
            else:
                resource_id = entry

            if resource_id is None:
                continue

            resource_id_str = str(resource_id).strip()
            if resource_id_str:
                resource_ids.append(resource_id_str)

        return list(dict.fromkeys(resource_ids))

    def _normalize_concept_values(self, raw: Any) -> List[str]:
        """Normalize concept payloads into a list of concept IDs."""
        entries = raw if isinstance(raw, list) else [raw]
        concept_values: List[str] = []

        for entry in entries:
            if entry is None:
                continue

            concept_value = str(entry).strip()
            if concept_value:
                concept_values.append(concept_value)

        return list(dict.fromkeys(concept_values))

    def _collect_concept_ids(self, datatype: str, value: Any, concept_ids) -> None:
        """Accumulate concept IDs for later bulk label resolution."""
        if datatype == "concept":
            if value:
                concept_ids.add(value)
            return

        if datatype == "concept-list":
            concept_ids.update(self._normalize_concept_values(value))

    def _resolve_concept_value(
        self,
        datatype: str,
        value: Any,
        concept_label_map: Dict[str, str],
    ) -> Any:
        """Resolve concept UUID placeholders to their labels."""
        if datatype == "concept":
            return concept_label_map.get(value, value)

        if datatype == "concept-list":
            return [
                concept_label_map.get(concept_value, concept_value)
                for concept_value in self._normalize_concept_values(value)
            ]

        return value

    def _get_related_resource_descriptor(
        self,
        resource_id: str,
        language: str,
    ) -> Optional[str]:
        """Resolve a related resource ID to its stored descriptor string."""
        resource_id = str(resource_id).strip()
        if resource_id == "":
            return None

        descriptor = self._get_stored_resource_descriptor(resource_id, language)
        if descriptor is not None:
            descriptor = str(descriptor).strip() or None

        return descriptor or resource_id

    def _get_stored_resource_descriptor(
        self, resource_id: str, language: str, descriptor_type: str = "name"
    ) -> Optional[str]:
        """Read the stored Arches descriptor from ResourceInstance.descriptors."""
        from arches.app.models.models import ResourceInstance

        row = (
            ResourceInstance.objects.filter(resourceinstanceid=resource_id)
            .values("descriptors")
            .first()
        )
        if not row:
            return None

        descriptors = row.get("descriptors") or {}
        if not isinstance(descriptors, dict):
            return None

        localized = descriptors.get(language)
        if isinstance(localized, dict):
            value = localized.get(descriptor_type)
            if value is not None:
                return str(value)

        if language != "en":
            default_localized = descriptors.get("en")
            if isinstance(default_localized, dict):
                value = default_localized.get(descriptor_type)
                if value is not None:
                    return str(value)

        fallback_value = descriptors.get(descriptor_type)
        if fallback_value is not None:
            return str(fallback_value)

        return None

    def _get_concept_label_map(self, concept_ids) -> Dict[str, str]:
        """Resolve concept UUID strings to labels in a single query."""
        normalized_ids = []
        for concept_id in concept_ids:
            try:
                normalized_ids.append(UUID(str(concept_id)))
            except (ValueError, TypeError):
                continue

        if not normalized_ids:
            return {}

        from arches.app.models.models import Value

        return {
            str(row["valueid"]): row["value"]
            for row in Value.objects.filter(valueid__in=normalized_ids).values(
                "valueid", "value"
            )
        }

    def clear_cache(self):
        """Clear cached parsed config."""
        self._config_cache = None


def _validate_operation_type(op_type: str) -> None:
    """Validate that the operation type is valid.

    Args:
        op_type: The operation type string to validate.

    Raises:
        ValueError: If the operation type is not valid.
    """
    if not op_type:
        raise ValueError("Operation type cannot be empty")

    try:
        OperationType(op_type)
    except ValueError:
        valid_types = [op.value for op in OperationType]
        raise ValueError(
            f"Invalid operation type: '{op_type}'. "
            f"Valid types are: {', '.join(valid_types)}"
        )


def _normalize_field_filters(raw_filters: dict) -> dict:
    """Normalize field_filters so each value is a list.

    YAML may provide a scalar string (e.g. "Primary|Statutory|Original").
    Ensure consumers always see a list of values.
    """
    if not isinstance(raw_filters, dict):
        return {}

    normalized: dict = {}
    for k, v in raw_filters.items():
        if isinstance(v, str):
            normalized[k] = [v]
        elif isinstance(v, list):
            normalized[k] = v
        else:
            normalized[k] = [v]

    return normalized


# Global service instance
_display_descriptor_service = None


def get_display_descriptor_service() -> DisplayDescriptorService:
    """Get the global display descriptor service instance."""
    global _display_descriptor_service
    if _display_descriptor_service is None:
        _display_descriptor_service = DisplayDescriptorService()
    return _display_descriptor_service


def render_display_descriptor(resource: Dict[str, Any]) -> Optional[str]:
    """Convenience function to render a display descriptor."""
    service = get_display_descriptor_service()
    return service.render(resource)


def render_display_descriptor_for_resource(
    resource_id: str, language: str = "en", strict_sortorder: bool = False
) -> Optional[str]:
    """Convenience function to build resource data and render a display descriptor."""
    service = get_display_descriptor_service()
    return service.render_for_resource(
        resource_id=resource_id,
        language=language,
        strict_sortorder=strict_sortorder,
    )
