"""生成标识核验演示样本（合成数据，覆盖三态判定）。

用法：python scripts/make_label_samples.py [输出目录，默认 _samples/]
样本：
- ai_generated.png     AI 原图（SD 参数块）        → 有标识
- provider_labeled.png 服务商字段（Software=即梦AI） → 有标识
- camera_photo.jpg     普通相机照（Canon EXIF）      → 无标识
- reencoded.jpg        重编码痕迹（gd-jpeg 注释）    → 疑似被清理
- edited.jpg           编辑工具痕迹（Photoshop）     → 疑似被清理（阴性集）
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo


def _inject_comment(path: Path, comment: str) -> None:
    data = path.read_bytes()
    payload = comment.encode("utf-8")
    segment = b"\xff\xfe" + (len(payload) + 2).to_bytes(2, "big") + payload
    path.write_bytes(data[:2] + segment + data[2:])


def main(out_dir: str = "_samples") -> None:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    info = PngInfo()
    info.add_text("parameters", "a cat, steps: 20, sampler: Euler a, CFG scale: 7, Seed: 42, Model: sd_xl")
    Image.new("RGB", (256, 192), (40, 90, 140)).save(target / "ai_generated.png", pnginfo=info)

    info2 = PngInfo()
    info2.add_text("Software", "即梦AI v2")
    Image.new("RGB", (256, 192), (90, 40, 140)).save(target / "provider_labeled.png", pnginfo=info2)

    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif[0x0110] = "Canon EOS R6"
    exif[0x0131] = "Ver1.00"
    Image.new("RGB", (256, 192), (140, 90, 40)).save(target / "camera_photo.jpg", exif=exif.tobytes())

    Image.new("RGB", (256, 192), (60, 60, 60)).save(target / "reencoded.jpg")
    _inject_comment(target / "reencoded.jpg", "CREATOR: gd-jpeg v1.0 (using IJG JPEG v62)")

    exif2 = Image.Exif()
    exif2[0x0131] = "Adobe Photoshop 25.0"
    Image.new("RGB", (256, 192), (80, 80, 80)).save(target / "edited.jpg", exif=exif2.tobytes())

    print(f"样本已生成：{target.resolve()}")
    for item in sorted(target.iterdir()):
        print(" -", item.name)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_samples")
