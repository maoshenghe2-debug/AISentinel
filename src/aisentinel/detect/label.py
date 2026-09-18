"""★ 标识核验器：对照《人工智能生成合成内容标识办法》核验文件元数据隐式标识。

三态判定（评审冻结契约，见 docs/08 §4）：
- 字段白名单命中（强字段直判；弱字段需值提示命中）→ ``has_label``（有标识）
- 无标识字段但存在重编码 / 编辑痕迹 → ``suspected_cleaned``（疑似被清理）
- 皆无 → ``no_label``（无标识）

仅依赖 Pillow 解析（PNG 文本块 / EXIF / XMP / JPEG COM 注释 / C2PA 扫描），
输出 ``LabelCheckRecord``（schema 校验）与 CSV 证据字段。
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from jsonschema import Draft7Validator
from PIL import ExifTags, Image

FIELDS_PATH = Path(__file__).parent / "label_fields.yaml"
SCHEMA_PATH = Path(__file__).parent / "label_record.schema.json"

VERDICT_HAS = "has_label"
VERDICT_SUSPECTED = "suspected_cleaned"
VERDICT_NONE = "no_label"

VERDICT_LABELS = {
    VERDICT_HAS: "有标识",
    VERDICT_SUSPECTED: "疑似被清理",
    VERDICT_NONE: "无标识",
}

STANDARD_REFS = [
    "《人工智能生成合成内容标识办法》第十二条（显式标识）",
    "《人工智能生成合成内容标识办法》第十三条（隐式标识：元数据）",
    "IPTC DigitalSourceType（trainedAlgorithmicMedia）",
    "C2PA 内容凭证（c2pa.claim / manifest）",
]

_XMP_PAIR_RE = re.compile(r'([A-Za-z0-9_]+(?::[A-Za-z0-9_]+)+)\s*=\s*"([^"]{1,300})"')


def load_fields(path: Path | None = None) -> dict:
    with open(path or FIELDS_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_record(record: dict, schema_path: Path | None = None) -> None:
    """Draft-07 schema 校验；失败抛 ValueError。"""
    schema = json.loads((schema_path or SCHEMA_PATH).read_text(encoding="utf-8"))
    errors = sorted(Draft7Validator(schema).iter_errors(record), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{list(err.path)}: {err.message}" for err in errors[:5])
        raise ValueError(f"LabelCheckRecord schema 校验失败：{detail}")


@dataclass
class Hit:
    group: str
    field: str
    value: str
    source: str

    def to_dict(self) -> dict:
        return {"group": self.group, "field": self.field, "value_preview": self.value[:120], "source": self.source}


@dataclass
class LabelRecord:
    file: str
    sha256: str
    size: int
    format: str
    verdict: str
    confidence: str
    groups: dict[str, list[dict]] = field(default_factory=dict)
    traces: list[dict] = field(default_factory=list)
    standard_refs: list[str] = field(default_factory=list)
    checked_at: str = ""

    @property
    def verdict_label(self) -> str:
        return VERDICT_LABELS.get(self.verdict, self.verdict)

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "file": self.file,
            "sha256": self.sha256,
            "size": self.size,
            "format": self.format,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "groups": self.groups,
            "traces": self.traces,
            "standard_refs": self.standard_refs,
            "checked_at": self.checked_at,
        }


# ------------------------------------------------------------------ 元数据提取


def _jpeg_segments(data: bytes) -> list[tuple[int, bytes]]:
    """解析 JPEG 段列表（marker, payload）；到 SOS 为止（熵编码段不再解析）。"""
    segments: list[tuple[int, bytes]] = []
    i, n = 2, len(data)  # 跳过 SOI
    while i + 4 <= n:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        if marker == 0xDA:  # SOS
            break
        length = (data[i + 2] << 8) | data[i + 3]
        payload = data[i + 4 : i + 2 + length]
        segments.append((marker, payload))
        i += 2 + length
    return segments


def _xmp_pairs(xmp: str) -> dict[str, str]:
    return {name: value for name, value in _XMP_PAIR_RE.findall(xmp or "")}


def extract_metadata(path: Path | str) -> dict:
    """提取元数据：文本块 / EXIF / XMP / JPEG 注释 / C2PA 扫描标记。"""
    path = Path(path)
    data = path.read_bytes()
    meta: dict = {"format": "", "text": {}, "exif": {}, "xmp": "", "comments": []}
    try:
        with Image.open(io.BytesIO(data)) as img:
            meta["format"] = img.format or ""
            for key, value in img.info.items():
                if key.lower() == "exif":
                    continue
                if isinstance(value, str):
                    meta["text"][key] = value
                    if "<xmpmeta" in value:
                        meta["xmp"] = value
            try:
                exif = img.getexif()
            except Exception:
                exif = {}
            for tag_id, value in exif.items():
                name = ExifTags.TAGS.get(tag_id, str(tag_id))
                meta["exif"][name] = str(value)[:300]
    except Exception as exc:  # 解析失败不阻断：记录并继续（文件仍可做字节级扫描）
        meta["error"] = str(exc)

    if data[:2] == b"\xff\xd8":  # JPEG
        for marker, payload in _jpeg_segments(data):
            if marker == 0xFE:  # COM 注释
                meta["comments"].append(payload.decode("utf-8", errors="replace")[:300])
            elif marker == 0xE1 and payload[:28] == b"http://ns.adobe.com/xap/1.0/":
                meta["xmp"] = payload[28:].decode("utf-8", errors="replace")
    if b"c2pa" in data:
        meta["text"]["__c2pa_scan__"] = "c2pa"
    return meta


def _candidates(meta: dict) -> list[tuple[str, str, str]]:
    """(字段名, 值, 来源) 候选三元组。"""
    out: list[tuple[str, str, str]] = []
    for key, value in meta["text"].items():
        if key == "__c2pa_scan__" or "<xmpmeta" in value:
            continue
        out.append((key, value, "text_chunk"))
    for key, value in meta["exif"].items():
        out.append((key, value, "exif"))
    for name, value in _xmp_pairs(meta.get("xmp", "")).items():
        out.append((name, value, "xmp"))
    for comment in meta["comments"]:
        out.append(("Comment", comment, "comment"))
    return out


def _normalize(name: str) -> str:
    return name.split(":")[-1].strip().lower()


def _find_traces(fields_doc: dict, meta: dict) -> list[dict]:
    blob = " ".join(
        [
            *[str(v) for v in meta["text"].values()],
            *[str(v) for v in meta["exif"].values()],
            *meta["comments"],
            meta.get("xmp", ""),
        ]
    ).lower()
    traces: list[dict] = []
    for kind, patterns in (fields_doc.get("traces") or {}).items():
        for pattern in patterns:
            if pattern.lower() in blob:
                traces.append({"kind": kind, "detail": pattern})
    return traces


# ------------------------------------------------------------------ 核验主流程


def verify_label(path: Path | str, *, validate: bool = False) -> LabelRecord:
    """核验单个文件的三态标识结论。"""
    path = Path(path)
    data = path.read_bytes()
    fields_doc = load_fields()
    meta = extract_metadata(path)
    candidates = _candidates(meta)

    hits: dict[str, list[Hit]] = {"provider": [], "synthesis": [], "content_id": []}
    for group_name, group in (fields_doc.get("groups") or {}).items():
        strong = {item.lower() for item in group.get("strong_fields", [])}
        weak = {_normalize(item) for item in group.get("fields", [])}
        hints = [hint.lower() for hint in group.get("value_hints", [])]
        for name, value, source in candidates:
            norm = _normalize(name)
            if norm in strong or (norm in weak and any(hint in str(value).lower() for hint in hints)):
                hits[group_name].append(Hit(group_name, name, str(value), source))
    if "__c2pa_scan__" in meta["text"]:
        hits["synthesis"].append(Hit("synthesis", "c2pa", "内容凭证（C2PA）存在", "raw"))

    traces = _find_traces(fields_doc, meta)
    if any(hits[group] for group in hits):
        verdict, confidence = VERDICT_HAS, "high"
    elif traces:
        verdict, confidence = VERDICT_SUSPECTED, "medium"
    else:
        verdict, confidence = VERDICT_NONE, "medium"

    record = LabelRecord(
        file=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        format=meta.get("format", ""),
        verdict=verdict,
        confidence=confidence,
        groups={group: [hit.to_dict() for hit in hit_list] for group, hit_list in hits.items()},
        traces=traces,
        standard_refs=list(STANDARD_REFS),
        checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    if validate:
        validate_record(record.to_dict())
    return record


def verify_dir(directory: Path | str, *, suffixes: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")) -> list[LabelRecord]:
    """目录级批量核验（按扩展名过滤，保序）。"""
    directory = Path(directory)
    records = []
    for item in sorted(directory.iterdir()):
        if item.is_file() and item.suffix.lower() in suffixes:
            records.append(verify_label(item))
    return records
