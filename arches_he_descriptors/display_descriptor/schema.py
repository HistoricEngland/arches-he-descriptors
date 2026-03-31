from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class FieldDefinition:
    name: str
    subfields: List[str] = field(default_factory=list)


@dataclass
class Operation:
    type: str
    separator: Optional[str] = None
    max_items: Optional[int] = None
    max_length: Optional[int] = None
    overflow_indicator: Optional[str] = None
    # For abbreviate operation
    length_per_word: Optional[int] = None
    skip_words: Optional[List[str]] = None
    uppercase: Optional[bool] = None
    # For prefix/suffix operations
    prefix_value: Optional[str] = None
    suffix_value: Optional[str] = None
    # For pad operations
    pad_length: Optional[int] = None
    pad_char: Optional[str] = None
    # For replace operation
    replace_from: Optional[str] = None
    replace_to: Optional[str] = None
    ignore_case: Optional[bool] = None
    # For coalesce operation
    coalesce_value: Optional[str] = None
    fallback_text: Optional[str] = None


@dataclass
class RuleDefinition:
    name: str
    required: Optional[bool] = None
    default: Optional[str] = None
    format_when_present: Optional[str] = None
    format_when_default: Optional[str] = None
    operations: List[Operation] = field(default_factory=list)
    field_filters: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class DisplayDescriptorRuleBlock:
    rule: List[RuleDefinition]
    format: str
    format_operations: List[Operation] = field(default_factory=list)


@dataclass
class DisplayDescriptorConfig:
    fields: List[FieldDefinition]
    display_descriptor_rules: List[DisplayDescriptorRuleBlock]
