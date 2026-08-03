"""L01 MOD-03 course-roster（L1 终端叶子）：CMP-MEMBERSHIP-VERIFIER + CMP-COURSE-ROSTER-ADMIN。Phase 2 (W1) 实现。

边界（child-handoff §2）：
- 继承契约：CT-003（VERIFIER）、CT-013（ADMIN）、FLOW-011（ADMIN，无网络契约）。
- 子级端口：CP-ROSTER-QUERY、CP-COURSE-ENDTIME（模块内只读，见 admin.py）。
- 不消费/不发布任何事件；不缓存校验通过结论（REQ-006 / LCD-002）。
"""
