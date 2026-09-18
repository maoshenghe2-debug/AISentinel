"""标识核验演示样本生成（合成数据，供 demo / 脚本 / 测试复用）。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo

PNG_SAMPLES = {
    "ai_generated.png": {
        "text": {
            "parameters": "a cat wearing a spacesuit, steps: 20, sampler: Euler a, CFG scale: 7.0, Seed: 42, Model: sd_xl_base_1.0"
        }
    },
    "provider_labeled.png": {"text": {"Software": "即梦AI v2.1（生成合成内容）", "Creator": "Dreamina"}},
    "plain_photo.png": {"text": {}},
}


def _jpeg_inject(path: Path, *, comment: str | None = None, xmp: str | None = None) -> None:
    data = path.read_bytes()
    inject = b""
    if comment:
        payload = comment.encode("utf-8")
        inject += b"\xff\xfe" + (len(payload) + 2).to_bytes(2, "big") + payload
    if xmp:
        payload = b"http://ns.adobe.com/xap/1.0/" + xmp.encode("utf-8")
        inject += b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    if inject:
        path.write_bytes(data[:2] + inject + data[2:])


def make_sample_set(out_dir: Path | str) -> list[Path]:
    """生成演示样本集（4 个文件，覆盖三态判定）。返回生成的文件列表。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    for name, spec in PNG_SAMPLES.items():
        target = out / name
        image = Image.new("RGB", (256, 192), (40, 90, 140))
        info = PngInfo()
        for key, value in (spec.get("text") or {}).items():
            info.add_text(key, value)
        if name == "plain_photo.png":
            image.save(target)
        else:
            image.save(target, pnginfo=info)
        files.append(target)

    camera = out / "camera_photo.jpg"
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif[0x0110] = "Canon EOS R6"
    exif[0x0131] = "Ver1.00"
    Image.new("RGB", (256, 192), (140, 90, 40)).save(camera, exif=exif.tobytes())
    files.append(camera)

    reencoded = out / "reencoded.jpg"
    Image.new("RGB", (256, 192), (60, 60, 60)).save(reencoded)
    _jpeg_inject(reencoded, comment="CREATOR: gd-jpeg v1.0 (using IJG JPEG v62)")
    files.append(reencoded)

    return files
