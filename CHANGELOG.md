# Changelog

All notable changes to ZTF are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [2.1.0] - 2026-09-17

7.5.1 alignment release. Most 2.0.0 configurations continue to work; see
**Deprecated** and **Removed** before upgrading.

### Added

- Python 3.14 support (3.10 through 3.14).
- Data-source interpolation: sources may reference other sources via
`{data.<entity>.<source>...}` or `depends_on`. Source names must be unique
within a domain.
- PE cluster-local helpers: `eula_pe`, `ad_server_pe`, `role_mapping_pe`,
`open_replication_ports`, `ha_reservation`.
- Foundation Central 1.11 HCI clusters (`fc_v1_imaging`, `fc_v1_cluster`).
- Foundation Central 2.2 compute-only clusters with external storage
(`fc_create_cluster`).
- Foundation Central helpers: `foundation_central_service`,
`generate_fc_api_key`, `update_cvm_foundation`, and `fc_v1_image_upload`.
- Prism Central 7.6 Lifecycle entities (`ntnx-lifecycle-py-client` 4.3.1):
claim tokens, images, nodes, discovered nodes, patched images, hardware
providers/connections/pools, and `foundation_central_config`. Other
namespaces stay on the 7.5.1 SDKs.
- Multi-domain entities: `location`, `registered_domain`, `local_domain`.
- `ztf migrate entity-registry` to rewrite config and state to canonical
entity names (dry-run by default; `--write` to apply).
- Apply progress logs Prism Central subtasks while waiting on long-running
operations.

### Changed

- Nutanix v4 SDK packages are pinned to the current 7.5.1 releases.
  The lifecycle namespace is the Prism Central 7.6 release.
  Schema negotiation still strips fields your Prism Central version does
  not support, so the same `input.yml` can target mixed PC minors.
- Several 2.0.0 entity headings still work and emit a deprecation warning.
  Prefer the canonical names going forward (old name → new name):
  - `aiops_scenario` → `capacity_planning_scenario`
  - `aiops_sources_v4` → `aiops_stats_source`
  - `bgp_session_bgp_route_route` → `bgp_session_route`
  - `category_mapping` / `ds_category_mapping` →
    `directory_server_category_mapping`
  - `cluster_data_store` → `cluster_datastore`
  - `licensing_license_recommendation` → `licensing_recommendation`
  - `lifecycle_license_recommendation` → `lifecycle_recommendation`
  - `source_entity_descriptors_v4` → `aiops_stats_entity_descriptor`
  - `source_entity_metrics_v4` → `aiops_entity_stats`
  - `source_entity_types_v4` → `aiops_stats_entity_type`
  - `task` → `prism_task`
- Custom operations that were attached to the wrong resource now run on
  the resource that actually owns them (for example SNMP transport add/
  remove on `cluster_snmp_config`, VM IP assign/release on `vm_nic`).
  See [Entity Registry Corrections](docs/entity-registry-migration.md).
- `ztf repl` `list()` and `get()` take the same argument names as YAML
  data sources (`filter`, `select`, `orderby`, `limit`, `page`). You can
  query an entity type that is not in the current `input.yml`; the REPL
  creates the client on first use.
- State is written to a temporary file and then replaced. A crash during
  serialization no longer leaves a truncated `state.yml`.

### Deprecated

- Old entity headings listed above remain accepted in 2.x with a warning.
  Plan to switch to the canonical names; `ztf migrate entity-registry`
  can rewrite them for you.
- These operation forms are **rejected** with a message that names the
  replacement. Update `input.yml` (or run the migrator) before apply:
  - `cluster.add_snmp_transport` / `cluster.add_transports` →
    `cluster_snmp_config.add_transports`
  - `cluster.remove_snmp_transport` / `cluster.remove_transports` →
    `cluster_snmp_config.remove_transports`
  - `cluster_snmp_status.update_status` →
    `cluster_snmp_config.update_status`
  - `disk_led_state.update_led_state` →
    `clustermgmt_disk.update_led_state`
  - `user_state.change_state` → `user.change_state`
  - `manage_alert.manage_alert` → `alert.manage_alert`
  - `bridge.migrate` → `virtual_switch.migrate`
  - `domain_manager_backup_target.restore` →
    `restore_source_restore_point.restore`
  - `vm.assign_ip` → `vm_nic.assign_ip`
  - `vm.release_ip` → `vm_nic.release_ip`
- These resource headings were actions, not persistent objects. Declare
  them as `operations` on the owning resource instead:
  - `cluster_snmp_status` update → `cluster_snmp_config.update_status`
  - `disk_led_state` update → `clustermgmt_disk.update_led_state`
  - `user_state` update → `user.change_state`
  - `entity_sync_policy` create → `entity_sync_policy.sync_entity`

### Removed

- `consistency_group` (not in public 7.5.1 APIs). Remove it from config and
state before upgrading, or stay on 2.0.0.

### Fixed

- `refresh` and `import` strip server-managed fields (`createTime`,
`ownerExtId`, `sizeBytes`, and similar) so they no longer appear as drift.
- Generated examples nest extra method parameters under `params:`, where
apply reads them; previously they were emitted as siblings of `body:` and
silently ignored.

### Known Limitations

- Nutanix Files APIs remain unavailable due to an upstream package
dependency conflict.
- `update`, `delete`, `create_before_destroy`, `operations`, and `destroy`
remain beta.

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

