"""生成标识核验演示样本（合成数据，覆盖三态判定）。

用法：python scripts/make_label_samples.py [输出目录，默认 _samples/]
实现见 aisentinel.detect.samples.make_sample_set（与 demo 共用同一生成器）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aisentinel.detect.samples import make_sample_set  # noqa: E402

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("_samples")
    files = make_sample_set(out)
    print(f"已生成 {len(files)} 个标识核验样本 → {out}")
    for path in files:
        print(" ·", path.name)
