from django.test import SimpleTestCase

from arches_he_descriptors.display_descriptor.engine import DisplayDescriptorEngine
from arches_he_descriptors.display_descriptor.schema import (
    DisplayDescriptorConfig,
    DisplayDescriptorRuleBlock,
    FieldDefinition,
    Operation,
    RuleDefinition,
    SubfieldDefinition,
)


class DisplayDescriptorEngineTests(SimpleTestCase):
    def test_required_rule_falls_through_to_next_rule_block(self):
        config = DisplayDescriptorConfig(
            fields=[],
            display_descriptor_rules=[
                DisplayDescriptorRuleBlock(
                    rule=[RuleDefinition(name="Name", required=True)],
                    format="{Name}",
                ),
                DisplayDescriptorRuleBlock(
                    rule=[RuleDefinition(name="Name", default="Unrecorded")],
                    format="Site: {Name}",
                    format_operations=[Operation(type="uppercase")],
                ),
            ],
        )

        result = DisplayDescriptorEngine(config).render({})

        self.assertEqual(result, "SITE: UNRECORDED")

    def test_rule_formats_present_and_default_values_differently(self):
        rule = RuleDefinition(
            name="Name",
            default="Unrecorded",
            format_when_present="{Name}",
            format_when_default="{Name} (unknown)",
        )
        block = DisplayDescriptorRuleBlock(rule=[rule], format="Name: {Name}")

        self.assertEqual(
            DisplayDescriptorEngine(DisplayDescriptorConfig(fields=[], display_descriptor_rules=[block])).render({}),
            "Name: Unrecorded (unknown)",
        )
        self.assertEqual(
            DisplayDescriptorEngine(DisplayDescriptorConfig(fields=[], display_descriptor_rules=[block])).render({"Name": "St Mary's"}),
            "Name: St Mary's",
        )

    def test_priority_filter_supports_subfield_aliases(self):
        fields = [
            FieldDefinition(
                name="Place",
                subfields=[SubfieldDefinition(name="Use Type", alias="Type")],
            )
        ]
        config = DisplayDescriptorConfig(
            fields=fields,
            display_descriptor_rules=[
                DisplayDescriptorRuleBlock(
                    rule=[
                        RuleDefinition(
                            name="Place",
                            field_filters={"Type": ["Primary|Original|FIRST"]},
                            operations=[Operation(type="titlecase")],
                        )
                    ],
                    format="{Place} ({Type})",
                )
            ],
        )
        result = DisplayDescriptorEngine(config).render(
            {
                "Place": [
                    {"value": "secondary chapel", "Use Type": "Original"},
                    {"value": "main chapel", "Use Type": "Primary"},
                    {"value": "other chapel", "Use Type": "Primary"},
                ]
            }
        )
        self.assertEqual(result, "Main Chapel (Primary)")

    def test_subfield_alias_can_be_referenced_as_a_rule(self):
        fields = [
            FieldDefinition(
                name="Place",
                subfields=[SubfieldDefinition(name="Use Type", alias="Type")],
            )
        ]
        config = DisplayDescriptorConfig(
            fields=fields,
            display_descriptor_rules=[
                DisplayDescriptorRuleBlock(
                    rule=[RuleDefinition(name="Type", operations=[Operation(type="uppercase")])],
                    format="{Type}",
                )
            ],
        )
        result = DisplayDescriptorEngine(config).render({"Place": [{"value": "main chapel", "Use Type": "Primary"}]})
        self.assertEqual(result, "PRIMARY")

    def test_missing_format_field_skips_block(self):
        config = DisplayDescriptorConfig(
            fields=[],
            display_descriptor_rules=[
                DisplayDescriptorRuleBlock(rule=[], format="{Missing}"),
                DisplayDescriptorRuleBlock(rule=[RuleDefinition(name="Name")], format="Name: {Name}"),
            ],
        )
        self.assertEqual(
            DisplayDescriptorEngine(config).render({"Name": "Old Chapel"}),
            "Name: Old Chapel",
        )

    def test_render_returns_none_when_no_rule_block_can_render(self):
        config = DisplayDescriptorConfig(
            fields=[],
            display_descriptor_rules=[DisplayDescriptorRuleBlock(rule=[], format="{Missing}")],
        )
        self.assertIsNone(DisplayDescriptorEngine(config).render({}))

    def test_missing_values_use_default_or_fail_required_rule(self):
        for value in (None, "", " \t\n", [], {"value": ""}, {"value": None}):
            for default in (None, "Unrecorded"):
                with self.subTest(value=value, default=default):
                    config = DisplayDescriptorConfig(
                        fields=[],
                        display_descriptor_rules=[
                            DisplayDescriptorRuleBlock(
                                rule=[RuleDefinition(name="Name", required=True, default=default)],
                                format="Name: {Name}",
                            ),
                            DisplayDescriptorRuleBlock(rule=[], format="Catch-all"),
                        ],
                    )
                    self.assertEqual(
                        DisplayDescriptorEngine(config).render({"Name": value}),
                        "Catch-all" if default is None else "Name: Unrecorded",
                    )

    def test_zero_and_false_are_not_missing_values(self):
        config = DisplayDescriptorConfig(
            fields=[],
            display_descriptor_rules=[
                DisplayDescriptorRuleBlock(
                    rule=[RuleDefinition(name="Value", required=True, default="Unknown")],
                    format="{Value}",
                )
            ],
        )
        for value, expected in ((0, "0"), (False, "False")):
            with self.subTest(value=value):
                self.assertEqual(DisplayDescriptorEngine(config).render({"Value": value}), expected)

    def test_blank_value_uses_explicit_empty_default_format(self):
        config = DisplayDescriptorConfig(
            fields=[],
            display_descriptor_rules=[
                DisplayDescriptorRuleBlock(
                    rule=[
                        RuleDefinition(
                            name="Name",
                            format_when_present="Present: {Name}",
                            format_when_default="",
                        )
                    ],
                    format="Site[{Name}]",
                )
            ],
        )
        for value in (None, "", " \t", []):
            with self.subTest(value=value):
                self.assertEqual(DisplayDescriptorEngine(config).render({"Name": value}), "Site[]")

    def test_subfield_agreement_and_ambiguity_control_formatting(self):
        fields = [
            FieldDefinition(
                name="Place",
                subfields=[SubfieldDefinition(name="Use Type", alias="Type")],
            )
        ]
        for second_type, expected in (
            ("Primary", "one / two (Type: PRIMARY)"),
            ("Alternative", "one / two (ambiguous)"),
        ):
            with self.subTest(second_type=second_type):
                config = DisplayDescriptorConfig(
                    fields=fields,
                    display_descriptor_rules=[
                        DisplayDescriptorRuleBlock(
                            rule=[
                                RuleDefinition(
                                    name="Place",
                                    operations=[Operation(type="combine", separator=" / ")],
                                ),
                                RuleDefinition(
                                    name="Type",
                                    operations=[Operation(type="uppercase")],
                                    format_when_present="Type: {Type}",
                                    format_when_default="ambiguous",
                                ),
                            ],
                            format="{Place} ({Type})",
                        )
                    ],
                )
                resource = {
                    "Place": [
                        {"value": "one", "Use Type": "Primary"},
                        {"value": "two", "Use Type": second_type},
                    ]
                }
                self.assertEqual(DisplayDescriptorEngine(config).render(resource), expected)

    def test_required_ambiguous_subfield_falls_through(self):
        config = DisplayDescriptorConfig(
            fields=[
                FieldDefinition(
                    name="Place",
                    subfields=[SubfieldDefinition(name="Use Type", alias="Type")],
                )
            ],
            display_descriptor_rules=[
                DisplayDescriptorRuleBlock(
                    rule=[
                        RuleDefinition(name="Place", operations=[Operation(type="combine")]),
                        RuleDefinition(name="Type", required=True),
                    ],
                    format="{Place} ({Type})",
                ),
                DisplayDescriptorRuleBlock(rule=[], format="Ambiguous use type"),
            ],
        )
        self.assertEqual(
            DisplayDescriptorEngine(config).render(
                {
                    "Place": [
                        {"value": "one", "Use Type": "Primary"},
                        {"value": "two", "Use Type": "Alternative"},
                    ]
                }
            ),
            "Ambiguous use type",
        )

    def test_priority_filters_fallback_no_match_and_no_op(self):
        fields = [
            FieldDefinition(
                name="Place",
                subfields=[SubfieldDefinition(name="Use Type", alias="Type")],
            )
        ]
        resource = {
            "Place": [
                {"value": "first", "Use Type": "Former"},
                {"value": "second", "Use Type": "Alternative"},
            ]
        }
        for priority, expected in (
            ("Primary|Alternative|FIRST", "second"),
            ("Primary|FIRST", "first"),
            ("Primary|Original", "Catch-all"),
            ("|", "first / second"),
            ("||Alternative|", "second"),
        ):
            with self.subTest(priority=priority):
                config = DisplayDescriptorConfig(
                    fields=fields,
                    display_descriptor_rules=[
                        DisplayDescriptorRuleBlock(
                            rule=[
                                RuleDefinition(
                                    name="Place",
                                    required=True,
                                    field_filters={"Type": [priority]},
                                    operations=[Operation(type="combine", separator=" / ")],
                                )
                            ],
                            format="{Place}",
                        ),
                        DisplayDescriptorRuleBlock(rule=[], format="Catch-all"),
                    ],
                )
                self.assertEqual(DisplayDescriptorEngine(config).render(resource), expected)

    def test_multiple_subfield_filters_intersect_and_preserve_matching_context(self):
        fields = [
            FieldDefinition(
                name="Place",
                subfields=[
                    SubfieldDefinition(name="Use Type", alias="Type"),
                    SubfieldDefinition(name="Currency", alias="Status"),
                ],
            )
        ]
        resource = {
            "Place": [
                {"value": "old main", "Use Type": "Primary", "Currency": "Former"},
                {"value": "other", "Use Type": "Alternative", "Currency": "Current"},
                {"value": "new main", "Use Type": "Primary", "Currency": "Current"},
            ]
        }
        for currency, expected in (
            ("Current", "New Main (PRIMARY, Current)"),
            ("Unrecorded", "Catch-all"),
        ):
            with self.subTest(currency=currency):
                config = DisplayDescriptorConfig(
                    fields=fields,
                    display_descriptor_rules=[
                        DisplayDescriptorRuleBlock(
                            rule=[
                                RuleDefinition(
                                    name="Place",
                                    required=True,
                                    field_filters={
                                        "Type": ["Primary"],
                                        "Status": [currency],
                                    },
                                    operations=[Operation(type="titlecase")],
                                ),
                                RuleDefinition(
                                    name="Type",
                                    operations=[Operation(type="uppercase")],
                                ),
                            ],
                            format="{Place} ({Type}, {Status})",
                        ),
                        DisplayDescriptorRuleBlock(rule=[], format="Catch-all"),
                    ],
                )
                self.assertEqual(DisplayDescriptorEngine(config).render(resource), expected)
