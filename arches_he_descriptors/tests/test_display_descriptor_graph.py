import json
import uuid

from arches.app.models import models
from arches.app.models.resource import Resource
from tests.base_test import ArchesTestCase

from arches_he_descriptors.functions.arches_he_descriptors import details
from arches_he_descriptors.models import DisplayDescriptorGraphConfig
from arches_he_descriptors.display_descriptor.service import (
    DisplayDescriptorService,
)


GRAPH_ID = uuid.UUID("c9b37a14-17b3-11eb-a708-acde48001122")
NAME_NODEGROUP_ID = uuid.UUID("c9b37b7c-17b3-11eb-a708-acde48001122")
NAME_NODE_ID = uuid.UUID("c9b37b7c-17b3-11eb-a708-acde48001122")


class DisplayDescriptorGraphTests(ArchesTestCase):
    graph_fixtures = ["Resource Test Model"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.graph = models.GraphModel.objects.get(pk=GRAPH_ID)
        cls.function, _ = models.Function.objects.update_or_create(
            functionid=uuid.UUID(details["functionid"]),
            defaults={
                "name": details["name"],
                "functiontype": details["type"],
                "description": details["description"],
                "defaultconfig": details["defaultconfig"],
                "modulename": details["modulename"],
                "classname": details["classname"],
                "component": details["component"],
            },
        )
        function_config = json.loads(json.dumps(details["defaultconfig"]))
        function_config["descriptor_types"]["name"]["show_prn"] = True
        cls.function_x_graph, _ = models.FunctionXGraph.objects.update_or_create(
            graph=cls.graph,
            function=cls.function,
            defaults={"config": function_config},
        )

        cls.resource_instance = models.ResourceInstance.objects.create(graph=cls.graph)
        models.TileModel.objects.create(
            nodegroup_id=NAME_NODEGROUP_ID,
            resourceinstance=cls.resource_instance,
            data={
                str(NAME_NODE_ID): {
                    "en": {"value": "  old chapel ", "direction": "ltr"}
                }
            },
            sortorder=0,
        )
        models.TileModel.objects.create(
            nodegroup_id=NAME_NODEGROUP_ID,
            resourceinstance=cls.resource_instance,
            data={
                str(NAME_NODE_ID): {"en": {"value": "new chapel", "direction": "ltr"}}
            },
            sortorder=1,
        )
        DisplayDescriptorGraphConfig.objects.update_or_create(
            graph_id=GRAPH_ID,
            defaults={
                "yaml_config": json.dumps(
                    {
                        "fields": [{"name": "Name"}],
                        "display_descriptor_rules": [
                            {
                                "rule": [
                                    {
                                        "name": "Name",
                                        "operations": ["first", "trim", "titlecase"],
                                    }
                                ],
                                "format": "Historic site: {Name}",
                            }
                        ],
                    }
                )
            },
        )

    def test_attached_function_renders_descriptor_from_resource_tiles(self):
        self.assertTrue(
            models.FunctionXGraph.objects.filter(
                graph=self.graph,
                function=self.function,
                config__descriptor_types__name__show_prn=True,
            ).exists()
        )

        resource = Resource.objects.get(pk=self.resource_instance.pk)
        resource.save_descriptors(descriptors=("name",))

        self.assertEqual(
            resource.descriptors["en"]["name"],
            "Historic site: Old Chapel",
        )

    def test_strict_sortorder_rejects_tile_without_sortorder(self):
        tile = models.TileModel.objects.create(
            nodegroup_id=NAME_NODEGROUP_ID,
            resourceinstance=self.resource_instance,
            data={
                str(NAME_NODE_ID): {
                    "en": {"value": "unsorted chapel", "direction": "ltr"}
                }
            },
            sortorder=2,
        )
        models.TileModel.objects.filter(pk=tile.pk).update(sortorder=None)

        with self.assertRaisesRegex(ValueError, "all tiles must have sortorder set"):
            DisplayDescriptorService().get_resource_data(
                resource_id=str(self.resource_instance.pk),
                strict_sortorder=True,
            )

    def test_inline_config_rejects_field_missing_from_resource_graph(self):
        with self.assertRaisesRegex(ValueError, "missing from graph"):
            DisplayDescriptorService().get_resource_data(
                resource_id=str(self.resource_instance.pk),
                config_data={
                    "fields": ["Unknown field"],
                    "display_descriptor_rules": [
                        {
                            "rule": [{"name": "Unknown field"}],
                            "format": "{Unknown field}",
                        }
                    ],
                },
            )
