import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from django.db import IntegrityError

from arches.app.datatypes.concept_types import ConceptDataType
from arches.app.datatypes.datatypes import NumberDataType, StringDataType
from arches.app.models import models
from arches.app.models.concept import Concept
from arches.app.models.resource import Resource
from arches_he_descriptors.display_descriptor.service import DisplayDescriptorService
from arches_he_descriptors.functions.arches_he_descriptors import details
from arches_he_descriptors.models import DisplayDescriptorGraphConfig
from tests.function_tests.base_test import BaseDescriptorTestCase
from tests.function_tests.resource_fixture import (
    SIMPLE_SECTIONS,
    _node_objects,
    create_monument_resource,
)


NAME_NODE_ID = "676d47ff-9c1c-11ea-b07f-f875a44e0e11"
DESCRIPTION_NODE_ID = "ba345577-b554-11ea-a9ee-f875a44e0e11"
PRN_NODE_ID = "325a2f33-efe4-11eb-b0bb-a87eeabdefba"
NAME_USE_NODE_ID = "676d47fc-9c1c-11ea-b5b0-f875a44e0e11"
DESCRIPTION_TYPE_NODE_ID = "ba34557b-b554-11ea-ab95-f875a44e0e11"
PRIMARY_VALUE_ID = "2df285fa-9cf2-45e7-bc05-a67b7d7ddc2f"


class MonumentResourceSetupTests(BaseDescriptorTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.resource_source = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "pkg"
            / "business_data"
            / "st_bernards_monument.bulk_disambiguated.json"
        )
        cls.fixture = create_monument_resource(
            cls.resource_source, cls.graph_definition
        )
        cls.descriptor_config = {
            "fields": [
                {
                    "name": "Monument Name",
                    "subfields": [
                        {"name": "Monument Name Use Type", "alias": "NameUse"}
                    ],
                },
                "Primary Reference Number",
            ],
            "display_descriptor_rules": [
                {
                    "rule": [
                        {
                            "name": "Monument Name",
                            "field_filters": {"NameUse": ["Primary|FIRST"]},
                            "operations": ["first"],
                        },
                        {"name": "Primary Reference Number"},
                    ],
                    "format": "[{Primary Reference Number}] {Monument Name}",
                }
            ],
        }
        DisplayDescriptorGraphConfig.objects.create(
            graph_id=cls.monument_graph_id,
            yaml_config=json.dumps(cls.descriptor_config),
        )

    def test_resource_and_simple_tiles_are_created(self):
        resource = self.fixture.resource
        self.assertEqual(str(resource.pk), "f5ab4bd6-43d4-4940-b856-fa6f93c98d4c")
        self.assertEqual(str(resource.graph_id), self.monument_graph_id)
        self.assertEqual(resource.legacyid, str(resource.pk))
        self.assertEqual(resource.graph_publication_id, resource.graph.publication_id)
        self.assertIsNotNone(resource.graph_publication_id)
        self.assertEqual(
            models.TileModel.objects.filter(resourceinstance=resource).count(), 18
        )
        self.assertTrue(all(tile.parenttile_id is None for tile in self.fixture.tiles))
        self.assertIsNone(resource.descriptors)

    def test_names_and_descriptions_preserve_source_order_and_text(self):
        entry = next(iter(json.loads(self.resource_source.read_text()).values()))
        for section, field, node_id, count in (
            ("Monument Names", "Monument Name", NAME_NODE_ID, 13),
            ("Descriptions", "Description", DESCRIPTION_NODE_ID, 4),
        ):
            with self.subTest(section=section):
                group_id = models.Node.objects.get(pk=node_id).nodegroup_id
                tiles = list(
                    models.TileModel.objects.filter(
                        resourceinstance=self.fixture.resource, nodegroup_id=group_id
                    ).order_by("sortorder")
                )
                self.assertEqual(len(tiles), count)
                self.assertEqual([tile.sortorder for tile in tiles], list(range(count)))
                self.assertEqual(
                    [str(tile.pk) for tile in tiles],
                    [record["@tile_id"] for record in entry["resource"][section]],
                )
                self.assertEqual(
                    [tile.data[node_id] for tile in tiles],
                    [
                        {
                            "en": {
                                "value": record[field]["@display_value"],
                                "direction": "ltr",
                            }
                        }
                        for record in entry["resource"][section]
                    ],
                )
                for tile in tiles:
                    self.assertEqual(StringDataType().validate(tile.data[node_id]), [])

    def test_identifier_number_is_numeric(self):
        tile = next(tile for tile in self.fixture.tiles if PRN_NODE_ID in tile.data)
        self.assertEqual(tile.data[PRN_NODE_ID], 149652)
        self.assertIsInstance(tile.data[PRN_NODE_ID], int)
        self.assertEqual(NumberDataType().validate(tile.data[PRN_NODE_ID]), [])

    def test_related_resource_sections_remain_omitted(self):
        self.assertIn("Associated Actors", self.fixture.skipped_sections)
        self.assertIn("Location Data", self.fixture.skipped_sections)
        for tile in self.fixture.tiles:
            for node_id, value in tile.data.items():
                datatype = models.Node.objects.get(pk=node_id).datatype
                if datatype not in ("string", "number", "concept"):
                    self.assertIsNone(value)
        self.assertEqual(
            models.ResourceInstance.objects.filter(
                graph_id=self.monument_graph_id
            ).count(),
            1,
        )

    def test_used_concept_values_and_collection_memberships_are_loaded(self):
        entry = next(iter(json.loads(self.resource_source.read_text()).values()))
        tiles = {str(tile.pk): tile for tile in self.fixture.tiles}
        value_ids = set()
        collection_ids = set()
        for section in SIMPLE_SECTIONS:
            for node_object in _node_objects(entry["resource"][section]):
                node_id = node_object["@node_id"]
                node = models.Node.objects.get(pk=node_id)
                if node.datatype != "concept":
                    continue
                value_id = node_object.get("valueid")
                self.assertEqual(tiles[node_object["@tile_id"]].data[node_id], value_id)
                if value_id is None:
                    continue
                with self.subTest(node=node.name, value=value_id):
                    value = models.Value.objects.get(pk=value_id)
                    self.assertEqual(str(value.concept_id), node_object["concept_id"])
                    self.assertEqual(value.value, node_object["value"])
                    self.assertEqual(value.language_id, node_object["language_id"])
                    self.assertEqual(value.valuetype_id, node_object["valuetype_id"])
                    self.assertEqual(ConceptDataType().validate(value_id), [])
                    collection_id = node.config["rdmCollection"]
                    collection = models.Concept.objects.get(pk=collection_id)
                    self.assertEqual(collection.nodetype_id, "Collection")
                    member_values = {
                        member[2]
                        for member in Concept().get_child_collections(collection_id)
                    }
                    self.assertIn(value_id, member_values)
                value_ids.add(value_id)
                collection_ids.add(collection_id)
        self.assertEqual(len(value_ids), 11)
        self.assertEqual(len(collection_ids), 5)

    def test_service_reads_simple_names_from_fixture(self):
        result = DisplayDescriptorService().get_resource_data(
            resource_id=str(self.fixture.resource.pk),
            config_data=self.descriptor_config,
            strict_sortorder=True,
        )
        entry = next(iter(json.loads(self.resource_source.read_text()).values()))
        self.assertEqual(
            result,
            {
                "Monument Name": [
                    {
                        "value": record["Monument Name"]["@display_value"],
                        "Monument Name Use Type": record["Monument Name Use Type"].get(
                            "value"
                        ),
                    }
                    for record in entry["resource"]["Monument Names"]
                ],
                "Primary Reference Number": 149652,
            },
        )

    def test_installed_function_generates_and_persists_name(self):
        assignment = models.FunctionXGraph.objects.get(
            graph_id=self.monument_graph_id,
            function__functiontype="primarydescriptors",
        )
        self.assertEqual(str(assignment.function_id), details["functionid"])
        resource = Resource.objects.get(pk=self.fixture.resource.pk)
        resource.save_descriptors(descriptors=("name",))
        expected = "[149652] St Bernard's Hospital (Georgian Psychiatric Hospital)"
        self.assertEqual(resource.descriptors["en"]["name"], expected)
        saved_resource = models.ResourceInstance.objects.get(pk=resource.pk)
        self.assertEqual(saved_resource.descriptors["en"]["name"], expected)
        self.assertEqual(saved_resource.name["en"], expected)

    def test_function_selects_primary_name_even_when_not_first(self):
        names = models.TileModel.objects.filter(
            resourceinstance=self.fixture.resource,
            nodegroup_id=models.Node.objects.get(pk=NAME_NODE_ID).nodegroup_id,
        ).order_by("sortorder")
        first_primary = names.first()
        self.assertEqual(first_primary.data[NAME_USE_NODE_ID], PRIMARY_VALUE_ID)
        first_primary.sortorder = 20
        first_primary.save()
        primary_tiles = [
            tile for tile in names if tile.data[NAME_USE_NODE_ID] == PRIMARY_VALUE_ID
        ]
        self.assertEqual(len(primary_tiles), 2)
        resource = Resource.objects.get(pk=self.fixture.resource.pk)
        resource.save_descriptors(descriptors=("name",))
        self.assertEqual(
            resource.descriptors["en"]["name"],
            "[149652] St Bernard's Hospital, Southall (Georgian Psychiatric Hospital)",
        )

    def test_function_falls_back_to_first_name_without_primary(self):
        for tile in self.fixture.tiles:
            if tile.data.get(NAME_USE_NODE_ID) == PRIMARY_VALUE_ID:
                tile.data[NAME_USE_NODE_ID] = None
                tile.save()
        resource = Resource.objects.get(pk=self.fixture.resource.pk)
        resource.save_descriptors(descriptors=("name",))
        self.assertEqual(
            resource.descriptors["en"]["name"],
            "[149652] St Bernard's Hospital (Georgian Psychiatric Hospital)",
        )

    def test_third_rule_wins_after_two_required_subfield_filters_fail(self):
        config = deepcopy(self.descriptor_config)
        config["display_descriptor_rules"] = [
            {
                "rule": [
                    {
                        "name": "Monument Name",
                        "required": True,
                        "field_filters": {"NameUse": [use_type]},
                        "operations": ["first"],
                    },
                    {
                        "name": "NameUse",
                        "required": True,
                        "operations": ["uppercase"],
                    },
                ],
                "format": f"Rule {index}: {{Monument Name}} ({{NameUse}})",
            }
            for index, use_type in enumerate(
                ("Registered", "Original", "Primary"), start=1
            )
        ]
        service = DisplayDescriptorService()
        self.assertEqual(len(config["display_descriptor_rules"]), 3)
        for index in range(2):
            with self.subTest(failing_rule=index + 1):
                isolated_config = deepcopy(config)
                isolated_config["display_descriptor_rules"] = [
                    config["display_descriptor_rules"][index]
                ]
                self.assertIsNone(
                    service.render_for_resource(
                        resource_id=str(self.fixture.resource.pk),
                        config_data=isolated_config,
                        strict_sortorder=True,
                    )
                )

        expected = (
            "Rule 3: St Bernard's Hospital (Georgian Psychiatric Hospital) (PRIMARY)"
        )
        self.assertEqual(
            service.render_for_resource(
                resource_id=str(self.fixture.resource.pk),
                config_data=config,
                strict_sortorder=True,
            ),
            expected,
        )
        DisplayDescriptorGraphConfig.objects.filter(
            graph_id=self.monument_graph_id
        ).update(yaml_config=json.dumps(config))
        resource = Resource.objects.get(pk=self.fixture.resource.pk)
        resource.save_descriptors(descriptors=("name",))
        saved_resource = models.ResourceInstance.objects.get(pk=resource.pk)
        self.assertEqual(saved_resource.descriptors["en"]["name"], expected)
        self.assertEqual(saved_resource.name["en"], expected)

    def test_catch_all_format_wins_when_all_subfield_rules_fail(self):
        config = deepcopy(self.descriptor_config)
        config["display_descriptor_rules"] = [
            {
                "rule": [
                    {
                        "name": "Monument Name",
                        "required": True,
                        "field_filters": {"NameUse": [use_type]},
                        "operations": ["first"],
                    }
                ],
                "format": f"Rule {index}: {{Monument Name}} ({{NameUse}})",
            }
            for index, use_type in enumerate(
                ("Registered", "Original", "Latest"), start=1
            )
        ]
        service = DisplayDescriptorService()
        for index, block in enumerate(config["display_descriptor_rules"], start=1):
            with self.subTest(failing_rule=index):
                isolated_config = deepcopy(config)
                isolated_config["display_descriptor_rules"] = [block]
                self.assertIsNone(
                    service.render_for_resource(
                        resource_id=str(self.fixture.resource.pk),
                        config_data=isolated_config,
                        strict_sortorder=True,
                    )
                )
        self.assertIsNone(
            service.render_for_resource(
                resource_id=str(self.fixture.resource.pk),
                config_data=config,
                strict_sortorder=True,
            )
        )

        expected = "Monument: no matching name use type"
        config["display_descriptor_rules"].append({"rule": [], "format": expected})
        self.assertEqual(
            service.render_for_resource(
                resource_id=str(self.fixture.resource.pk),
                config_data=config,
                strict_sortorder=True,
            ),
            expected,
        )
        DisplayDescriptorGraphConfig.objects.filter(
            graph_id=self.monument_graph_id
        ).update(yaml_config=json.dumps(config))
        resource = Resource.objects.get(pk=self.fixture.resource.pk)
        resource.save_descriptors(descriptors=("name",))
        saved_resource = models.ResourceInstance.objects.get(pk=resource.pk)
        self.assertEqual(saved_resource.descriptors["en"]["name"], expected)
        self.assertEqual(saved_resource.name["en"], expected)

    def test_description_priority_resolves_summary_full_then_first(self):
        entry = next(iter(json.loads(self.resource_source.read_text()).values()))
        descriptions = entry["resource"]["Descriptions"]
        config = {
            "fields": [
                {
                    "name": "Description",
                    "subfields": [{"name": "Description Type", "alias": "UseType"}],
                }
            ],
            "display_descriptor_rules": [
                {
                    "rule": [
                        {
                            "name": "Description",
                            "field_filters": {"UseType": ["Summary|Full|FIRST"]},
                            "operations": ["first"],
                        }
                    ],
                    "format": "{Description}",
                }
            ],
        }
        for expected_index, remove_type in (
            (0, None),
            (2, "Summary"),
            (1, "Full"),
        ):
            with self.subTest(expected_index=expected_index):
                if remove_type is not None:
                    value_id = next(
                        record["Description Type"]["valueid"]
                        for record in descriptions
                        if record["Description Type"].get("value") == remove_type
                    )
                    models.TileModel.objects.filter(
                        resourceinstance=self.fixture.resource,
                        **{f"data__{DESCRIPTION_TYPE_NODE_ID}": value_id},
                    ).delete()
                result = DisplayDescriptorService().render_for_resource(
                    resource_id=str(self.fixture.resource.pk),
                    config_data=config,
                    strict_sortorder=True,
                )
                self.assertEqual(
                    result,
                    descriptions[expected_index]["Description"]["@display_value"],
                )

    def test_missing_concept_value_is_rejected_before_resource_creation(self):
        models.Value.objects.filter(pk=PRIMARY_VALUE_ID).delete()
        count = models.ResourceInstance.objects.count()
        with self.assertRaisesRegex(
            ValueError, "Missing or mismatched.*" + PRIMARY_VALUE_ID
        ):
            create_monument_resource(self.resource_source, self.graph_definition)
        self.assertEqual(models.ResourceInstance.objects.count(), count)

    def test_mismatched_concept_label_is_rejected(self):
        models.Value.objects.filter(pk=PRIMARY_VALUE_ID).update(value="Wrong label")
        with self.assertRaisesRegex(ValueError, "Missing or mismatched"):
            create_monument_resource(self.resource_source, self.graph_definition)

    def test_missing_collection_membership_is_rejected(self):
        models.Relation.objects.filter(
            conceptto_id=models.Value.objects.get(pk=PRIMARY_VALUE_ID).concept_id,
            relationtype_id="member",
        ).delete()
        with self.assertRaisesRegex(ValueError, "must belong"):
            create_monument_resource(self.resource_source, self.graph_definition)

    def test_unpublished_graph_is_rejected(self):
        models.GraphModel.objects.filter(pk=self.monument_graph_id).update(
            publication=None
        )
        with self.assertRaisesRegex(ValueError, "must be published"):
            create_monument_resource(self.resource_source, self.graph_definition)

    def test_wrong_graph_is_rejected_without_creating_resources(self):
        graph = deepcopy(self.graph_definition)
        graph["graphid"] = "00000000-0000-0000-0000-000000000000"
        count = models.ResourceInstance.objects.count()
        with self.assertRaisesRegex(ValueError, "does not match"):
            create_monument_resource(self.resource_source, graph)
        self.assertEqual(models.ResourceInstance.objects.count(), count)

    def test_duplicate_load_does_not_overwrite_existing_resource(self):
        with self.assertRaises(IntegrityError):
            create_monument_resource(self.resource_source, self.graph_definition)
        self.assertEqual(
            models.TileModel.objects.filter(
                resourceinstance=self.fixture.resource
            ).count(),
            18,
        )

    def test_tile_failure_rolls_back_resource_creation(self):
        self.fixture.resource.delete()
        with patch.object(
            models.TileModel.objects, "create", side_effect=ValueError("tile failure")
        ):
            with self.assertRaisesRegex(ValueError, "tile failure"):
                create_monument_resource(self.resource_source, self.graph_definition)
        self.assertFalse(
            models.ResourceInstance.objects.filter(
                pk="f5ab4bd6-43d4-4940-b856-fa6f93c98d4c"
            ).exists()
        )
