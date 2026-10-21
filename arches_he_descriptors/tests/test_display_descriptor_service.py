import json

from django.test import SimpleTestCase

from arches_he_descriptors.display_descriptor.service import DisplayDescriptorService


class DisplayDescriptorServiceTests(SimpleTestCase):
    def setUp(self):
        self.service = DisplayDescriptorService()

    def test_load_config_from_yaml_normalizes_fields_filters_and_operations(self):
        config = self.service.load_config_from_yaml(
            """
fields:
  - name: Monument Name
    alias: Name
    subfields:
      - name: Name Use Type
        alias: Use Type
display_descriptor_rules:
  - rule:
      - name: Name
        field_filters:
          Use Type: Primary|Original
        operations:
          - type: titlecase
    format: "{Name}"
"""
        )

        self.assertEqual(config.fields[0].name, "Name")
        self.assertEqual(config.fields[0].graph_name, "Monument Name")
        self.assertEqual(config.fields[0].subfields[0].name, "Name Use Type")
        self.assertEqual(config.fields[0].subfields[0].alias, "Use Type")
        self.assertEqual(
            config.display_descriptor_rules[0].rule[0].field_filters,
            {"Use Type": ["Primary|Original"]},
        )
        self.assertEqual(
            config.display_descriptor_rules[0].rule[0].operations[0].type,
            "titlecase",
        )

    def test_load_config_from_json_accepts_string_fields(self):
        config = self.service.load_config_from_json(
            json.dumps(
                {
                    "fields": ["Name"],
                    "display_descriptor_rules": [
                        {
                            "rule": [{"name": "Name"}],
                            "format": "Place: {Name}",
                        }
                    ],
                }
            )
        )

        self.assertEqual(config.fields[0].name, "Name")
        self.assertEqual(config.fields[0].graph_name, "Name")

    def test_load_config_from_dict_and_render_with_inline_config(self):
        config_data = {
            "fields": ["Name"],
            "display_descriptor_rules": [
                {
                    "rule": [{"name": "Name", "operations": ["titlecase"]}],
                    "format": "Site: {Name}",
                }
            ],
        }

        config = self.service.load_config_from_dict(config_data)
        result = self.service.render_with_config({"Name": "old chapel"}, config_data)

        self.assertEqual(config.display_descriptor_rules[0].format, "Site: {Name}")
        self.assertEqual(result, "Site: Old Chapel")

    def test_invalid_yaml_and_json_are_reported(self):
        with self.assertRaisesRegex(ValueError, "Invalid YAML"):
            self.service.load_config_from_yaml("fields: [")

        with self.assertRaisesRegex(ValueError, "Invalid JSON"):
            self.service.load_config_from_json("{")

    def test_config_must_deserialize_to_object(self):
        with self.assertRaisesRegex(ValueError, "must deserialize to an object"):
            self.service.load_config_from_yaml("- Name")

    def test_unknown_operation_is_rejected_while_loading_config(self):
        with self.assertRaisesRegex(ValueError, "Invalid operation type: 'not-real'"):
            self.service.load_config_from_dict(
                {
                    "display_descriptor_rules": [
                        {
                            "rule": [
                                {
                                    "name": "Name",
                                    "operations": ["not-real"],
                                }
                            ],
                            "format": "{Name}",
                        }
                    ]
                }
            )
