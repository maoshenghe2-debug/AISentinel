"""标识核验 CSV 证据输出（冻结清单：三态单测 + CSV 证据字段）。"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from .label import LabelRecord

COLUMNS = [
    "file",
    "verdict",
    "verdict_label",
    "confidence",
    "format",
    "size",
    "provider_hits",
    "synthesis_hits",
    "content_id_hits",
    "traces",
    "sha256",
    "checked_at",
]


def _join_hits(hits: list[dict]) -> str:
    return "; ".join(f"{item['field']}={item['value_preview']}" for item in hits)


def records_to_csv(records: Iterable[LabelRecord], out_path: Path | str) -> int:
    """写出 CSV 证据文件，返回记录数。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for record in records:
            groups = record.groups
            writer.writerow(
                {
                    "file": record.file,
                    "verdict": record.verdict,
                    "verdict_label": record.verdict_label,
                    "confidence": record.confidence,
                    "format": record.format,
                    "size": record.size,
                    "provider_hits": _join_hits(groups.get("provider", [])),
                    "synthesis_hits": _join_hits(groups.get("synthesis", [])),
                    "content_id_hits": _join_hits(groups.get("content_id", [])),
                    "traces": "; ".join(f"{item['kind']}:{item['detail']}" for item in record.traces),
                    "sha256": record.sha256,
                    "checked_at": record.checked_at,
                }
            )
            count += 1
    return count
