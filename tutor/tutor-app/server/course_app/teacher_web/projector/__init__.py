"""CMP-READMODEL-PROJECTOR 实现包（T-B03b / MOD-05 教师读模型投影）。

消费 CT-005/CT-006/CT-012/CT-014（Outbox，经 SI-RELAY handler 注册）+
M05-IC-05 复核模块内事件（ReviewEventPublisher 形状），维护 ST-READ-MODEL
读模型表与 projection_checkpoints（投影与位点同事务）；M05-IC-02 双侧面
（L15 query() / L16 group_view()）由 ProjectorReadModel 提供；CT-005 scored
经注入的 M05-IC-01（L14 create_review_record）幂等建复核记录；CT-012/CT-014
清除投影并登记墓碑（重放守卫：旧事件重放不重建已清除数据）。
"""
from .models import (
    Base,
    ProjectionCheckpoint,
    RmCourse,
    RmGroup,
    RmPurgeTombstone,
    RmStudent,
    RmSubmission,
)
from .projector import (
    OUTBOX_CONTRACTS,
    CreateReviewRecord,
    ProjectorValidationError,
    ReadModelProjector,
)
from .read_model import ProjectorReadModel

__all__ = [
    "Base",
    "CreateReviewRecord",
    "OUTBOX_CONTRACTS",
    "ProjectionCheckpoint",
    "ProjectorReadModel",
    "ProjectorValidationError",
    "ReadModelProjector",
    "RmCourse",
    "RmGroup",
    "RmPurgeTombstone",
    "RmStudent",
    "RmSubmission",
]
