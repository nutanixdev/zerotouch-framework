# Changelog

All notable changes to ZTF are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-04-17

Pre-GA hardening release covering Phase A-E review items from the `ztf-2.0-rc`
branch. No breaking changes; all fixes are drop-in compatible with 2.0.0.

### Added

- Count-style iteration: `count: N` sugar desugars to `for_each: {str(i): i}`
with `each.index` token support (Phase E1).
- Plan-file workflow: `ztf plan --out <file>` writes a canonical JSON plan and
`ztf apply --plan <file> [--force]` replays it with hash verification to
guarantee plan/apply consistency (Phase E2).
- Destroy cross-domain reverse waves: `destroy` now walks the domain dependency
graph in reverse topological order so dependent domains tear down before
their providers (Phase E3).

### Changed

- Sub-entity updates correctly resolve referenced parent ext-ids and dispatch
the right SDK method, fixing update drift on nested resources (Phase A).
- `run_results` directory now resolves relative to the invoking workspace
instead of the package install path (Phase C).
- Deep structural comparison rewritten from quadratic match-and-delete to a
linear multiset freeze, significantly speeding up `plan` on large states
(Phase E5).

### Fixed

- Deepcopy guard prevents mutation of cached entity payloads across plan/apply
invocations (Phase B).
- Entity cache keys use tuple composition instead of string concatenation,
eliminating a class of cross-entity cache-key collisions (Phase E4).
- Internal tech-debt cleanup in provider and entity handler (Phase D).

### Security

- `setuptools.packages.find` now restricts wheel contents to the `ztf*`
namespace, preventing `tests/`, `scripts/`, `examples/`, and `workflow/`
from shipping as importable top-level packages on install.

## [2.0.0-b1] - 2026-03-23

### Added

- Multi-domain orchestration across Nutanix Prism Central instances.
- Declarative YAML configuration with `input.yml` and `global.yml`.
- CLI commands: `init`, `plan`, `apply`, `refresh`, `destroy`, `import`, `examples`, `repl`.
- Automatic dependency resolution via interpolation analysis and `depends_on`.
- State management with advisory file locking, automatic backups, and incremental writes.
- Auto-refresh of state before `plan` and `apply` (with `--no-refresh` and `--strict` flags).
- Interactive confirmation prompt before `apply` and `destroy` (`--auto-approve` for CI/CD).
- Field-level diff output in `plan` showing exactly which fields changed.
- Variables and var-files with multi-source override precedence.
- Auto-loaded variable files: `ztfvars.yml` and `*.auto.ztfvars.yml`.
- Dynamic resources via `for_each` expansion.
- Lifecycle rules: `prevent_destroy`, `ignore_changes`, `create_before_destroy`.
- Data sources for read-only lookups of existing infrastructure.
- Schema negotiation for version-aware request body filtering across PC versions.
- Single and bulk `import` with suggested config snippet generation.
- Outputs section with YAML/JSON file export via `--output-file`.
- Selective destroy with `--target` flag.
- Auto-generated per-entity YAML examples and Markdown reference docs.
- Read-only Python REPL with data sources loaded (`ztf repl`).
- Post-apply summary with created/updated/deleted/failed counts.
- Support for Python 3.10, 3.11, 3.12, and 3.13.
- 16 Nutanix v4 SDK namespace integrations.

### Known Limitations

- Nutanix Files APIs not supported due to upstream package dependency conflict.
- `update`, `delete`, `create_before_destroy`, `operations`, and `destroy` are beta.

