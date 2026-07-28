"""Patch plan.json with manually extracted component cards and prompts."""
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
sys.path.insert(0, str(SCRIPT_DIR))

from run_subagent_skill import build_component_agent_prompt

work_dir = Path(os.environ.get('VALIDATE_ARCH_WORK_DIR', PROJECT_ROOT / '.work' / 'validate-arch' / 'interactive'))
plan_path = work_dir / 'plan_locked.json'
plan_source = work_dir / 'plan.json'
plan = json.loads(plan_source.read_text(encoding='utf-8'))

components = [
    {"name": "RetentionQueryAPI", "responsibility": "提供同步 REST API 供 AI Tutoring 查询原始图片/会话数据的保留状态（READABLE/EXPIRED/PURGED）。", "tech_stack": "Python FastAPI", "strict_agent_component": True},
    {"name": "TrainingUseControlAPI", "responsibility": "接收训练平台的数据使用授权请求，判断数据用途是否为模型训练并返回 ALLOWED/BLOCKED 决定。", "tech_stack": "Python FastAPI", "strict_agent_component": True},
    {"name": "ComplianceAuditAPI", "responsibility": "提供审计日志查询接口，供合规审计人员检索删除、访问拒绝、训练使用拦截等事件。", "tech_stack": "Python FastAPI", "strict_agent_component": True},
    {"name": "UpstreamEventConsumer", "responsibility": "订阅上游 Problem Intake / Tutoring Session 的 ImageUploaded / TutoringSessionCompleted 事件，创建保留策略。", "tech_stack": "Python Redis Streams consumer", "strict_agent_component": True},
    {"name": "RetentionScheduler", "responsibility": "消费 Redis Streams T+30 延迟消息（及 PostgreSQL 兜底轮询），触发保留期到期清理。", "tech_stack": "Python scheduler / cron", "strict_agent_component": True},
    {"name": "S3PurgeAdapter", "responsibility": "在保留期到期后调用 S3 接口物理清理原始图片对象。", "tech_stack": "Python S3 adapter", "strict_agent_component": True},
    {"name": "TrainingPlatformACL", "responsibility": "将训练平台的数据使用请求翻译为本模块统一语言，并调用 ComplianceRule 执行训练使用禁令。", "tech_stack": "Python ACL layer", "strict_agent_component": True},
    {"name": "RetentionPolicy Aggregate", "responsibility": "聚合根：管理保留策略生命周期（创建、过期、状态查询、数据清理协调），维护 expiration_time 与状态机。", "tech_stack": "Domain aggregate", "strict_agent_component": True},
    {"name": "ComplianceRule Aggregate", "responsibility": "聚合根：封装训练使用禁令等业务规则，判断数据用途是否被禁止。", "tech_stack": "Domain aggregate", "strict_agent_component": True},
    {"name": "AuditLog Aggregate", "responsibility": "聚合根：以追加只写方式记录所有删除、访问拒绝、训练使用拦截等合规审计事件。", "tech_stack": "Domain aggregate", "strict_agent_component": True},
    {"name": "AI Tutoring", "responsibility": "下游查询方：在答疑过程中查询原始图片和会话数据的保留状态。", "tech_stack": "External system", "strict_agent_component": True},
    {"name": "Training Platform", "responsibility": "下游被拦截方：请求将学生数据用于模型训练。", "tech_stack": "External system", "strict_agent_component": True},
    {"name": "Problem Intake", "responsibility": "上游事件发布方：在学生上传原始图片后发布 ImageUploaded 事件。", "tech_stack": "External system", "strict_agent_component": True},
    {"name": "Tutoring Session", "responsibility": "上游事件发布方：在答疑会话完成后发布 TutoringSessionCompleted 事件。", "tech_stack": "External system", "strict_agent_component": True},
    {"name": "S3 Object Storage", "responsibility": "外部对象存储：持久化原始图片文件。", "tech_stack": "AWS S3 / compatible", "strict_agent_component": True},
    {"name": "PostgreSQL", "responsibility": "外部关系数据库：持久化 retention_policies、compliance_rules、audit_events 状态。", "tech_stack": "PostgreSQL", "strict_agent_component": True},
    {"name": "Redis / Redis Streams", "responsibility": "外部缓存/队列：缓存保留状态、投递 T+30 延迟消息、事件总线。", "tech_stack": "Redis", "strict_agent_component": True},
]

data_flow = [
    {"from": "Problem Intake", "to": "UpstreamEventConsumer", "action": "event", "message": "ImageUploaded"},
    {"from": "Tutoring Session", "to": "UpstreamEventConsumer", "action": "event", "message": "TutoringSessionCompleted"},
    {"from": "UpstreamEventConsumer", "to": "RetentionPolicy Aggregate", "action": "call", "message": "CreateRetentionPolicy"},
    {"from": "RetentionPolicy Aggregate", "to": "Redis / Redis Streams", "action": "write", "message": "create delayed message"},
    {"from": "RetentionScheduler", "to": "Redis / Redis Streams", "action": "consume", "message": "delayed message"},
    {"from": "RetentionScheduler", "to": "RetentionPolicy Aggregate", "action": "call", "message": "MarkExpired"},
    {"from": "RetentionPolicy Aggregate", "to": "S3PurgeAdapter", "action": "call", "message": "DataPurged"},
    {"from": "S3PurgeAdapter", "to": "S3 Object Storage", "action": "delete", "message": "purge object"},
    {"from": "RetentionPolicy Aggregate", "to": "AI Tutoring", "action": "event", "message": "DataPurged"},
    {"from": "AI Tutoring", "to": "RetentionQueryAPI", "action": "call", "message": "CRT-API-001"},
    {"from": "RetentionQueryAPI", "to": "RetentionPolicy Aggregate", "action": "call", "message": "QueryRetentionStatus"},
    {"from": "Training Platform", "to": "TrainingUseControlAPI", "action": "call", "message": "CRT-API-002"},
    {"from": "TrainingUseControlAPI", "to": "TrainingPlatformACL", "action": "call", "message": "AuthorizeTrainingUse"},
    {"from": "TrainingPlatformACL", "to": "ComplianceRule Aggregate", "action": "call", "message": "EnforceTrainingUseProhibition"},
    {"from": "ComplianceRule Aggregate", "to": "AuditLog Aggregate", "action": "call", "message": "RecordAuditEvent"},
    {"from": "ComplianceAuditAPI", "to": "AuditLog Aggregate", "action": "call", "message": "QueryAuditTrail"},
    {"from": "RetentionPolicy Aggregate", "to": "PostgreSQL", "action": "write", "message": "write retention_policies"},
    {"from": "ComplianceRule Aggregate", "to": "PostgreSQL", "action": "write", "message": "write compliance_rules"},
    {"from": "AuditLog Aggregate", "to": "PostgreSQL", "action": "write", "message": "write audit_events"},
    {"from": "RetentionPolicy Aggregate", "to": "Redis / Redis Streams", "action": "read", "message": "cache retention status"},
    {"from": "ComplianceRule Aggregate", "to": "Redis / Redis Streams", "action": "read", "message": "cache rules"},
]

inbound_map = {}
outbound_map = {}
for step in data_flow:
    outbound_map.setdefault(step["from"], set()).add(step["to"])
    inbound_map.setdefault(step["to"], set()).add(step["from"])

constraints = [
    {"type": "rule", "description": "原始图片和会话数据保留期为上传成功时间 T 起 30 天", "target": "RetentionPolicy Aggregate", "value": "30 days"},
    {"type": "rule", "description": "T + 30 天 + 1 分钟时数据必须变为不可读取", "target": "RetentionPolicy Aggregate", "value": "T+30d+1m"},
    {"type": "rule", "description": "学生上传图片和会话数据不得用于模型训练", "target": "ComplianceRule Aggregate", "value": "prohibited"},
    {"type": "rule", "description": "删除、访问拒绝、训练使用拦截操作必须可审计", "target": "AuditLog Aggregate", "value": "auditable"},
]
nfrs = [
    {"id": "NFR-D001", "metric": "retention boundary precision", "threshold": 1.0, "unit": "minute"},
    {"id": "NFR-D002", "metric": "training data misuse prevention", "threshold": 100.0, "unit": "percent"},
]
state_machine = {
    "states": ["READABLE", "EXPIRED", "PURGED"],
    "transitions": [
        {"from": "READABLE", "to": "EXPIRED", "trigger": "RetentionPeriodExpired"},
        {"from": "EXPIRED", "to": "PURGED", "trigger": "ExecutePurge"},
    ],
}

cards = {}
for c in components:
    name = c["name"]
    outbound_names = sorted(outbound_map.get(name, set()))
    inbound_names = sorted(inbound_map.get(name, set()))
    outbound_interfaces = [{"name": n, "protocol": "data_flow", "contract": {}} for n in outbound_names]
    inbound_interfaces = [{"name": n, "protocol": "data_flow", "contract": {}} for n in inbound_names]
    relevant_constraints = [con for con in constraints if name.lower() in (con["target"] or "").lower() or name.lower() in con["description"].lower()]
    cards[name] = {
        "name": name,
        "component_kind": "component" if c.get("strict_agent_component", True) else "external",
        "strict_agent_component": c.get("strict_agent_component", True),
        "responsibility": c["responsibility"],
        "tech_stack": c.get("tech_stack"),
        "inbound_interfaces": inbound_interfaces,
        "outbound_interfaces": outbound_interfaces,
        "state_machine_subset": state_machine,
        "relevant_nfrs": nfrs,
        "relevant_constraints": relevant_constraints,
    }

component_prompts = {
    name: build_component_agent_prompt(card, data_flow, [c["name"] for c in components])
    for name, card in cards.items()
}

entry_updates = {
    "TC-COMPLIAN-001-001": "AI Tutoring",
    "TC-COMPLIAN-001-002": "AI Tutoring",
    "SCENARIO-002": "Training Platform",
}
for plan_item in plan["plans"]:
    tc_id = plan_item["test_case_id"]
    if tc_id in entry_updates:
        plan_item["entry_component"] = entry_updates[tc_id]
        plan_item["entry_action"] = "handle"
        plan_item["entry_confidence"] = "high"
        plan_item["entry_reason"] = "基于运行时架构图手工设置入口组件"

plan["component_cards"] = cards
plan["component_prompts"] = component_prompts
plan["component_prompt_mode"] = "embedded"

plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Updated {plan_path}: {len(cards)} components, {len(component_prompts)} prompts, {len(plan['plans'])} plans")
