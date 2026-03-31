# from dataclasses import dataclass, field
import re
import unicodedata
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from .schema import (
    FieldDefinition,
    Operation,
    RuleDefinition,
    DisplayDescriptorRuleBlock,
    DisplayDescriptorConfig,
)


class OperationType(str, Enum):
    """Valid operation types for display descriptor transformations."""

    TITLECASE = "titlecase"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    CAPITALIZE = "capitalize"
    TRIM = "trim"
    LTRIM = "ltrim"
    RTRIM = "rtrim"
    LPAD = "lpad"
    RPAD = "rpad"
    NORMALIZE_WHITESPACE = "normalize_whitespace"
    REPLACE = "replace"
    COALESCE = "coalesce"
    FALLBACK_TEXT = "fallback_text"
    REMOVE_DIACRITICS = "remove_diacritics"
    REMOVE_SPECIAL_CHARS = "remove_special_chars"
    UNIQUE = "unique"
    SORT = "sort"
    REVERSE = "reverse"
    ABBREVIATE = "abbreviate"
    PREFIX = "prefix"
    SUFFIX = "suffix"
    TRUNCATE = "truncate"
    COMBINE = "combine"


def op_titlecase(value: Any) -> Any:
    if isinstance(value, str):
        # Proper title case that handles apostrophes correctly-ish:
        # Capitalize the first alphabetical character of each word and
        # lowercase the remainder.
        def _cap_word(w: str) -> str:
            for i, ch in enumerate(w):
                if ch.isalpha():
                    return w[:i] + ch.upper() + w[i + 1:].lower()
            return w

        return " ".join(_cap_word(word) for word in value.split())
    if isinstance(value, list):
        return [op_titlecase(v) for v in value]
    return value


def op_uppercase(value: Any) -> Any:
    if isinstance(value, str):
        return value.upper()
    if isinstance(value, list):
        return [op_uppercase(v) for v in value]
    return value


def op_lowercase(value: Any) -> Any:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, list):
        return [op_lowercase(v) for v in value]
    return value


def op_trim(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [op_trim(v) for v in value]
    return value


def op_ltrim(value: Any) -> Any:
    if isinstance(value, str):
        return value.lstrip()
    if isinstance(value, list):
        return [op_ltrim(v) for v in value]
    return value


def op_rtrim(value: Any) -> Any:
    if isinstance(value, str):
        return value.rstrip()
    if isinstance(value, list):
        return [op_rtrim(v) for v in value]
    return value


def _normalize_pad_char(pad_char: Optional[str]) -> str:
    if not pad_char:
        return " "
    return pad_char[0]


def op_lpad(value: Any, pad_length: int, pad_char: str = " ") -> Any:
    if isinstance(value, str):
        if len(value) >= pad_length:
            return value
        return value.rjust(pad_length, _normalize_pad_char(pad_char))
    if isinstance(value, list):
        return [op_lpad(v, pad_length, pad_char) for v in value]
    return value


def op_rpad(value: Any, pad_length: int, pad_char: str = " ") -> Any:
    if isinstance(value, str):
        if len(value) >= pad_length:
            return value
        return value.ljust(pad_length, _normalize_pad_char(pad_char))
    if isinstance(value, list):
        return [op_rpad(v, pad_length, pad_char) for v in value]
    return value


def op_normalize_whitespace(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if isinstance(value, list):
        return [op_normalize_whitespace(v) for v in value]
    return value


def op_replace(
    value: Any,
    replace_from: str,
    replace_to: str = "",
    ignore_case: bool = False,
) -> Any:
    if isinstance(value, str):
        if replace_from is None or replace_from == "":
            return value
        if ignore_case:
            return re.sub(
                re.escape(replace_from),
                lambda _: replace_to,
                value,
                flags=re.IGNORECASE,
            )
        return value.replace(replace_from, replace_to)
    if isinstance(value, list):
        return [op_replace(v, replace_from, replace_to, ignore_case) for v in value]
    return value


def op_coalesce(value: Any, coalesce_value: str = "") -> Any:
    if value is None:
        return coalesce_value
    if isinstance(value, str) and value.strip() == "":
        return coalesce_value
    if isinstance(value, list):
        if len(value) == 0:
            return coalesce_value
        return [op_coalesce(v, coalesce_value) for v in value]
    return value


def op_remove_diacritics(value: Any) -> Any:
    if isinstance(value, str):
        # Normalize to NFD (decomposed form) and filter out combining characters
        normalized = unicodedata.normalize("NFD", value)
        return "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    if isinstance(value, list):
        return [op_remove_diacritics(v) for v in value]
    return value


def op_remove_special_chars(value: Any) -> Any:
    if isinstance(value, str):
        # Keep only alphanumerics and spaces
        return re.sub(r"[^a-zA-Z0-9\s]", "", value)
    if isinstance(value, list):
        return [op_remove_special_chars(v) for v in value]
    return value


def op_unique(value: Any) -> Any:
    if isinstance(value, list):
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for item in value:
            # Handle dicts with 'value' key for uniqueness check
            check_val = item.get("value", item) if isinstance(
                item, dict) else item
            # Convert to string for comparison to handle various types
            check_key = str(check_val)
            if check_key not in seen:
                seen.add(check_key)
                result.append(item)
        return result
    return value


def op_sort(value: Any) -> Any:
    if isinstance(value, list):
        # Sort items, handling dicts with 'value' key
        def _sort_key(item):
            if isinstance(item, dict):
                return str(item.get("value", "")).lower()
            return str(item).lower()

        return sorted(value, key=_sort_key)
    return value


def op_reverse(value: Any) -> Any:
    if isinstance(value, list):
        return list(reversed(value))
    return value


def op_truncate(value: Any, max_length: int, truncate_indicator: str = "...") -> Any:
    if isinstance(value, str):
        if len(value) <= max_length:
            return value
        # Subtract indicator length from max_length to make room for it
        available = max_length - len(truncate_indicator)
        if available < 0:
            # If indicator is longer than max_length, just use indicator
            return truncate_indicator[:max_length]
        return value[:available] + truncate_indicator
    if isinstance(value, list):
        return [op_truncate(v, max_length, truncate_indicator) for v in value]
    return value


def op_capitalize(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) == 0:
            return value
        return value[0].upper() + value[1:].lower()
    if isinstance(value, list):
        return [op_capitalize(v) for v in value]
    return value


def op_abbreviate(
    value: Any,
    length_per_word: int = 1,
    skip_words: Optional[List[str]] = None,
    uppercase: bool = True,
) -> Any:
    if isinstance(value, str):
        skip_list = [w.lower() for w in (skip_words or [])]
        words = value.split()
        abbrev_chars = []
        for word in words:
            if word.lower() not in skip_list:
                # Take characters from the word
                chars = word[:length_per_word]
                if uppercase:
                    chars = chars.upper()
                abbrev_chars.append(chars)
        return "".join(abbrev_chars)
    if isinstance(value, list):
        return [op_abbreviate(v, length_per_word, skip_words, uppercase) for v in value]
    return value


def op_prefix(value: Any, prefix_value: str = "") -> Any:
    if isinstance(value, str):
        return prefix_value + value
    if isinstance(value, list):
        return [op_prefix(v, prefix_value) for v in value]
    return value


def op_suffix(value: Any, suffix_value: str = "") -> Any:
    if isinstance(value, str):
        return value + suffix_value
    if isinstance(value, list):
        return [op_suffix(v, suffix_value) for v in value]
    return value


def op_combine(
    values: Any,
    separator: str = ", ",
    max_items: Optional[int] = None,
    max_length: Optional[int] = None,
    overflow_indicator: str = "...",
) -> Any:
    if not isinstance(values, list):
        return values

    # If items are dicts with a 'value' key, extract that for combining.
    def _extract(v):
        if isinstance(v, dict):
            return v.get("value", v)
        return v

    items = [_extract(v) for v in values]
    if max_items is not None:
        items = items[:max_items]

    combined = separator.join(str(v) for v in items)

    if max_length is not None and len(combined) > max_length:
        combined = combined[:max_length] + overflow_indicator

    return combined


# -------------------------------------------------------------------
# Operation handler functions for dispatch dictionary
# -------------------------------------------------------------------


def _handle_abbreviate(value: Any, op: Operation) -> Any:
    """Handler for abbreviate operation with parameter extraction."""
    return op_abbreviate(
        value,
        length_per_word=op.length_per_word or 1,
        skip_words=op.skip_words,
        uppercase=op.uppercase if op.uppercase is not None else True,
    )


def _handle_prefix(value: Any, op: Operation) -> Any:
    """Handler for prefix operation with parameter extraction."""
    return op_prefix(value, prefix_value=op.prefix_value or "")


def _handle_suffix(value: Any, op: Operation) -> Any:
    """Handler for suffix operation with parameter extraction."""
    return op_suffix(value, suffix_value=op.suffix_value or "")


def _handle_truncate(value: Any, op: Operation) -> Any:
    """Handler for truncate operation with parameter extraction."""
    if op.max_length is not None:
        return op_truncate(
            value,
            max_length=op.max_length,
            truncate_indicator=(
                op.overflow_indicator if op.overflow_indicator is not None else "..."
            ),
        )
    return value


def _handle_combine(value: Any, op: Operation) -> Any:
    """Handler for combine operation with parameter extraction."""
    return op_combine(
        value,
        separator=op.separator if op.separator is not None else ", ",
        max_items=op.max_items,
        max_length=op.max_length,
        overflow_indicator=(
            op.overflow_indicator if op.overflow_indicator is not None else "..."
        ),
    )


def _handle_lpad(value: Any, op: Operation) -> Any:
    """Handler for lpad operation with parameter extraction."""
    if op.pad_length is None:
        return value
    return op_lpad(
        value,
        pad_length=op.pad_length,
        pad_char=op.pad_char if op.pad_char is not None else " ",
    )


def _handle_rpad(value: Any, op: Operation) -> Any:
    """Handler for rpad operation with parameter extraction."""
    if op.pad_length is None:
        return value
    return op_rpad(
        value,
        pad_length=op.pad_length,
        pad_char=op.pad_char if op.pad_char is not None else " ",
    )


def _handle_replace(value: Any, op: Operation) -> Any:
    """Handler for replace operation with parameter extraction."""
    return op_replace(
        value,
        replace_from=op.replace_from if op.replace_from is not None else "",
        replace_to=op.replace_to if op.replace_to is not None else "",
        ignore_case=op.ignore_case if op.ignore_case is not None else False,
    )


def _handle_coalesce(value: Any, op: Operation) -> Any:
    """Handler for coalesce operation with parameter extraction."""
    fallback_value = (
        op.coalesce_value
        if op.coalesce_value is not None
        else (op.fallback_text if op.fallback_text is not None else "")
    )
    return op_coalesce(
        value,
        coalesce_value=fallback_value,
    )


# Dispatch dictionary mapping operation types to their handlers
OPERATION_HANDLERS = {
    OperationType.TITLECASE.value: lambda v, op: op_titlecase(v),
    OperationType.UPPERCASE.value: lambda v, op: op_uppercase(v),
    OperationType.LOWERCASE.value: lambda v, op: op_lowercase(v),
    OperationType.CAPITALIZE.value: lambda v, op: op_capitalize(v),
    OperationType.TRIM.value: lambda v, op: op_trim(v),
    OperationType.LTRIM.value: lambda v, op: op_ltrim(v),
    OperationType.RTRIM.value: lambda v, op: op_rtrim(v),
    OperationType.LPAD.value: _handle_lpad,
    OperationType.RPAD.value: _handle_rpad,
    OperationType.NORMALIZE_WHITESPACE.value: lambda v, op: op_normalize_whitespace(v),
    OperationType.REPLACE.value: _handle_replace,
    OperationType.COALESCE.value: _handle_coalesce,
    OperationType.FALLBACK_TEXT.value: _handle_coalesce,
    OperationType.REMOVE_DIACRITICS.value: lambda v, op: op_remove_diacritics(v),
    OperationType.REMOVE_SPECIAL_CHARS.value: lambda v, op: op_remove_special_chars(v),
    OperationType.UNIQUE.value: lambda v, op: op_unique(v),
    OperationType.SORT.value: lambda v, op: op_sort(v),
    OperationType.REVERSE.value: lambda v, op: op_reverse(v),
    OperationType.ABBREVIATE.value: _handle_abbreviate,
    OperationType.PREFIX.value: _handle_prefix,
    OperationType.SUFFIX.value: _handle_suffix,
    OperationType.TRUNCATE.value: _handle_truncate,
    OperationType.COMBINE.value: _handle_combine,
}


def apply_operation_chain(value: Any, ops: List[Operation]) -> Any:
    """Apply a chain of operations to a value.

    Args:
        value: The value to transform.
        ops: List of Operation objects to apply sequentially.

    Returns:
        The transformed value after applying all operations.

    Raises:
        ValueError: If an unknown operation type is encountered.
    """
    for op in ops:
        handler = OPERATION_HANDLERS.get(op.type)
        if handler:
            value = handler(value, op)
        else:
            # This shouldn't happen if validation is working correctly
            raise ValueError(f"Unknown operation type: {op.type}")
    return value


# -------------------------------------------------------------------
# Selector logic (including Statutory|Original|FIRST)
# -------------------------------------------------------------------


def _priority_select(
    candidates: List[Dict[str, Any]], field: str, priority_spec: str
) -> List[Dict[str, Any]]:
    """
    priority_spec example: "Statutory|Original|FIRST"
    """
    options = priority_spec.split("|")
    remaining = candidates

    for opt in options:
        if opt == "FIRST":
            return remaining[:1] if remaining else []
        filtered = [c for c in remaining if c.get(field) == opt]
        if filtered:
            # Pick the first matching candidate to enforce a single value
            return filtered[:1]

    return []


def _match_filter_value_simple(
    candidate: Dict[str, Any], field: str, allowed: List[str]
) -> bool:
    value = candidate.get(field)
    return value in allowed


def _find_parent_field_for_subfield(
    field_defs: List[FieldDefinition], subfield_name: str
) -> Optional[str]:
    """Find the parent field that contains the given subfield."""
    for field_def in field_defs:
        if subfield_name in field_def.subfields:
            return field_def.name
    return None


def select_field_value(
    rule: RuleDefinition, resource: Dict[str, Any], field_defs: Optional[List[FieldDefinition]] = None
) -> Any:
    """
    Resolve the value for a rule's field from the resource, applying filters and priority semantics.

    Assumes complex fields like:
      "Monument Name": [
          {"value": "old church", "Monument Name Use Type": "Primary"},
          ...
      ]

    Also supports subfield rules: if the rule name is a subfield of a parent field,
    this function will extract it from the parent field's value.
    """

    # Check if this rule references a subfield
    parent_field = None
    if field_defs:
        parent_field = _find_parent_field_for_subfield(field_defs, rule.name)

    if parent_field:
        # Get the parent field value
        raw_value = resource.get(parent_field)
        if raw_value is None:
            return None

        # Extract the subfield from the parent field's value(s)
        if isinstance(raw_value, list) and all(isinstance(x, dict) for x in raw_value):
            # Parent field is a list of dict entries; extract subfield from each
            subfield_values = []
            for entry in raw_value:
                if rule.name in entry:
                    subfield_values.append(entry[rule.name])

            if not subfield_values:
                return None
            if len(subfield_values) == 1:
                return subfield_values[0]
            return subfield_values
        elif isinstance(raw_value, dict):
            # Single dict entry
            return raw_value.get(rule.name)
        return None

    # Original logic for non-subfield rules
    raw_value = resource.get(rule.name)

    if raw_value is None:
        return None

    if not rule.field_filters:
        return raw_value

    # list-of-dicts case (e.g. Monument Name entries)
    if isinstance(raw_value, list) and all(isinstance(x, dict) for x in raw_value):
        candidates = raw_value

        for field, allowed in rule.field_filters.items():
            if len(allowed) == 1 and isinstance(allowed[0], str) and "|" in allowed[0]:
                candidates = _priority_select(candidates, field, allowed[0])
            else:
                candidates = [
                    c
                    for c in candidates
                    if _match_filter_value_simple(c, field, allowed)
                ]

            if not candidates:
                break

        if not candidates:
            return None

        if len(candidates) == 1:
            c = candidates[0]
            # Preserve the full entry when it carries subfields so the caller
            # can spread them into the format context.
            if isinstance(c, dict) and "value" in c and len(c) > 1:
                return c
            return c.get("value", c)
        return [c.get("value", c) for c in candidates]

    # scalar case with filters: you can tighten this later if needed
    return raw_value


# -------------------------------------------------------------------
# Formatting engine
# -------------------------------------------------------------------


def execute_rule_definition(
    rule: RuleDefinition, resource: Dict[str, Any], field_defs: Optional[List[FieldDefinition]] = None
) -> Tuple[Optional[Any], bool]:
    """
    Returns:
      (value, used_default)

    When the resolved value is a subfield dict (e.g. {"value": "old church",
    "Monument Name Use Type": "Primary"}), operations are applied only to the
    inner "value" string and the full dict is returned so that callers can
    spread the subfield entries into the format context.
    """
    value = select_field_value(rule, resource, field_defs)
    used_default = False

    if value is None:
        if rule.default is not None:
            value = rule.default
            used_default = True
        elif rule.required:
            return None, False

    if isinstance(value, dict) and "value" in value:
        processed = apply_operation_chain(value["value"], rule.operations)
        return {**value, "value": processed}, used_default

    value = apply_operation_chain(value, rule.operations)
    return value, used_default


def execute_rule_block(
    block: DisplayDescriptorRuleBlock, resource: Dict[str, Any], field_defs: Optional[List[FieldDefinition]] = None
) -> Optional[str]:
    """
    Try to execute a single rule block.
    Returns formatted string or None if the block fails.
    """
    context: Dict[str, Any] = {}

    for rule in block.rule:
        # Check if this rule references a subfield that was already populated from a parent field
        is_subfield = field_defs and any(
            rule.name in field_def.subfields for field_def in field_defs
        )

        if is_subfield and rule.name in context:
            # Use the subfield value that's already in context from the parent field rule
            # and apply this rule's operations to it
            value = context[rule.name]
            value = apply_operation_chain(value, rule.operations)
            used_default = False
        else:
            # Extract from resource normally (operations applied by execute_rule_definition)
            value, used_default = execute_rule_definition(
                rule, resource, field_defs)

        # When the value is a subfield dict, spread its extra keys into the
        # context so they are referenceable in the format string (e.g.
        # {Monument Name Use Type}).  Extract the plain string for the
        # parent field name as usual.
        subfield_context: Dict[str, Any] = {}
        if isinstance(value, dict) and "value" in value:
            subfield_context = {k: v for k, v in value.items() if k != "value"}
            value = value["value"]

        if value is None and rule.required:
            return None

        if used_default and rule.format_when_default:
            formatted = rule.format_when_default.format(**{rule.name: value})
            context[rule.name] = formatted
        elif not used_default and rule.format_when_present:
            formatted = rule.format_when_present.format(**{rule.name: value})
            context[rule.name] = formatted
        else:
            context[rule.name] = "" if value is None else value

        context.update(subfield_context)

    try:
        formatted = block.format.format(**context)
        formatted = apply_operation_chain(formatted, block.format_operations)
        return formatted
    except KeyError:
        return None


class DisplayDescriptorEngine:
    def __init__(self, config: DisplayDescriptorConfig):
        self.config = config

    def render(self, resource: Dict[str, Any]) -> Optional[str]:
        """
        Try each rule block in order; return the first successful formatted string.
        """
        for block in self.config.display_descriptor_rules:
            result = execute_rule_block(block, resource, self.config.fields)
            if result is not None:
                return result
        return None
