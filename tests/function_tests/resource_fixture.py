import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from django.db import transaction

from arches.app.models import models


SIMPLE_SECTIONS = (
    "Monument Names",
    "Descriptions",
    "System Reference Numbers",
)


@dataclass(frozen=True)
class MonumentFixtureResult:
    resource: models.ResourceInstance
    tiles: tuple[models.TileModel, ...]
    skipped_sections: tuple[str, ...]


def _node_objects(value):
    if isinstance(value, dict):
        if "@node_id" in value:
            yield value
        for child in value.values():
            yield from _node_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _node_objects(child)


def create_monument_resource(source: Path, graph_definition: dict) -> MonumentFixtureResult:
    """Create names, descriptions and identifiers using preloaded concept values."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    if len(payload) != 1:
        raise ValueError("The Monument fixture must contain exactly one resource")
    resource_id, entry = next(iter(payload.items()))
    if str(UUID(resource_id)) != entry["resourceinstanceid"]:
        raise ValueError("The fixture resource key and resourceinstanceid must match")
    if entry["graph_id"] != graph_definition["graphid"]:
        raise ValueError("The Monument fixture does not match the prepared graph")

    nodes = {node["nodeid"]: node for node in graph_definition["nodes"]}
    groups = {group["nodegroupid"]: group for group in graph_definition["nodegroups"]}
    resource_data = entry["resource"]
    planned_tiles = []
    concept_values = {}
    concept_memberships = set()
    tile_ids = set()

    for section in SIMPLE_SECTIONS:
        records = resource_data[section]
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list) or not records:
            raise ValueError(f"The fixture section {section!r} must contain tiles")
        section_group_id = None
        for sortorder, record in enumerate(records):
            collector = nodes[record["@node_id"]]
            group_id = collector["nodegroup_id"]
            if not collector["is_collector"] or collector["datatype"] != "semantic" or groups[group_id]["parentnodegroup_id"] is not None:
                raise ValueError(f"Section {section!r} must use a root nodegroup")
            if section_group_id is not None and section_group_id != group_id:
                raise ValueError(f"Section {section!r} spans multiple nodegroups")
            section_group_id = group_id
            tile_id = str(UUID(record["@tile_id"]))
            if tile_id in tile_ids:
                raise ValueError(f"Duplicate fixture tile ID: {tile_id}")
            tile_ids.add(tile_id)
            data = {}
            for node_object in _node_objects(record):
                node_id = node_object["@node_id"]
                node = nodes[node_id]
                if node_object["@tile_id"] != tile_id or node["nodegroup_id"] != group_id:
                    raise ValueError(f"Node {node_id} does not belong to tile {tile_id}")
                datatype = node["datatype"]
                if datatype == "semantic":
                    continue
                if datatype not in ("string", "number", "concept"):
                    raise ValueError(f"Unsupported simple fixture datatype: {datatype}")
                if datatype == "concept":
                    value = node_object.get("valueid")
                    if value is None:
                        if node_object.get("@display_value") not in (None, ""):
                            raise ValueError(f"Concept node {node_id} has no value ID")
                    else:
                        value = str(UUID(value))
                        metadata = (
                            node_object["concept_id"],
                            node_object["value"],
                            node_object["language_id"],
                            node_object["valuetype_id"],
                        )
                        if value in concept_values and concept_values[value] != metadata:
                            raise ValueError(f"Conflicting concept metadata: {value}")
                        concept_values[value] = metadata
                        concept_memberships.add((node["config"]["rdmCollection"], metadata[0]))
                else:
                    value = node_object["@display_value"]
                if value is not None and datatype != "concept":
                    if not isinstance(value, str):
                        raise ValueError(f"Expected display text for node {node_id}")
                    if datatype == "string":
                        # The source API exposes display text, not language metadata.
                        value = {"en": {"value": value, "direction": "ltr"}}
                    else:
                        value = int(value)
                if node_id in data:
                    raise ValueError(f"Duplicate value for node {node_id}")
                data[node_id] = value
            if not any(value is not None for value in data.values()):
                raise ValueError(f"Tile {tile_id} has no supported populated values")
            planned_tiles.append((tile_id, group_id, sortorder, data))

    with transaction.atomic():
        graph = models.GraphModel.objects.get(pk=entry["graph_id"])
        if graph.publication_id is None:
            raise ValueError("The Monument graph must be published before loading data")
        stored_values = {
            str(value.pk): (
                str(value.concept_id),
                value.value,
                value.language_id,
                value.valuetype_id,
            )
            for value in models.Value.objects.filter(pk__in=concept_values)
        }
        for value_id, metadata in concept_values.items():
            if stored_values.get(value_id) != metadata:
                raise ValueError(f"Missing or mismatched fixture concept value: {value_id}")
        memberships = {
            (str(parent), str(child))
            for parent, child in models.Relation.objects.filter(
                conceptfrom_id__in={parent for parent, _ in concept_memberships},
                relationtype_id="member",
            ).values_list("conceptfrom_id", "conceptto_id")
        }
        if not concept_memberships.issubset(memberships):
            raise ValueError("Fixture concepts must belong to their graph collections")
        resource = models.ResourceInstance.objects.create(
            resourceinstanceid=resource_id,
            graph=graph,
            legacyid=entry["legacyid"],
        )
        tiles = tuple(
            models.TileModel.objects.create(
                tileid=tile_id,
                resourceinstance=resource,
                nodegroup_id=group_id,
                sortorder=sortorder,
                data=data,
            )
            for tile_id, group_id, sortorder, data in planned_tiles
        )

    return MonumentFixtureResult(
        resource=resource,
        tiles=tiles,
        skipped_sections=tuple(section for section in resource_data if section not in SIMPLE_SECTIONS),
    )
