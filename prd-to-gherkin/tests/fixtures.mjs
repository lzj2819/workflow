export function readyPrd() {
  const requirements = [
    {
      id: 'REQ-NOTE-CREATE', type: 'functional', text: '用户可创建笔记', priority: 'Must Have',
      release_scope: 'current', scope_reason: null, requirement_kind: 'atomic', source_kind: 'explicit',
      evidence_refs: ['EVID-REQ-001'], parent_requirement_id: null,
      implementation_surfaces: ['API'], related_requirement_ids: [],
    },
    {
      id: 'NFR-NOTE-LATENCY', type: 'nfr', text: '创建请求满足时延目标', priority: null,
      release_scope: 'current', scope_reason: null, requirement_kind: 'atomic', source_kind: 'valid_derivation',
      evidence_refs: ['EVID-NFR-001'], parent_requirement_id: null,
      implementation_surfaces: ['API'], related_requirement_ids: ['REQ-NOTE-CREATE'],
    },
  ]
  const acceptanceContracts = [
    {
      id: 'AC-REQ-NOTE-CREATE-01', type: 'functional', verifies: ['REQ-NOTE-CREATE'], release_scope: 'current',
      actor: '已认证用户', preconditions: ['用户拥有有效会话', '标题不为空'], trigger: '用户提交创建笔记请求',
      response: ['系统保存笔记', '系统返回新笔记标识'], observable_oracles: ['查询该标识可获得相同标题'],
      boundaries: [{ condition: '标题长度等于允许上限', response: '系统保存笔记' }],
      exceptions: [{ condition: '标题为空', response: '系统拒绝请求且不保存笔记' }],
      population: null, measurement_start: null, measurement_end: null, unit: null, threshold: null,
      exclusions: [], pass_rule: null, evidence_refs: ['EVID-AC-001'],
    },
    {
      id: 'AC-NFR-NOTE-LATENCY-01', type: 'nfr', verifies: ['NFR-NOTE-LATENCY'], release_scope: 'current',
      actor: null, preconditions: [], trigger: null, response: [], observable_oracles: [], boundaries: [], exceptions: [],
      population: '有效创建笔记请求', measurement_start: '服务收到请求', measurement_end: '响应完整发送',
      unit: '毫秒', threshold: 'p95 <= 300', exclusions: ['客户端断开连接'],
      pass_rule: '测量样本的第95百分位不超过300毫秒', evidence_refs: ['EVID-AC-NFR-001'],
    },
  ]
  return {
    schema_version: '1.0', artifact_schema_version: 'prd/v3', run_id: 'run-001', project_id: 'notes',
    node_id: 'root', parent_node_id: null, artifact_id: 'PRD-NOTES-001', artifact_type: 'prd',
    created_at: '2026-08-02T00:00:00Z', generator: 'prd-generation', status: 'PASS', input_artifacts: [],
    requirement_ids: requirements.map((item) => item.id), prd_status: 'approved', mode: 'root', depth: 0,
    max_depth: 4, node_history: [], requirements: requirements.map((item) => item.id), section_order: [],
    payload: {
      document: {
        doc_id: 'notes-prd', title: '笔记服务', version: '1.0.0', author: 'product', priority: 'P0', tags: [],
        release_scope_frozen: true, ready_for_test_generation: true, oracle_blocked_count: 0,
        inheritance_complete: true, review_method: 'independent_agent', requirement_id_mapping: {},
      },
      problem_statement: {
        summary: '创建笔记', target_users: '用户', pain_points: '无法保存', desired_outcomes: '可靠保存',
        current_alternatives: [], assumptions: [],
      },
      scope: {
        product: 'notes', release: '1.0.0', current_release_boundary: 'create only', in_scope: ['create'],
        non_goals: [], dependencies: [], data_availability: [], retired_requirement_ids: [],
      },
      requirements,
      architecture_input_contract: {
        system_boundary: [], external_dependencies: [], data_and_storage_constraints: [],
        runtime_and_capacity_constraints: [], security_and_privacy_constraints: [], deployment_constraints: [],
        open_decisions: [],
      },
      success_metrics: [], acceptance_contracts: acceptanceContracts,
      oracle_coverage_ledger: requirements.map((item) => ({
        requirement_id: item.id, requirement_type: item.type, release_scope: 'current',
        acceptance_contract_ids: acceptanceContracts.filter((contract) => contract.verifies.includes(item.id)).map((contract) => contract.id),
        status: 'ready', reason: null,
      })),
      future_backlog_requirement_ids: [], risks: [], dependencies: [], blocking_questions: [],
      traceability: requirements.map((item) => ({
        requirement_id: item.id,
        acceptance_contract_ids: acceptanceContracts.filter((contract) => contract.verifies.includes(item.id)).map((contract) => contract.id),
        success_metric_ids: [], evidence_refs: item.evidence_refs,
      })),
      review: {
        method: 'independent_agent', status: 'PASS', reviewer: 'reviewer', model: 'model',
        reviewed_at: '2026-08-02T00:00:00Z', input_hash: 'hash', findings: [],
      },
    },
  }
}
