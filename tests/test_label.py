"""标识核验器测试：5 类测试矩阵 + 阴性集 + schema 校验 + CSV 证据字段。

测试矩阵（docs/08 §4 冻结口径）：
1. AI 原图（SD 参数块）→ 有标识
2. 服务商字段 + 值提示（Software=即梦AI）→ 有标识
3. 重编码痕迹（gd-jpeg 编码注释）→ 疑似被清理
4. 普通相机照（EXIF 相机字段，无 AI 痕迹）→ 无标识
5. XMP DigitalSourceType=trainedAlgorithmicMedia → 有标识（合成属性）
阴性集：编辑工具痕迹（Photoshop）→ 疑似被清理（设计内行为，不得判为「有标识」）
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from aisentinel.detect.csvout import records_to_csv
from aisentinel.detect.label import (
    VERDICT_HAS,
    VERDICT_NONE,
    VERDICT_SUSPECTED,
    extract_metadata,
    validate_record,
    verify_dir,
    verify_label,
)


def _png_with_text(path: Path, pairs: dict[str, str], *, extra_bytes: bytes = b"") -> Path:
    img = Image.new("RGB", (64, 48), (30, 60, 90))
    info = PngInfo()
    for key, value in pairs.items():
        info.add_text(key, value)
    img.save(path, pnginfo=info)
    if extra_bytes:
        path.write_bytes(path.read_bytes() + extra_bytes)
    return path


def _jpeg_with_meta(
    path: Path,
    exif_pairs: dict[int, str] | None = None,
    *,
    comment: str | None = None,
    xmp: str | None = None,
) -> Path:
    img = Image.new("RGB", (64, 48), (120, 90, 60))
    kwargs: dict = {}
    if exif_pairs:
        exif = Image.Exif()
        for tag_id, value in exif_pairs.items():
            exif[tag_id] = value
        kwargs["exif"] = exif.tobytes()
    img.save(path, **kwargs)
    inject = b""
    if comment:
        payload = comment.encode("utf-8")
        inject += b"\xff\xfe" + (len(payload) + 2).to_bytes(2, "big") + payload
    if xmp:
        payload = b"http://ns.adobe.com/xap/1.0/" + xmp.encode("utf-8")
        inject += b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    if inject:
        data = path.read_bytes()
        path.write_bytes(data[:2] + inject + data[2:])
    return path


# ------------------------------------------------------------------ 5 类矩阵


def test_matrix_1_ai_sd_png_has_label(tmp_path):
    path = _png_with_text(
        tmp_path / "ai_sd.png",
        {"parameters": "a cat, steps: 20, sampler: Euler a, CFG scale: 7, Seed: 42, Model: sd_xl"},
    )
    record = verify_label(path, validate=True)
    assert record.verdict == VERDICT_HAS
    assert any(hit["field"] == "parameters" for hit in record.groups["synthesis"])


def test_matrix_2_provider_hint_png_has_label(tmp_path):
    path = _png_with_text(tmp_path / "provider.png", {"Software": "即梦AI v2"})
    record = verify_label(path)
    assert record.verdict == VERDICT_HAS
    assert record.groups["provider"]


def test_matrix_3_reencoded_jpeg_suspected(tmp_path):
    path = _jpeg_with_meta(tmp_path / "reencoded.jpg", comment="CREATOR: gd-jpeg v1.0 (using IJG JPEG v62)")
    record = verify_label(path)
    assert record.verdict == VERDICT_SUSPECTED
    assert record.traces and record.traces[0]["kind"] == "encoder_comments"


def test_matrix_4_camera_jpeg_no_label(tmp_path):
    path = _jpeg_with_meta(
        tmp_path / "camera.jpg",
        exif_pairs={0x010F: "Canon", 0x0110: "Canon EOS R6", 0x0131: "Ver1.00"},
    )
    record = verify_label(path)
    assert record.verdict == VERDICT_NONE
    assert not record.traces  # 相机固件 Software 不应误报为编辑痕迹


def test_matrix_5_xmp_digital_source_type(tmp_path):
    xmp = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description '
        'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia" '
        'xmp:CreatorTool="Adobe Firefly"/></rdf:RDF></x:xmpmeta>'
    )
    path = _jpeg_with_meta(tmp_path / "xmp.jpg", xmp=xmp)
    record = verify_label(path)
    assert record.verdict == VERDICT_HAS
    assert any("DigitalSourceType" in hit["field"] for hit in record.groups["synthesis"])


def test_matrix_c2pa_scan_png(tmp_path):
    path = _png_with_text(tmp_path / "c2pa.png", {"Source": "screenshot"}, extra_bytes=b"c2pa.claim")
    record = verify_label(path)
    assert record.verdict == VERDICT_HAS
    assert any(hit["field"] == "c2pa" for hit in record.groups["synthesis"])


# ------------------------------------------------------------------ 阴性集


def test_negative_edited_jpeg_never_has_label(tmp_path):
    """编辑工具痕迹（Photoshop）→ 疑似被清理；绝不能判为「有标识」。"""
    path = _jpeg_with_meta(tmp_path / "edited.jpg", exif_pairs={0x0131: "Adobe Photoshop 25.0"})
    record = verify_label(path)
    assert record.verdict == VERDICT_SUSPECTED
    assert record.verdict != VERDICT_HAS


def test_negative_plain_png_no_label(tmp_path):
    path = tmp_path / "plain.png"
    Image.new("RGB", (64, 48), (10, 10, 10)).save(path)
    record = verify_label(path)
    assert record.verdict == VERDICT_NONE
    assert all(not record.groups[group] for group in ("provider", "synthesis", "content_id"))


# ------------------------------------------------------------------ 元数据 / CSV / schema


def test_extract_metadata_sources(tmp_path):
    path = _jpeg_with_meta(
        tmp_path / "meta.jpg",
        exif_pairs={0x0131: "TestSoft"},
        comment="hello-comment",
        xmp='<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><x:CreatorTool="ToolX"/></rdf:RDF></x:xmpmeta>',
    )
    meta = extract_metadata(path)
    assert meta["format"] == "JPEG"
    assert meta["exif"].get("Software") == "TestSoft"
    assert "hello-comment" in meta["comments"]
    assert "ToolX" in meta["xmp"]


def test_csv_evidence_columns(tmp_path):
    directory = tmp_path / "imgs"
    directory.mkdir()
    _png_with_text(directory / "a.png", {"parameters": "steps: 1"})
    _jpeg_with_meta(directory / "b.jpg", comment="CREATOR: gd-jpeg v1.0")
    records = verify_dir(directory)
    assert len(records) == 2
    out = tmp_path / "out.csv"
    assert records_to_csv(records, out) == 2
    header = out.read_text(encoding="utf-8-sig").splitlines()[0]
    for column in ("verdict", "provider_hits", "synthesis_hits", "content_id_hits", "traces", "sha256"):
        assert column in header


def test_schema_rejects_bad_record():
    with pytest.raises(ValueError):
        validate_record({"schema_version": 1, "file": "x"})


def test_verify_dir_skips_non_images(tmp_path):
    directory = tmp_path / "mixed"
    directory.mkdir()
    (directory / "readme.txt").write_text("x", encoding="utf-8")
    _png_with_text(directory / "only.png", {"Software": "TestSuite"})
    records = verify_dir(directory)
    assert len(records) == 1
