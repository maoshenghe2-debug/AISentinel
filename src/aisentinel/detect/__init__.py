"""aisentinel.detect：AIGC 鉴别（★ 标识核验器）。"""

from .label import (
    STANDARD_REFS,
    VERDICT_HAS,
    VERDICT_LABELS,
    VERDICT_NONE,
    VERDICT_SUSPECTED,
    LabelRecord,
    extract_metadata,
    load_fields,
    validate_record,
    verify_dir,
    verify_label,
)

__all__ = [
    "STANDARD_REFS",
    "VERDICT_HAS",
    "VERDICT_LABELS",
    "VERDICT_NONE",
    "VERDICT_SUSPECTED",
    "LabelRecord",
    "extract_metadata",
    "load_fields",
    "validate_record",
    "verify_dir",
    "verify_label",
]
