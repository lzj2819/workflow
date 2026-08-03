"""tutor_shared：DU-2/DU-3 共享平台层（配置、日志、metrics、健康、Outbox、租约）。

仅 Integration Owner 维护；叶子可消费公共接口但不得修改本包。
第三方依赖为零（stdlib）；生产适配（SQLAlchemy/psycopg）在各 DU 内按 DD 落地。
"""

__version__ = "0.1.0-phase1"
