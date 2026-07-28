"""RESULT-PUBLISHER（ICT-007，T-B02a）：CT-005 事件经 SQL Outbox 的发布端口。

语义：
- 以调用方注入的 SQLAlchemy Session 构造 SqlaOutboxStore（T-B01b）；
  enqueue 发生在 L03 终态事务内，本端口内部不 commit/rollback（KD-002：
  业务写入与 Outbox 行同一本地事务提交，事务边界归调用方）；
- CT-005 scored / scoring_failed 载荷形状与 L03 orchestrator 既有入队载荷
  完全一致（只读复用其常量与领域校验）；
- 投递确认语义同 T-B01b：fetch_due 认领为 delivering，消费方确认前不推进为
  confirmed；确认后经 mark_confirmed 落 confirmed，不再投递。
"""
from assessment_worker.result_publisher.publisher import ResultPublisher

__all__ = ["ResultPublisher"]
