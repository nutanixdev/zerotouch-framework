# v2.1.0

ZTF 2.1.0 aligns the framework with Nutanix 7.5.1 APIs and brings
Foundation Central imaging and cluster create into the 2.x plan-and-apply
model.

Most 2.0.0 `input.yml` files keep working. See
[Upgrade notes](#upgrade-notes) before you upgrade.

## What's New

- Data sources can reference other data sources.
  [Data Sources](../../docs/configuration-reference.md#5-data-sources)
- ZTF adds Prism Element cluster-local helpers: `eula_pe`, `ad_server_pe`,
  `role_mapping_pe`, `open_replication_ports`, and `ha_reservation`.
  [Custom PE-Ops Helper Entities](../../docs/advanced-topics.md#5-custom-pe-ops-helper-entities)
- Foundation Central 1.11 can image and create HCI clusters
  (`fc_v1_imaging`, `fc_v1_cluster`).
  [FC 1.11 — HCI clusters](../../docs/advanced-topics.md#fc-111--hci-clusters)
- Foundation Central 2.2 can create compute-only clusters with external
  storage (`fc_create_cluster`).
  [FC 2.2 — compute-only clusters with external storage](../../docs/advanced-topics.md#fc-22--compute-only-clusters-with-external-storage)
- The lifecycle namespace is the Prism Central 7.6 release
  (`ntnx-lifecycle-py-client` 4.3.1). This release adds its entities,
  and multi-domain registration (`location`, `registered_domain`,
  `local_domain`).
  [Foundation Central Helper Entities](../../docs/advanced-topics.md#6-foundation-central-helper-entities),
  [Domain Configuration](../../docs/getting-started.md#domain-configuration)
- Entity names follow the 7.5.1 public API. Some 2.0.0 headings remain
  as aliases, and a few operations move to the resource that owns them.
  [Entity Registry Corrections and One-Time Migration](../../docs/entity-registry-migration.md)
- `ztf repl` `list()` and `get()` now use the same argument names as YAML
  data sources.
  [ztf repl](../../docs/configuration-reference.md#ztf-repl)
- Apply logs Prism Central subtasks while it waits, and `state.yml` is
  replaced atomically.
  [Logging and Audit](../../docs/advanced-topics.md#2-logging-and-audit),
  [State Management](../../docs/configuration-reference.md#11-state-management)
- Nutanix v4 SDK packages are pinned to the current 7.5.1 releases.
  The lifecycle namespace is the Prism Central 7.6 release.
  [Schema Negotiation](../../docs/configuration-reference.md#14-schema-negotiation)
- `refresh` and `import` omit server-managed fields, and generated
  examples place extra method parameters under `params:`.
  [ztf refresh](../../docs/configuration-reference.md#ztf-refresh),
  [Using Example Configurations](../../docs/configuration-reference.md#15-using-example-configurations)

## Upgrade notes

1. **`consistency_group` is removed.** Those endpoints are not in the
   public 7.5.1 APIs. Remove the resources from `input.yml` and state
   before upgrading, or stay on 2.0.0.
   [Removed resources](../../docs/entity-registry-migration.md#removed-resources)
2. **Operations declared on the wrong resource are rejected.**
   Move each operation to the resource that provides it. Edit `input.yml`,
   or run `ztf migrate entity-registry` (dry-run by default), then
   `ztf refresh` and `ztf plan`.
   [Entity Registry Corrections and One-Time Migration](../../docs/entity-registry-migration.md)
