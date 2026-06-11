# v2.0.0

ZTF 2.0.0 is a ground-up rewrite using the Nutanix v4 API Python SDK. The legacy
v2 / v3 / Foundation Central / NCM-Calm / NDB workflows from the 1.x line
are not yet ported (see [Migrating from ZTF 1.x](../../README.md#migrating-from-ztf-1x)
in the project README); 2.x establishes the new declarative,
multi-domain, plan-and-apply foundation.

## What's New

### Framework Rewrite

- New declarative configuration model: `input.yml` (resources & data
  sources) + `global.yml` (SDK / connection settings).
- New `ztf` Click CLI replacing the legacy `python main.py --workflow`
  invocation. Commands: `init`, `plan`, `apply`, `refresh`, `destroy`,
  `import`, `examples`, `repl`.
- Multi-domain orchestration: a single run can target many Prism
  Centrals in parallel, each with its own data sources, resources,
  and credentials.
- Dependency resolution: automatic topological ordering via
  interpolation analysis (`{resource_name.extId}`,
  `{domain.resource.field}`) plus explicit `depends_on`.
- State management: YAML state file with advisory file locking,
  automatic backups, and incremental writes.
- Auto-refresh: `plan`, `apply`, and `destroy` reconcile state with
  live infrastructure first; `--no-refresh` and `--strict` available
  for CI flows.
- Confirmation prompt before `apply` / `destroy`; `--auto-approve`
  for trusted CI/CD.
- Post-apply summary with created / updated / deleted / failed counts.

### v4 SDK Coverage

- 16 Nutanix v4 namespaces wired through `ntnx-*-py-client` packages:
  `clustermgmt`, `networking`, `prism`, `vmm`, `iam`, `volumes`,
  `microseg`, `dataprotection`, `monitoring`, `lifecycle`, `aiops`,
  `security`, `licensing`, `objects`, `opsmgmt`, `datapolicies`,
  `multidomain`.
- Schema negotiation: per-PC-version request body filtering driven by
  `multi_namespace_compatibility_map.json` so the same `input.yml`
  works across PC minors that ship different namespace versions.
- ETag / `If-Match` round-trip handled automatically via SDK reserved
  fields and a curated 268-entity `etag_required` map.
- `NTNX-Request-Id` auto-injection on every mutation (SDK-level).

### Plan / Apply Lifecycle

- Field-level diff output in `plan` showing exactly which fields will
  change on update.
- Plan-file workflow: `ztf plan --out plan.json` writes a canonical
  plan; `ztf apply --plan plan.json [--force]` replays it with hash
  verification to guarantee plan/apply consistency.
- Selective destroy via `--target` (repeatable).
- Cross-domain reverse-wave destroy: dependent domains tear down
  before the domains they reference.
- `--strict` makes refresh errors a hard failure (CI-friendly).

### Configuration Surface

- Variables and var-files with multi-source override precedence.
- Auto-loaded variable files: `ztfvars.yml` and `*.auto.ztfvars.yml`.
- Dynamic resources: `for_each` expansion plus the new `count: N`
  sugar (desugars to `for_each: {str(i): i}` with `each.index`).
- Lifecycle rules: `prevent_destroy`, `ignore_changes`,
  `create_before_destroy` (beta).
- Data sources: read-only lookups of existing infrastructure with
  filter support; resolved at apply time.
- Outputs section with YAML / JSON file export via `--output-file`.
- User-defined `{fn.*}` functions (`functions.py`) for computed
  values, templates, and base64 encoding.
- Interpolation tokens: `{var.name}`, `{each.key}`, `{each.value}`,
  `{each.index}`, `{fn.name(args)}`, `{data.entity.name.field}`,
  `{resource_name.extId}`, `{domain.resource.field}`.

### Import & Examples

- `ztf import <resource> <domain>` brings existing infrastructure under
  state with a suggested config snippet printed for the user.
- `ztf import --file <manifest>` for bulk import.
- `ztf examples` auto-generates per-entity YAML examples and Markdown
  reference docs (field descriptions, enum values, version
  availability) under `examples/` plus a starter `functions.py`.
- `ztf repl` opens a read-only Python REPL with data sources loaded
  for ad-hoc value discovery.

### Operational Improvements (Phase A–E hardening)

Drop-in fixes from the `ztf-2.0-rc` branch — no breaking changes:

- Sub-entity updates correctly resolve referenced parent ext-ids and
  dispatch the right SDK method, fixing update drift on nested
  resources.
- `run_results/` resolves relative to the invoking workspace instead
  of the package install path.
- Deepcopy guard prevents mutation of cached entity payloads across
  repeated plan / apply invocations.
- Entity cache keys use tuple composition instead of string
  concatenation, eliminating cross-entity cache-key collisions.
- Deep structural comparison rewritten from quadratic
  match-and-delete to a linear multiset freeze; significantly faster
  `plan` on large states.
- Internal tech-debt cleanup in `provider.py` and
  `entity_handler.py`.

### Security

- `setuptools.packages.find` restricts wheel contents to the `ztf*`
  namespace, preventing `tests/`, `scripts/`, `examples/`, and
  `workflow/` from shipping as importable top-level packages on
  install.
- License switched from MIT (1.x) to Apache-2.0; see `LICENSE.txt`
  and `NOTICE`.

### Tooling

- Python 3.10, 3.11, 3.12, and 3.13 supported.
- Packaged via `pyproject.toml` (legacy `setup.py` removed); managed
  with `uv` and published to PyPI as `nutanix-ztf`.
- Multi-stage `Dockerfile` shipping a `runtime` image and a
  `wheels-export` target for dark-site offline installs.
- New CI surface: `ci.yml`, `publish.yml`, `functional-tests.yml`,
  `black-duck.yml`. Linting & formatting via `ruff`, type checking
  via `mypy`, security scanning via `bandit`.

## Known Limitations

- Nutanix Files APIs not supported due to an upstream package
  dependency conflict; tracking with Nutanix.
- `update`, `delete`, `create_before_destroy`, `operations`, and
  `destroy` are functional but **beta** — always run `ztf plan`
  before `ztf apply` and review the diff.
- Legacy 1.x feature surfaces (Foundation Central imaging, Prism
  Element v2 operations, Pod / pod-block conceptual workflows, NCM /
  Calm DSL workloads, NDB, NKE / Karbon, legacy script-based Objects
  flow) are **not yet ported**. Use the
  [`1.x` branch](https://github.com/nutanixdev/zerotouch-framework/tree/1.x)
  (last release `v1.5.2`) until parity lands. See
  [Migrating from ZTF 1.x](../../README.md#migrating-from-ztf-1x).

## Migration

Anyone tracking `nutanixdev/zerotouch-framework@main` on a pinned
SHA will see a large delete-and-rewrite as 2.0.0 ships:
`framework/`, `calm-dsl-bps/`, `calm-whl/`, `requirements/`,
`dev-setup-README.md`, `setup.py`, `main.py`, and
`config/example-configs/` are removed; the new tree is rooted at the
`ztf/` Python package plus `pyproject.toml`. Pin to `v1.5.2` or the
`1.x` branch if you need the legacy surfaces. Forward parity work is
ongoing.
