"""readiness / liveness 健康检查原语。

- liveness：进程存活，永远 ok；
- readiness：逐项依赖检查（db、contracts_registry、storage_dir……），
  任一项 fail 则整体 not_ready；检查项由各 DU 注册。
HTTP 绑定（/health/live、/health/ready）随 L09 SI-API 落地；此处为纯函数。
"""
from __future__ import annotations

from typing import Callable

CheckFn = Callable[[], tuple[bool, str]]


def liveness() -> dict:
    return {"status": "ok"}


def readiness(checks: dict[str, CheckFn]) -> dict:
    results: dict[str, dict] = {}
    ready = True
    for name, check in checks.items():
        try:
            ok, detail = check()
        except Exception as exc:  # 检查本身失败同样视为未就绪
            ok, detail = False, f"check raised: {exc!r}"
        results[name] = {"status": "ok" if ok else "fail", "detail": detail}
        ready = ready and ok
    return {"status": "ready" if ready else "not_ready", "checks": results}
