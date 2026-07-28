"""DU-2 ASGI 应用装配（T-B03d 组合根挂载）。

create_app(settings=None, *, composition=None)：
- 挂载组合根全部 router（L09 multipart+JSON/auth-token/CT-002、L01 CT-003/CT-013、
  L14 CT-008、L15 CT-007、L16 CT-009、B03c CT-011、L17 SSR）；
- 平台面 /health/live、/health/ready（config/contracts/database/storage 四项检查，
  DB 检查直连组合根 engine）、/metrics；
- relay 驱动钩子：app.state.composition.relayer_tick()（进程内调度器/测试调用，
  不在请求路径上阻塞）。

uvicorn 目标：`uvicorn course_app.main:create_app --factory`。
"""
from __future__ import annotations


def _readiness_checks(composition) -> dict:
    """readiness 检查项：不泄露 secret 值，失败如实上报（不伪造 ok）。"""

    def _check_config() -> tuple[bool, str]:
        settings = composition.settings
        ok = bool(settings.database_url) and bool(settings.teacher_session_secret)
        return ok, "settings present" if ok else "missing database_url or teacher_session_secret"

    def _check_contracts() -> tuple[bool, str]:
        try:
            from course_app.contracts_registry import load_registry  # noqa: PLC0415

            registry = load_registry(composition.settings.contracts_dir)
        except Exception as exc:
            return False, f"contracts registry error: {exc}"
        return True, f"{len(registry)} contracts loaded"

    def _check_database() -> tuple[bool, str]:
        try:
            import sqlalchemy as sa  # noqa: PLC0415

            with composition.engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
        except Exception as exc:
            return False, f"database unreachable: {type(exc).__name__}"
        return True, "select 1 ok"

    def _check_storage() -> tuple[bool, str]:
        data_dir = composition.settings.data_dir
        return (True, "dir exists") if data_dir.exists() else (False, f"{data_dir} missing")

    return {
        "config": _check_config,
        "contracts": _check_contracts,
        "database": _check_database,
        "storage": _check_storage,
    }


def create_app(settings=None, *, composition=None):  # pragma: no cover - 需要 fastapi 运行时
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.responses import PlainTextResponse  # noqa: PLC0415

    from tutor_shared import health as shared_health  # noqa: PLC0415
    from tutor_shared.metrics import registry as metrics_registry  # noqa: PLC0415

    from course_app.composition import build_composition  # noqa: PLC0415
    from course_app.settings import Settings  # noqa: PLC0415

    settings = settings or Settings.from_env()
    comp = composition or build_composition(settings)

    import os  # noqa: PLC0415
    from contextlib import asynccontextmanager  # noqa: PLC0415

    @asynccontextmanager
    async def _lifespan(_app):
        # 进程内调度器：周期驱动 relayer_tick（Outbox 投递 + CT-004 confirmed 推进钩子），
        # 不在请求路径上阻塞；RELAY_TICK_INTERVAL_SECONDS=0 可关闭（单测/手工驱动）。
        import asyncio  # noqa: PLC0415

        from tutor_shared import logging as shared_logging  # noqa: PLC0415

        logger = shared_logging.get_logger("course_app.relay_scheduler")
        interval = float(os.environ.get("RELAY_TICK_INTERVAL_SECONDS", "1.0"))
        task = None

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                try:
                    await asyncio.to_thread(comp.relayer_tick)
                except Exception as exc:  # tick 失败如实记录，下轮继续
                    logger.error("relayer_tick failed: %s: %s", type(exc).__name__, exc)

        if interval > 0:
            task = asyncio.create_task(_loop())
        try:
            yield
        finally:
            if task is not None:
                task.cancel()

    app = FastAPI(title="tutor course-app (DU-2)", version="0.1.0-du2", lifespan=_lifespan)
    app.state.composition = comp
    for router in comp.routers:
        app.include_router(router)

    @app.get("/health/live")
    def _live() -> dict:
        return shared_health.liveness()

    @app.get("/health/ready")
    def _ready() -> dict:
        return shared_health.readiness(_readiness_checks(comp))

    @app.get("/metrics", response_class=PlainTextResponse)
    def _metrics() -> str:
        return metrics_registry.render_text()

    return app


app = None  # uvicorn 目标：course_app.main:create_app --factory
