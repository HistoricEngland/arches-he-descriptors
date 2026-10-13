import json

from arches.app.models import models
from arches.app.models.graph import Graph

from arches_he_descriptors.functions.arches_he_descriptors import details
from tests.function_tests.base_test import BaseDescriptorTestCase
from tests.function_tests.graph_fixture import SOURCE_DESCRIPTOR_FUNCTION_ID


class MonumentGraphSetupTests(BaseDescriptorTestCase):
    def test_monument_graph_is_available(self):
        self.assertTrue(
            models.Ontology.objects.filter(
                ontologyid=self.cidoc_crm_ontology_id
            ).exists()
        )

        graph_definition = self.graph_definition
        required_widget_ids = {
            widget["widget_id"]
            for widget in graph_definition["cards_x_nodes_x_widgets"]
        }
        registered_widget_ids = {
            str(widget_id)
            for widget_id in models.Widget.objects.filter(
                widgetid__in=required_widget_ids
            ).values_list("widgetid", flat=True)
        }
        self.assertSetEqual(
            required_widget_ids,
            registered_widget_ids,
            "The Monument graph fixture references unregistered widgets.",
        )

        graph = Graph.objects.get(graphid=self.monument_graph_id)

        self.assertEqual(graph.name["en"], "Monument")
        self.assertEqual(graph.description["en"], graph_definition["description"]["en"])
        self.assertEqual(graph.subtitle["en"], graph_definition["subtitle"]["en"])
        self.assertEqual(
            models.CardXNodeXWidget.objects.filter(
                card__graph_id=self.monument_graph_id
            ).count(),
            len(graph_definition["cards_x_nodes_x_widgets"]),
        )

        for card_definition in graph_definition["cards"]:
            with self.subTest(card_id=card_definition["cardid"]):
                card = models.CardModel.objects.get(pk=card_definition["cardid"])
                self.assertEqual(card.name["en"], card_definition["name"]["en"])
        for widget_definition in graph_definition["cards_x_nodes_x_widgets"]:
            with self.subTest(widget_id=widget_definition["id"]):
                widget = models.CardXNodeXWidget.objects.get(pk=widget_definition["id"])
                self.assertEqual(widget.label["en"], widget_definition["label"]["en"])

    def test_he_descriptor_function_is_registered(self):
        function = models.Function.objects.get(functionid=details["functionid"])

        self.assertEqual(function.name, "Arches HE Descriptors")
        self.assertEqual(function.functiontype, "primarydescriptors")
        self.assertEqual(function.modulename, details["modulename"])
        self.assertEqual(function.classname, details["classname"])
        self.assertEqual(function.component, details["component"])

    def test_monument_uses_he_descriptor_function(self):
        assignments = models.FunctionXGraph.objects.filter(
            graph_id=self.monument_graph_id,
            function__functiontype="primarydescriptors",
        )
        self.assertEqual(assignments.count(), 1)
        assignment = assignments.get()
        self.assertEqual(str(assignment.function_id), details["functionid"])
        self.assertTrue(assignment.config["descriptor_types"]["name"]["show_prn"])
        self.assertEqual(
            assignment.config["module"], details["defaultconfig"]["module"]
        )
        self.assertEqual(
            assignment.config["class_name"], details["defaultconfig"]["class_name"]
        )

        graph_definition = json.loads(self.graph_source.read_text())["graph"][0]
        original_config = next(
            function["config"]
            for function in graph_definition["functions_x_graphs"]
            if function["function_id"] == SOURCE_DESCRIPTOR_FUNCTION_ID
        )
        for descriptor, original_descriptor in original_config[
            "descriptor_types"
        ].items():
            with self.subTest(descriptor=descriptor):
                for key, value in original_descriptor.items():
                    self.assertEqual(
                        assignment.config["descriptor_types"][descriptor][key], value
                    )
        self.assertEqual(
            assignment.config["triggering_nodegroups"],
            original_config["triggering_nodegroups"],
        )
        self.assertEqual(
            models.FunctionXGraph.objects.filter(
                graph_id=self.monument_graph_id
            ).count(),
            1,
        )
