# Entity Registry Corrections and One-Time Migration

This release replaces method-name inference with a reviewed OpenAPI and SDK
catalog for the SDK versions pinned in `pyproject.toml`. Existing entity aliases
remain accepted during ZTF 2.x and emit a deprecation warning. Incorrect custom
operation owners and false CRUD forms emit an actionable warning and are
rejected.

The optional migration described here applies only to this registry correction.
It is not a general version-to-version migration framework.

## Removed resources

`consistency_group` is not in the public 7.5.1 APIs ZTF uses. There is no
automatic move to Protection Policy consistency rules. Remove those resources
from `input.yml` and state before upgrading from 2.0.0, or stay on 2.0.0.

## Entity aliases

The following released names resolve to the canonical name on the right:

- `aiops_scenario` -> `capacity_planning_scenario`
- `aiops_sources_v4` -> `aiops_stats_source`
- `bgp_session_bgp_route_route` -> `bgp_session_route`
- `category_mapping` -> `directory_server_category_mapping`
- `ds_category_mapping` -> `directory_server_category_mapping`
- `cluster_data_store` -> `cluster_datastore`
- `licensing_license_recommendation` -> `licensing_recommendation`
- `lifecycle_license_recommendation` -> `lifecycle_recommendation`
- `source_entity_descriptors_v4` -> `aiops_stats_entity_descriptor`
- `source_entity_metrics_v4` -> `aiops_entity_stats`
- `source_entity_types_v4` -> `aiops_stats_entity_type`
- `task` -> `prism_task`

`category_mapping` and `ds_category_mapping` were two partial views of one
persistent Microseg resource. Collection create/list and item
get/update/delete use the same `CategoryMapping` model and
`DirectoryServerConfigsApi`. The canonical name is therefore
`directory_server_category_mapping`, and both released names remain aliases.

Two additional corrections are recorded for Files:

- `file_server_emailconfig_email_config` -> `file_server_email_config`
- `file_server_license_recommendation` -> `file_server_recommendation`

These Files names render only when `ntnx-files-py-client` can be installed with
the complete pinned SDK set. Files remains unavailable in this release because
its published `certifi` constraint conflicts with the other SDK dependencies.

## Corrected operation owners

Custom operations are stateless. Their old owners do not require state
migration, but the old invocation is rejected so that configurations cannot
continue to encode the wrong resource relationship.

- `cluster.add_snmp_transport` or `cluster.add_transports` ->
  `cluster_snmp_config.add_transports`
- `cluster.remove_snmp_transport` or `cluster.remove_transports` ->
  `cluster_snmp_config.remove_transports`
- `cluster_snmp_status.update_snmp_status` or
  `cluster_snmp_status.update_status` ->
  `cluster_snmp_config.update_status`
- `disk_led_state.update_disk_led_state` or
  `disk_led_state.update_led_state` ->
  `clustermgmt_disk.update_led_state`
- `user_state.update_user_state` or `user_state.change_state` ->
  `user.change_state`
- `manage_alert.manage_alert` -> `alert.manage_alert`
- `bridge.migrate_bridge` or `bridge.migrate` ->
  `virtual_switch.migrate`
- `domain_manager_backup_target.restore` ->
  `restore_source_restore_point.restore`
- `vm.assign_ip_by_id` or `vm.assign_ip` -> `vm_nic.assign_ip`
- `vm.release_ip_by_id` or `vm.release_ip` -> `vm_nic.release_ip`

The catalog stores exact OpenAPI operation IDs and the API class for each
operation. ZTF no longer reconstructs operation IDs from Python method names or
assumes that every operation uses the lifecycle entity's API class.

## Corrected lifecycle forms

The following released lifecycle forms represented actions rather than
persistent CRUD:

- `cluster_snmp_status.update` -> operation
  `cluster_snmp_config.update_status`
- `disk_led_state.update` -> operation
  `clustermgmt_disk.update_led_state`
- `user_state.update` -> operation `user.change_state`
- `entity_sync_policy.create` -> operation
  `entity_sync_policy.sync_entity`
- `file_server_infected_file.create` -> operation
  `file_server_infected_file.fix_infected_file`

The Files action remains unavailable with the Files SDK exclusion. If managed
state exists for `entity_sync_policy` while its false create form is present,
the migrator stops for manual review because the state entry may represent a
real imported policy.

`addDisk` is the inverse correction: it creates a persistent
`clustermgmt_disk`, so `clustermgmt_disk.create` remains supported.

## Dry-run migration

Entity aliases can remain in place. Run the migrator only if you want to update
configuration and state to canonical names or convert rejected legacy forms.

```bash
ztf migrate entity-registry \
  --input config/input.yml \
  --state state.yml
```

Dry-run is the default. When changes are found, it leaves both originals
untouched and writes:

- `config/input.entity-registry-migrated.yml`
- `state.entity-registry-migrated.yml`
- `config/entity-registry-migration-report.json`

The report records source hashes and every applied transform. YAML comments and
formatting are not preserved; review semantic changes in the sibling files.

## Write migration

After reviewing the dry-run output:

```bash
ztf migrate entity-registry \
  --input config/input.yml \
  --state state.yml \
  --write
```

Write mode:

1. acquires the state lock;
2. verifies that neither source changed after inspection;
3. creates `*.pre-entity-registry-migration.bak` backups;
4. validates and atomically replaces both YAML files;
5. restores both originals if either replacement fails.

The command refuses to overwrite a prior one-time backup. It also stops before
writing on conflicting resource-name merges, unsupported parameters, Files
forms, or state that cannot be proven synthetic.

After a successful write, run:

```bash
ztf refresh
ztf plan
```

Review the refreshed state and the complete plan before applying any
infrastructure change.
