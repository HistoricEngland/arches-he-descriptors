import json
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import captured_stdout

from arches.app.models import models
from arches.app.models.graph import Graph
from arches.app.utils.data_management.resource_graphs.importer import import_graph

from arches_he_descriptors.functions.arches_he_descriptors import details
from tests.function_tests.graph_fixture import prepare_descriptor_graph


class BaseDescriptorTestCase(TestCase):
    monument_graph_id = "076f9381-7b00-11e9-8d6b-80000b44d1d9"
    cidoc_crm_ontology_id = "e6e8db47-2ccf-11e6-927e-b8f6b115d7dd"

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.get(username="admin")
        project_root = Path(__file__).resolve().parents[2]
        fixtures_root = project_root / "tests" / "fixtures" / "pkg"
        cls.graph_source = (
            project_root / "arches_he_descriptors" / "tests" / "fixtures" / "pkg" / "graphs" / "resource_models" / "Monument.json"
        )

        descriptor_function_source = project_root / "arches_he_descriptors" / "functions" / "arches_he_descriptors.py"
        with captured_stdout():
            call_command("fn", "register", source=str(descriptor_function_source))
        cls.descriptor_function = models.Function.objects.get(functionid=details["functionid"])

        ontology_source = fixtures_root / "ontologies" / "cidoc_crm"
        with captured_stdout():
            call_command("load_ontology", source=str(ontology_source), verbosity=0)

        cls.concept_source = fixtures_root / "reference_data" / "st_bernards_concepts.json"
        call_command("loaddata", str(cls.concept_source), verbosity=0)

        widget_source = fixtures_root / "widgets" / "photo-widget.json"
        with captured_stdout():
            call_command("widget", "register", source=str(widget_source))

        source_definition = json.loads(cls.graph_source.read_text())["graph"][0]
        cls.graph_definition = prepare_descriptor_graph(source_definition, details)
        with captured_stdout():
            import_graph([cls.graph_definition], user=cls.admin)

        graph = Graph.objects.get(graphid=cls.monument_graph_id)
        cls.descriptor_assignment = models.FunctionXGraph.objects.get(graph=graph, function__functiontype="primarydescriptors")
        graph.publish(user=cls.admin)
