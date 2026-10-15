import json
from copy import deepcopy
from pathlib import Path
from unittest import TestCase

from tests.function_tests.graph_fixture import (
    EXCLUDED_FUNCTION_IDS,
    EXCLUDED_NODEGROUP_ID,
    prepare_descriptor_graph,
)


class DescriptorGraphFixtureTests(TestCase):
    def setUp(self):
        project_root = Path(__file__).resolve().parents[2]
        source = project_root / "arches_he_descriptors/tests/fixtures/pkg/graphs/resource_models/Monument.json"
        self.source = json.loads(source.read_text())["graph"][0]
        self.details = {
            "functionid": "60000000-0000-0000-0000-000000000003",
            "defaultconfig": {
                "module": "arches_he_descriptors.functions.arches_he_descriptors",
                "class_name": "ArchesHEDescriptors",
                "descriptor_types": {
                    "name": {"show_prn": False},
                    "description": {},
                    "map_popup": {},
                },
                "triggering_nodegroups": [],
            },
        }

    def test_translatable_fields_are_language_keyed(self):
        graph = prepare_descriptor_graph(self.source, self.details)

        for field in ("name", "description", "subtitle"):
            self.assertEqual(graph[field], {"en": self.source[field]})
        for card in graph["cards"]:
            original = next(item for item in self.source["cards"] if item["cardid"] == card["cardid"])
            for field in (
                "name",
                "description",
                "instructions",
                "helptitle",
                "helptext",
            ):
                if isinstance(original.get(field), str):
                    self.assertEqual(card[field], {"en": original[field]})
                else:
                    self.assertEqual(card.get(field), original.get(field))
        for widget in graph["cards_x_nodes_x_widgets"]:
            self.assertIsInstance(widget["label"], dict)
            self.assertIn("en", widget["label"])
        self.assertTrue(all(isinstance(node["name"], str) for node in graph["nodes"]))

    def test_existing_translations_and_source_are_preserved(self):
        self.source["name"] = {"en": "Monument", "fr": "Monument historique"}
        self.source["cards"][0]["name"] = {"en": "Actors", "fr": "Acteurs"}
        self.source["cards_x_nodes_x_widgets"][0]["label"] = {
            "en": "Related",
            "fr": "Lie",
        }
        original = deepcopy(self.source)

        graph = prepare_descriptor_graph(self.source, self.details)

        self.assertEqual(self.source, original)
        self.assertEqual(graph["name"], original["name"])
        self.assertEqual(graph["cards"][0]["name"], original["cards"][0]["name"])
        self.assertEqual(
            graph["cards_x_nodes_x_widgets"][0]["label"],
            original["cards_x_nodes_x_widgets"][0]["label"],
        )
        self.assertEqual(prepare_descriptor_graph(original, self.details), graph)

    def test_reduced_graph_has_no_dangling_structural_references(self):
        graph = prepare_descriptor_graph(self.source, self.details)
        nodes = {node["nodeid"] for node in graph["nodes"]}
        groups = {group["nodegroupid"] for group in graph["nodegroups"]}
        cards = {card["cardid"] for card in graph["cards"]}

        self.assertNotIn(EXCLUDED_NODEGROUP_ID, groups)
        self.assertNotIn("bngcentrepoint", {node["datatype"] for node in graph["nodes"]})
        self.assertEqual(graph["template_id"], "50000000-0000-0000-0000-000000000001")
        self.assertEqual(graph["config"], {})
        self.assertEqual(len(self.source["nodes"]) - len(nodes), 2)
        for edge in graph["edges"]:
            self.assertIn(edge["domainnode_id"], nodes)
            self.assertIn(edge["rangenode_id"], nodes)
        for node in graph["nodes"]:
            if node["nodegroup_id"] is not None:
                self.assertIn(node["nodegroup_id"], groups)
        for group in graph["nodegroups"]:
            if group["parentnodegroup_id"] is not None:
                self.assertIn(group["parentnodegroup_id"], groups)
        for card in graph["cards"]:
            self.assertIn(card["nodegroup_id"], groups)
        for widget in graph["cards_x_nodes_x_widgets"]:
            self.assertIn(widget["node_id"], nodes)
            self.assertIn(widget["card_id"], cards)

    def test_source_functions_are_replaced_with_he_descriptors(self):
        graph = prepare_descriptor_graph(self.source, self.details)
        self.assertEqual(len(graph["functions_x_graphs"]), 1)
        assignment = graph["functions_x_graphs"][0]
        self.assertEqual(assignment["function_id"], self.details["functionid"])
        self.assertEqual(assignment["config"]["module"], self.details["defaultconfig"]["module"])
        self.assertEqual(
            assignment["config"]["class_name"],
            self.details["defaultconfig"]["class_name"],
        )
        self.assertTrue(assignment["config"]["descriptor_types"]["name"]["show_prn"])
        self.assertEqual(
            assignment["config"]["descriptor_types"],
            self.source["functions_x_graphs"][0]["config"]["descriptor_types"],
        )

    def test_unexpected_dependencies_are_reported(self):
        self.source["functions_x_graphs"].append({"function_id": "unexpected", "config": {}})
        with self.assertRaisesRegex(ValueError, "Unexpected source graph functions"):
            prepare_descriptor_graph(self.source, self.details)

    def test_missing_descriptor_assignment_is_reported(self):
        self.source["functions_x_graphs"] = [
            assignment for assignment in self.source["functions_x_graphs"] if assignment["function_id"] in EXCLUDED_FUNCTION_IDS
        ]
        with self.assertRaisesRegex(ValueError, "exactly one descriptor assignment"):
            prepare_descriptor_graph(self.source, self.details)

    def test_unexpected_spatial_child_group_is_reported(self):
        self.source["nodegroups"].append({"nodegroupid": "unexpected", "parentnodegroup_id": EXCLUDED_NODEGROUP_ID})
        with self.assertRaisesRegex(ValueError, "unexpectedly has child nodegroups"):
            prepare_descriptor_graph(self.source, self.details)
