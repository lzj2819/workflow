"""assessment_worker：DU-3 assessment-worker（MOD-04 assessment）。

独立部署单元；经 Outbox（数据库）消费 CT-004、发布 CT-005；经 ACL 调用外部模型（CT-010）。
"""

__version__ = "0.1.0-phase1"
