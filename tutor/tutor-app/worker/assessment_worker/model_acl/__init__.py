"""MODEL-SERVICE-ACL（ICT-004，T-B02a）：可替换的模型调用防腐层。

边界（KD-001 / DD-009 / 任务卡）：
- 出站数据最小化校验（复用 model_provider.validate_request，禁业务标识）；
- 单次调用 ≤3 分钟预算守卫（时钟可注入，NFR-003）；
- 应答 CT-010 response schema 校验（复用 L12 validator）；
- 错误三分类：MODEL_TIMEOUT / MODEL_ERROR / INVALID_RESPONSE_SCHEMA
  （AclError 携带稳定 code，与 L03 ERROR_TAXONOMY / L12 MODEL_ERROR_KINDS 一致）；
- 本包只提供 fake 适配器：不接真实供应商、不配置密钥、不发任何网络请求、
  不外发材料或业务标识。
"""
from assessment_worker.model_acl.acl import ModelServiceAcl
from assessment_worker.model_acl.errors import (
    ACL_ERROR_CODES,
    ERROR_INVALID_RESPONSE_SCHEMA,
    ERROR_MODEL_ERROR,
    ERROR_MODEL_TIMEOUT,
    AclError,
)
from assessment_worker.model_acl.fake_adapter import FakeVendorAdapter

__all__ = [
    "ACL_ERROR_CODES",
    "ERROR_INVALID_RESPONSE_SCHEMA",
    "ERROR_MODEL_ERROR",
    "ERROR_MODEL_TIMEOUT",
    "AclError",
    "FakeVendorAdapter",
    "ModelServiceAcl",
]
