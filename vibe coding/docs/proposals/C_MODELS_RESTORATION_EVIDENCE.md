# C models restoration evidence

Base: `verilayer/a-contract-integration@3696874`
Candidate scope: only `mocktest/src/mock_framework/models/` and this evidence
record. No Gate, Contract, Adapter, Leaf, Coding, Tutor, or strict-run artifact
is changed.

## Controlled-source status

The controlled source is not auditable in this session. Every controlled-source
comparison is therefore `SOURCE_UNAVAILABLE`; this record makes no raw-source
`MATCH` claim. The table instead reconciles current checkout bytes, the Git
blob bytes, and CRLF-to-LF normalized bytes. A reconciliation match is not a
controlled-source match.

| File | Controlled source | Checkout raw SHA-256 | Git blob SHA-256 | LF-normalized SHA-256 | Reconciliation result |
|---|---|---|---|---|---|
| `__init__.py` | SOURCE_UNAVAILABLE | `e30bb2971a7c1420e6a4e932c039a6cea3127b1358e02d6dd4d545843e53a72a` | `23258870976f429ab0dc56c48eb0a47a3e776c79876b2fae860bc408066f2007` | `23258870976f429ab0dc56c48eb0a47a3e776c79876b2fae860bc408066f2007` | CHECKOUT-LF/GIT-BLOB MATCH |
| `arch.py` | SOURCE_UNAVAILABLE | `e38d81da43fb2d9bb818a0e92b375c0600cde95d6f9955e268ae4ffcdddc576b` | `8be5455f0ce5bba41d7e1743b01555a37b81de64398dd02b60e19c3b379673c9` | `8be5455f0ce5bba41d7e1743b01555a37b81de64398dd02b60e19c3b379673c9` | CHECKOUT-LF/GIT-BLOB MATCH |
| `gap.py` | SOURCE_UNAVAILABLE | `ad93888257f3e5db8a48d8d6977128f2806b0477df9917b52af5485fce17bc77` | `bf953d3d80b945320c0ef52889e8d61b45cc2cc5b2e3d994d6ac8c471b969ce3` | `bf953d3d80b945320c0ef52889e8d61b45cc2cc5b2e3d994d6ac8c471b969ce3` | CHECKOUT-LF/GIT-BLOB MATCH |
| `gherkin.py` | SOURCE_UNAVAILABLE | `7dc008b5e76b6578e258153d0e3c54ca1755743a48bbea031ab91764b430f87e` | `a429ce1e444d46c9d97c1f39e10d72f7f84782ed5c0cd5ebdf23a422b949bc19` | `a429ce1e444d46c9d97c1f39e10d72f7f84782ed5c0cd5ebdf23a422b949bc19` | CHECKOUT-LF/GIT-BLOB MATCH |
| `layer.py` | SOURCE_UNAVAILABLE | `2164b0112d900361155ba88118597f2bbd23bc4d00598a81a924cf09d9616431` | `08ac1eb874171177330e288691cc1d70e0234f26ada3cb0ffd774881b8e5f1f0` | `08ac1eb874171177330e288691cc1d70e0234f26ada3cb0ffd774881b8e5f1f0` | CHECKOUT-LF/GIT-BLOB MATCH |
| `loader.py` | SOURCE_UNAVAILABLE | `98fd36398f9d26e81025bc2f5c1c7bbeeb5c6ec977bb754a32affdd80bb36bd5` | `b2421a4775ff0a4c01d5084af0c2985d396f2038cfdcd985eb3be9bedb85cce6` | `b2421a4775ff0a4c01d5084af0c2985d396f2038cfdcd985eb3be9bedb85cce6` | CHECKOUT-LF/GIT-BLOB MATCH |
| `modification.py` | SOURCE_UNAVAILABLE | `1b6d5cacd5298051e6c8d372a10df0231d62b765cc332c56543d9502db065fe4` | `81fd69feaebb454418c4a13324752e9ac8638d3ca2f16e4c96ced05bad7065a4` | `81fd69feaebb454418c4a13324752e9ac8638d3ca2f16e4c96ced05bad7065a4` | CHECKOUT-LF/GIT-BLOB MATCH |
| `simulator.py` | SOURCE_UNAVAILABLE | `88710d7477e6bb2c8d23b0afcb49f0af470ca826ad8fc885ac77bedbde7f0a45` | `c004eccf5652f4c3dd34c7004341a956cd09697d84f9d9d0e07eeebb4f80099c` | `c004eccf5652f4c3dd34c7004341a956cd09697d84f9d9d0e07eeebb4f80099c` | CHECKOUT-LF/GIT-BLOB MATCH |
| `validator.py` | SOURCE_UNAVAILABLE | `00d4122f426e049dfbc6357a45a2c0a3af439164892e3d0f5010c29e5b6f7125` | `d7f1316e29b7ed8534ba555dd6ac19a145b0378011feda7e58e8bbad529e18c8` | `d7f1316e29b7ed8534ba555dd6ac19a145b0378011feda7e58e8bbad529e18c8` | CHECKOUT-LF/GIT-BLOB MATCH |

## Validation boundary

The candidate must run these checks after commit:

1. `import mock_framework.models`
2. `import mock_framework.models.validator`
3. `mocktest/.agents/skills/validate-arch/main_session_strict_driver.py --help`

Their exit codes prove only import/CLI reachability. They do not establish
strict, Mocktest semantic, Leaf, Coding, or downstream-gate PASS.

## Validation record

At candidate commit `dc1e0efe1ac9e3137ca78632e81b4e165af53480`, with
`PYTHONPATH=mocktest/src` and the locally available dependency-complete Python:

| Command | Exit code | Interpretation |
|---|---:|---|
| `python -c "import mock_framework.models"` | 0 | package import reachable |
| `python -c "import mock_framework.models.validator"` | 0 | validator import reachable |
| `python mocktest/.agents/skills/validate-arch/main_session_strict_driver.py --help` | 0 | driver help reachable |
