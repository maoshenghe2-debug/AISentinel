"""AISentinel 错误码与退出码（统一契约）。

退出码：0 成功 · 1 可用但有缺失（doctor）· 2 用法错误 · 3 环境不满足 · 4 运行期失败。
错误码：``AS-E<NNN>``（现象 → 原因 → 建议动作）。
"""

from __future__ import annotations

EXIT_OK = 0
EXIT_CHECK_WARN = 1
EXIT_USAGE = 2
EXIT_ENV = 3
EXIT_RUNTIME = 4


class ASentinelError(Exception):
    """带错误码的业务异常（AS-E<NNN>）。"""

    def __init__(self, code: str, message: str, fix: str = ""):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.fix = fix
