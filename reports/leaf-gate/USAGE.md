# Leaf Gate v2

Leaf Gate is the design workflow's final pre-coding gate. It first verifies that Mocktest is fully complete and, when defects occurred, that Architecture was changed and affected testcases were revalidated. Only then does it decide whether to keep decomposing or start Vibe Coding.

## Contract and command

- Input: `leaf_gate_input.json` (`leaf-gate-input/v2`)
- Registry: `schemas/leaf-gate-run.schema.json`
- Runner: `scripts/run_leaf_gate.py`

```powershell
python scripts/run_leaf_gate.py <node-dir> --output-dir <output-dir>
```

The runner is read-only with respect to the node directory. It writes only the fixed five-file output bundle to the explicit output directory.

## Routing

```text
Mocktest PASS + complete evidence
  -> Leaf admission
  -> CONTINUE_LAYERING (back to PRD/Architecture decomposition)
     or STOP_LAYERING (Vibe Coding)

Mocktest WARNING/FAIL/BLOCKED
  -> Architecture repair
  -> affected-testcase revalidation
  -> complete Mocktest publication
  -> Leaf admission retry

Mocktest execution/audit/publication error
  -> validation evidence repair
  -> Mocktest rerun
  -> Leaf admission retry
```

See `SKILL.md` for the operating protocol and `references/pressure_scenarios.md` for acceptance cases.
