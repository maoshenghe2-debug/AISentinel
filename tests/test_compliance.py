"""合规自查与 demo 测试。"""

from __future__ import annotations

from aisentinel.compliance.report import load_mapping, render_html, render_markdown, write_report


def test_mapping_count_and_shape():
    doc = load_mapping()
    items = doc.get("items") or []
    assert len(items) >= 15
    for item in items:
        for field in ("id", "source", "article", "requirement", "feature", "verify"):
            assert item.get(field), f"{item.get('id')} 缺字段 {field}"
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))


def test_render_and_write(tmp_path):
    doc = load_mapping()
    assert "合规自查" in render_html(doc, version="test")
    assert "条款" in render_markdown(doc, version="test")
    html_path, md_path = write_report(tmp_path / "c.html", version="test")
    assert html_path.exists() and md_path.exists()


def test_demo_smoke(tmp_path):
    from aisentinel.demo import run_demo

    result = run_demo(model="mock://", out_dir=tmp_path / "demo", limit=12)
    assert len(result["acts"]) == 4
    assert result["seconds"] >= 0
    demo_dir = tmp_path / "demo"
    for name in (
        "label_check.csv",
        "eval_report.html",
        "eval_report.md",
        "compliance_report.html",
        "compliance_report.md",
    ):
        assert (demo_dir / name).exists(), name
