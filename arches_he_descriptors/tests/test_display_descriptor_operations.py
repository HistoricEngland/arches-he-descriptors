from django.test import SimpleTestCase

from arches_he_descriptors.display_descriptor.engine import (
    OPERATION_HANDLERS,
    OperationType,
    apply_operation_chain,
)
from arches_he_descriptors.display_descriptor.schema import (
    Operation,
)


class DisplayDescriptorOperationTests(SimpleTestCase):
    def test_supported_operations(self):
        cases = [
            (Operation(type="titlecase"), "rED fox", "Red Fox"),
            (Operation(type="uppercase"), "heritage", "HERITAGE"),
            (Operation(type="lowercase"), "HERITAGE", "heritage"),
            (Operation(type="capitalize"), "hELLO WORLD", "Hello world"),
            (Operation(type="trim"), "  name  ", "name"),
            (Operation(type="ltrim"), "  name  ", "name  "),
            (Operation(type="rtrim"), "  name  ", "  name"),
            (
                Operation(type="lpad", pad_length=3, pad_char="0"),
                7,
                "007",
            ),
            (
                Operation(type="rpad", pad_length=3, pad_char="_"),
                "x",
                "x__",
            ),
            (
                Operation(type="normalize_whitespace"),
                "  old   church\nsite ",
                "old church site",
            ),
            (
                Operation(
                    type="replace",
                    replace_from="heritage",
                    replace_to="history",
                    ignore_case=True,
                ),
                "Heritage asset",
                "history asset",
            ),
            (
                Operation(type="coalesce", coalesce_value="Unknown"),
                None,
                "Unknown",
            ),
            (
                Operation(type="fallback_text", fallback_text="Unrecorded"),
                "",
                "Unrecorded",
            ),
            (Operation(type="remove_diacritics"), "café", "cafe"),
            (Operation(type="remove_special_chars"), "a+b!", "ab"),
            (Operation(type="unique"), [2, 1, 2], [2, 1]),
            (Operation(type="sort"), ["b", "A"], ["A", "b"]),
            (Operation(type="reverse"), ["north", "south"], ["south", "north"]),
            (Operation(type="first"), ["first", "second"], "first"),
            (
                Operation(type="abbreviate", skip_words=["of"]),
                "church of england",
                "CE",
            ),
            (
                Operation(type="prefix", prefix_value="Historic "),
                "England",
                "Historic England",
            ),
            (Operation(type="suffix", suffix_value=" site"), "Listed", "Listed site"),
            (
                Operation(type="truncate", max_length=5, overflow_indicator="!"),
                "Heritage",
                "Heri!",
            ),
            (
                Operation(type="combine", separator="/"),
                ["north", "south"],
                "north/south",
            ),
        ]

        enum_values = {operation.value for operation in OperationType}
        self.assertSetEqual({operation.type for operation, _, _ in cases}, enum_values)
        self.assertEqual(len(cases), len(enum_values))
        self.assertSetEqual(set(OPERATION_HANDLERS), enum_values)
        for operation, value, expected in cases:
            with self.subTest(operation=operation.type):
                self.assertEqual(apply_operation_chain(value, [operation]), expected)

    def test_operations_can_be_chained_in_order(self):
        operations = [
            Operation(type="normalize_whitespace"),
            Operation(type="remove_diacritics"),
            Operation(type="replace", replace_from="'", replace_to=""),
            Operation(type="titlecase", preserve_acronyms=True),
            Operation(type="suffix", suffix_value="!"),
        ]

        result = apply_operation_chain("  Église d'ART   UNESCO ", operations)

        self.assertEqual(result, "Eglise Dart UNESCO!")

    def test_list_operations_preserve_entries_and_order(self):
        value = [
            {"value": "beta", "type": "original"},
            {"value": "Alpha", "type": "primary"},
            {"value": "beta", "type": "duplicate"},
        ]

        result = apply_operation_chain(
            value,
            [
                Operation(type="unique"),
                Operation(type="sort"),
                Operation(type="reverse"),
                Operation(type="first"),
            ],
        )

        self.assertEqual(result, {"value": "beta", "type": "original"})

    def test_combine_honors_item_limit_and_extracts_dict_values(self):
        result = apply_operation_chain(
            [
                {"value": "north", "type": "primary"},
                {"value": "south", "type": "secondary"},
                {"value": "east", "type": "tertiary"},
            ],
            [
                Operation(
                    type="combine",
                    separator=" / ",
                    max_items=2,
                )
            ],
        )

        self.assertEqual(result, "north / south")

    def test_unknown_operation_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown operation type"):
            apply_operation_chain("name", [Operation(type="unknown")])

    def test_case_operations_preserve_acronyms_and_handle_lists(self):
        cases = [
            (
                Operation(type="titlecase", preserve_acronyms=True),
                ["UNESCO historic SITE", ""],
                ["UNESCO Historic SITE", ""],
            ),
            (
                Operation(type="capitalize", preserve_acronyms=True),
                ["UNESCO HISTORIC site", "historic UNESCO SITE", ""],
                ["UNESCO HISTORIC site", "Historic UNESCO SITE", ""],
            ),
            (
                Operation(type="capitalize", preserve_acronyms=False),
                "UNESCO historic site",
                "Unesco historic site",
            ),
            (Operation(type="uppercase"), ["north", "south"], ["NORTH", "SOUTH"]),
            (Operation(type="lowercase"), ["NORTH", "SOUTH"], ["north", "south"]),
        ]
        for operation, value, expected in cases:
            with self.subTest(operation=operation, value=value):
                self.assertEqual(apply_operation_chain(value, [operation]), expected)

    def test_replace_is_literal_and_honors_case_and_missing_parameters(self):
        cases = [
            (
                Operation(type="replace", replace_from="heritage", replace_to="history"),
                "Heritage heritage",
                "Heritage history",
            ),
            (Operation(type="replace", replace_from=".", replace_to="/"), "a.b", "a/b"),
            (
                Operation(
                    type="replace",
                    replace_from="heritage",
                    replace_to="history",
                    ignore_case=True,
                ),
                ["Heritage", "HERITAGE"],
                ["history", "history"],
            ),
            (Operation(type="replace"), "heritage", "heritage"),
            (
                Operation(type="replace", replace_from="heritage"),
                "heritage site",
                " site",
            ),
        ]
        for operation, value, expected in cases:
            with self.subTest(operation=operation):
                self.assertEqual(apply_operation_chain(value, [operation]), expected)

    def test_abbreviate_options_and_empty_values(self):
        operation = Operation(type="abbreviate", length_per_word=2, skip_words=["OF"], uppercase=False)
        self.assertEqual(
            apply_operation_chain(["church of england", "", "of"], [operation]),
            ["chen", "", ""],
        )
        self.assertEqual(
            apply_operation_chain("church of england", [Operation(type="abbreviate")]),
            "COE",
        )

    def test_padding_boundaries_defaults_numbers_and_booleans(self):
        for operation_type in ("lpad", "rpad"):
            for value in ("abc", "", 7, True):
                with self.subTest(operation=operation_type, value=value):
                    self.assertEqual(
                        apply_operation_chain(value, [Operation(type=operation_type)]),
                        value,
                    )
            for length, char, value, expected in (
                (2, "0", "abc", "abc"),
                (3, "0", "abc", "abc"),
                (0, "0", "", ""),
                (3, "01", 7, "007" if operation_type == "lpad" else "700"),
                (3, "", "x", "  x" if operation_type == "lpad" else "x  "),
                (3, None, "x", "  x" if operation_type == "lpad" else "x  "),
                (3, "0", True, True),
            ):
                with self.subTest(operation=operation_type, length=length, char=char, value=value):
                    self.assertEqual(
                        apply_operation_chain(
                            value,
                            [
                                Operation(
                                    type=operation_type,
                                    pad_length=length,
                                    pad_char=char,
                                )
                            ],
                        ),
                        expected,
                    )

    def test_truncate_length_boundaries_and_indicators(self):
        for length, indicator, value, expected in (
            (5, None, "abc", "abc"),
            (5, None, "abcde", "abcde"),
            (5, None, "abcdef", "ab..."),
            (2, "...", "abcdef", ".."),
            (0, "...", "abcdef", ""),
            (3, "", "abcdef", "abc"),
            (4, "!", "abcdef", "abc!"),
        ):
            with self.subTest(length=length, indicator=indicator, value=value):
                result = apply_operation_chain(
                    value,
                    [
                        Operation(
                            type="truncate",
                            max_length=length,
                            overflow_indicator=indicator,
                        )
                    ],
                )
                self.assertEqual(result, expected)
                self.assertLessEqual(len(result), length)
        self.assertEqual(
            apply_operation_chain(["abcdef", "xy"], [Operation(type="truncate", max_length=4)]),
            ["a...", "xy"],
        )
        self.assertEqual(apply_operation_chain("abcdef", [Operation(type="truncate")]), "abcdef")

    def test_combine_limits_defaults_and_scalar_passthrough(self):
        cases = [
            (Operation(type="combine"), ["a", "b"], "a, b"),
            (Operation(type="combine", separator=""), ["a", "b"], "ab"),
            (Operation(type="combine", max_items=0), ["a", "b"], ""),
            (Operation(type="combine", separator="/", max_length=3), ["a", "b"], "a/b"),
            (
                Operation(type="combine", separator="/", max_length=2),
                ["a", "b"],
                "a/...",
            ),
            (
                Operation(type="combine", separator="/", max_length=2, overflow_indicator="!"),
                ["a", "b"],
                "a/!",
            ),
            (
                Operation(type="combine", max_length=0, overflow_indicator="!"),
                ["a"],
                "!",
            ),
            (
                Operation(type="combine", max_length=2, overflow_indicator=""),
                ["abc"],
                "ab",
            ),
            (Operation(type="combine", max_items=1), ["a", "b"], "a"),
            (Operation(type="combine"), [], ""),
            (Operation(type="combine"), "a", "a"),
        ]
        for operation, value, expected in cases:
            with self.subTest(operation=operation, value=value):
                self.assertEqual(apply_operation_chain(value, [operation]), expected)

    def test_fallback_operations_handle_missing_and_present_values(self):
        for operation in (
            Operation(type="coalesce", coalesce_value="Unknown"),
            Operation(type="fallback_text", fallback_text="Unknown"),
        ):
            for value, expected in (
                (None, "Unknown"),
                ("", "Unknown"),
                (" \t", "Unknown"),
                ([], "Unknown"),
                ("Known", "Known"),
                (0, 0),
                (False, False),
                (["", "Known"], ["Unknown", "Known"]),
            ):
                with self.subTest(operation=operation.type, value=value):
                    self.assertEqual(apply_operation_chain(value, [operation]), expected)

    def test_operations_accept_none_and_empty_operation_chain_is_identity(self):
        for operation in OperationType:
            with self.subTest(operation=operation.value):
                expected = "" if operation in (OperationType.COALESCE, OperationType.FALLBACK_TEXT) else None
                self.assertEqual(
                    apply_operation_chain(None, [Operation(type=operation.value)]),
                    expected,
                )
        value = ["north", "south"]
        self.assertIs(apply_operation_chain(value, []), value)
