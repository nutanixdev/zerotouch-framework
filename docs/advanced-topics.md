# ZTF Advanced Topics

Multi-environment workflows, logging, custom Python functions, PE-ops
helpers, and Foundation Central helpers.
For initial setup, see [Getting Started](getting-started.md).
For the full configuration reference, see
[Configuration Reference](configuration-reference.md).

---

## Table of Contents

- [1. Multi-Config and Multi-Environment Workflows](#1-multi-config-and-multi-environment-workflows)
- [2. Logging and Audit](#2-logging-and-audit)
- [3. Custom Functions](#3-custom-functions)
- [4. Interrupt Handling and Recovery](#4-interrupt-handling-and-recovery)
- [5. Custom PE-Ops Helper Entities](#5-custom-pe-ops-helper-entities)
- [6. Foundation Central Helper Entities](#6-foundation-central-helper-entities)

---

## 1. Multi-Config and Multi-Environment Workflows

### Separate Environments with Shared Variables

Use a base config with environment-specific variable files:

```bash
# Same input, different secrets per environment
ztf apply -i config/input.yml --var-file envs/dev-secrets.yml -s dev-state.yml
ztf apply -i config/input.yml --var-file envs/prod-secrets.yml -s prod-state.yml
```

### Multiple Input Files for Different Concerns

Split infrastructure by concern and manage independently:

```bash
# Network infrastructure
ztf apply -i configs/network.yml -s states/network-state.yml

# Compute infrastructure (depends on network being applied first)
ztf apply -i configs/compute.yml -s states/compute-state.yml

# Monitoring and policies
ztf apply -i configs/monitoring.yml -s states/monitoring-state.yml
```

### CI/CD Pipeline Example

```bash
# In your CI/CD pipeline -- use --strict to fail on stale state
ztf plan -i config/input.yml -s state.yml --var-file secrets.yml --strict

# If plan looks good, apply without prompt
ztf apply -i config/input.yml -s state.yml --var-file secrets.yml --auto-approve --strict
```

---

## 2. Logging and Audit

All operations are logged to `ztf.log` with automatic rotation (1 MB max,
10 backups). The log format includes timestamps, thread names (useful for
debugging parallel operations), module names, and line numbers:

```
2025-01-15 10:30:45 INFO [lab1-subnet-create:provider:123] Creating entity: subnet
```

Check this file for detailed error information and audit trails. Enable
debug logging by setting `debug: true` in `global.yml`.

Run results (success/failure per operation) are also written to
`ztf_run_results.json` for programmatic consumption.

During `ztf apply`, Prism Central task waits also log child subtasks as they
appear. Each child is fetched at most once. A failed child GET is logged
and skipped; it does not abort the parent wait. The apply still succeeds or
fails based on the parent task status.

---

## 3. Custom Functions

User-defined Python functions extend the interpolation engine with
computational capabilities.  Functions are referenced in YAML via the
`{fn.<name>(<args>)}` token syntax.

### Setup

Place a `functions.py` file alongside your `input.yml`.  ZTF automatically
discovers and loads it.  Every public function defined in the file becomes
available as a `{fn.*}` token.

```
my-project/
  input.yml
  functions.py        # auto-discovered
  state.yml
```

Alternatively, specify the path explicitly:

```bash
ztf plan --functions path/to/functions.py
```

A starter `functions.py` is generated when you run
`ztf examples`.  Copy it alongside your `input.yml` and customise
as needed.

### Writing Functions

Each public function (no leading underscore) becomes a `{fn.*}` token.
Private functions (`_helper`) and imported modules are excluded.

```python
# functions.py
import base64
from pathlib import Path


def pad(value: object, width: int = 4) -> str:
    """Zero-pad a numeric value to width digits."""
    return str(int(value)).zfill(int(width))


def b64encode(value: str) -> str:
    """Base64-encode a UTF-8 string."""
    return base64.b64encode(value.encode()).decode()


def read_lines(path: str) -> list[str]:
    """Read a file and return non-empty lines as a list."""
    return [l.strip() for l in Path(path).read_text().splitlines() if l.strip()]
```

### Usage in YAML

```yaml
resources:
  vm:
    "my-vm-{fn.pad(each.value.index, 4)}":
      for_each:
        vm1: { index: 1 }
        vm2: { index: 2 }
      body:
        name: "my-vm-{fn.pad(each.value.index, 4)}"
        guestCustomization:
          config:
            cloudInit:
              userData: "{fn.b64encode(fn.template(cloud-init.tpl))}"
```

Function arguments can be:

- **Literals**: `{fn.pad(1, 4)}` -- numbers and strings
- **Variable references**: `{fn.pad(var.index, 4)}`
- **for_each references**: `{fn.pad(each.value.idx, 2)}`
- **Nested function calls**: `{fn.b64encode(fn.pad(1, 4))}`

### Template Files

`fn.template(path)` is a built-in that reads a template file and resolves
`{token}` placeholders using the current interpolation context.  The
template uses the **same** syntax as `input.yml` -- no explicit variable
passing is needed:

```yaml
# cloud-init.tpl
#cloud-config
hostname: {var.vmName}-{fn.pad(each.value.index, 4)}
fqdn: {var.vmName}-{fn.pad(each.value.index, 4)}.{var.domain}
users:
  - name: nutanix
    ssh-authorized-keys:
      - {var.publicKey}
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
```

The template has access to all scopes: `{var.*}`, `{each.*}`, `{data.*}`,
and `{fn.*}`.

### Nested Function Resolution

Functions can be nested.  Inner functions resolve first (inside-out):

```yaml
# fn.template() resolves first, then fn.b64encode() encodes the result
userData: "{fn.b64encode(fn.template(cloud-init.tpl))}"
```

### Terraform Function Mapping

The table below shows how common Terraform functions map to ZTF user-defined
functions.

| Terraform | ZTF Equivalent | Notes |
|-----------|----------------|-------|
| `format("%04d", n)` | `{fn.pad(n, 4)}` | Zero-pad numeric values |
| `base64encode(s)` | `{fn.b64encode(s)}` | Base64 encoding |
| `base64decode(s)` | `{fn.b64decode(s)}` | Base64 decoding |
| `templatefile(path, vars)` | `{fn.template(path)}` | Context passed automatically |
| `file(path)` | `{fn.read_file(path)}` | Read file as string |
| `csvdecode(file(path))` | `{fn.read_lines(path)}` | Single-column data; write a custom function for multi-column CSV |
| `upper(s)` | `{fn.upper(s)}` | Uppercase conversion |
| `lower(s)` | `{fn.lower(s)}` | Lowercase conversion |
| `join(sep, list)` | `{fn.join(sep, a, b, ...)}` | Join values with separator |
| `try(expr, default)` | N/A | Use Python control flow in your function instead |
| `count` + `count.index` | `for_each` + `{fn.pad(each.value, N)}` | ZTF uses `for_each` maps with explicit indices |

### Dependency Management

User functions run in the same Python process as ZTF:

- **Stdlib modules** (`csv`, `json`, `base64`, `hashlib`, etc.) are always
  available -- they ship with Python.
- **Packages in ZTF's dependencies** (e.g. `pyyaml`) are available
  automatically.
- **Third-party packages** must be installed by the user in the same
  environment where ZTF runs:

```bash
uv pip install pandas   # Then import pandas in functions.py
```

If a package is missing, Python raises `ModuleNotFoundError` with a clear
message. ZTF does not auto-install packages.

### Error Handling

- If a function raises an exception, ZTF logs the error and treats the
  token as unresolved (left as-is in lenient mode, raises in strict mode).
- If a function name is not found in `functions.py`, the `{fn.*}` token
  is left unresolved.
- `fn.template(path)` logs a warning and returns unresolved if the
  template file does not exist.

### Built-In Functions Reference

| Function | Description | Example |
|---|---|---|
| `fn.pad(value, width)` | Zero-pad number to width | `{fn.pad(1, 4)}` -> `0001` |
| `fn.b64encode(value)` | Base64-encode string | `{fn.b64encode(hello)}` -> `aGVsbG8=` |
| `fn.b64decode(value)` | Base64-decode string | `{fn.b64decode(aGVsbG8=)}` -> `hello` |
| `fn.template(path)` | Render template with context (built-in) | `{fn.template(cloud-init.tpl)}` |
| `fn.read_file(path)` | Read file as string | `{fn.read_file(config.txt)}` |
| `fn.read_lines(path)` | Read file as list of lines | `{fn.read_lines(ips.txt)}` |
| `fn.upper(value)` | Convert to uppercase | `{fn.upper(hello)}` -> `HELLO` |
| `fn.lower(value)` | Convert to lowercase | `{fn.lower(HELLO)}` -> `hello` |
| `fn.join(sep, ...)` | Join values with separator | `{fn.join(-, a, b)}` -> `a-b` |

`fn.template` is a built-in handled by the ZTF engine.  All other functions
come from your `functions.py` file and can be modified, removed, or extended
freely.

### Auto-Discovery

ZTF looks for `functions.py` in these locations (in order):

1. The directory containing `input.yml`
2. The parent directory of `input.yml`
3. `./examples/functions.py` relative to the current working directory
   (where `ztf examples` places the starter file)

The `--functions` CLI flag overrides auto-discovery.  If no functions file
is found and `--functions` is not specified, `{fn.*}` tokens are left
unresolved.

---

## 4. Interrupt Handling and Recovery

### What Happens When You Press Ctrl+C

ZTF handles interrupts gracefully during `apply` and `destroy`:

| Action           | Behaviour                                                    |
| ---------------- | ------------------------------------------------------------ |
| **First Ctrl+C** | ZTF stops scheduling new resource operations. The currently in-flight operation is allowed to finish. State is saved with all completed resources. |
| **Second Ctrl+C** | Immediate exit. Because state is written after every resource, only the single in-flight operation may be lost. |

State is persisted incrementally after **every** successful resource
operation -- not just at the end. This means an interrupted run never
leaves you with orphaned infrastructure that ZTF doesn't know about.

### Recovery After an Interrupt

After an interrupted `apply` or `destroy`, simply:

```bash
# See what's left to do
ztf plan

# Resume where you left off
ztf apply --auto-approve
```

ZTF compares the saved state against your config and generates a plan
for only the resources that weren't completed. Resources that were
successfully created, updated, or deleted before the interrupt are
already recorded in state.

### What About Partially Created Resources?

If a resource operation was in-flight when the interrupt occurred:

- **Create**: The resource may exist on the Nutanix cluster but not in
  ZTF state. On the next `apply`, ZTF's duplicate detection (via filter
  format) will find it and skip creation, returning the existing ext_id.
- **Update**: The resource keeps its previous state entry. The next
  `apply` will re-attempt the update.
- **Delete**: The resource stays in state. The next `destroy` or `apply`
  will re-attempt deletion.

---

## 5. Custom PE-Ops Helper Entities

Some Prism Element (PE) cluster-local operations have no Nutanix v4 API at
all -- they only exist as legacy v1/v2 REST endpoints or require direct SSH
access to a CVM. For these, ZTF ships hand-written "helper" classes
(`ztf/helpers/*.py`) instead of generating a client from an OpenAPI spec.
Helpers are registered in `ztf/custom_helpers.py`'s `custom_helpers_registry`
and declared in `manual_entities.yml`, which is cross-validated against the
registry and merged into the generated `entity_map.py` / `entity_catalog.json`
by the entity-catalog maintainer pipeline (see
[Entity Registry Migration](entity-registry-migration.md); the compiler
pipeline itself now lives in the separate `ztf-internal-scripts` repo).

### PE-Direct Helper Entities

| Entity                   | Purpose                                                        | Transport      |
| ------------------------ | ---------------------------------------------------------------| -------------- |
| `eula_pe`                | Accept the PE cluster EULA (username/company/job title)        | PE v1 REST     |
| `ad_server_pe`           | Register an Active Directory / OpenLDAP directory on a PE cluster | PE v1 REST  |
| `role_mapping_pe`        | Map an AD group/OU/user to a PE cluster role                   | PE v1 REST     |
| `open_replication_ports` | Open the standard DR replication ports (2020, 2030, 2036, 2073, 2090) on every CVM in a cluster | SSH (`allssh` + `modify_firewall`) |
| `ha_reservation`         | Enable/disable HA failover reservation on a PE cluster          | PE v0.8 REST   |

These behave like any other entity in `config/input.yml` -- declare them
under `resources:` with the fields listed in each helper's `helper_schema`
(see `manual_entities.yml` in `ztf-internal-scripts` for the authoritative
field list, types, and defaults), and reference them from other resources
with the usual `{resource_name.field}` interpolation tokens.

### Data sources for helper entities

Custom helpers that support list (`list_entities`) accept the same YAML
`data:` keys as SDK entities. Underscore SDK aliases (`_filter`, `_select`,
...) still map to the helper when it exposes those parameters. Any other
non-underscore key is forwarded as `custom_filter` so helper-specific
lookups work.

`role_mapping_pe` is keyed by directory name, not an OData `filter`. Pass
that field on the data source:

```yaml
data:
  role_mapping_pe:
    cluster_admins:
      directory_name: corp-ad
```

`depends_on` is still only a fetch-order edge; it is never sent to the
helper. See [Data Sources](configuration-reference.md#5-data-sources) for
the full list-arg rules.

### `open_replication_ports`

Omit `ports` to open the default DR set: `2020`, `2030`, `2036`, `2073`,
`2090`. To override, pass a non-empty list of integers (digit strings such
as `"2020"` are accepted) in the range 1-65535:

```yaml
resources:
  open_replication_ports:
    dr_ports:
      body:
        cluster_ip: 10.0.0.1
        cvm_credential:
          username: nutanix
          password: "{var.cvm_password}"
        ports: [2020, 2030, 2036, 2073, 2090]
```

ZTF validates `ports` before interpolating them into the CVM
`modify_firewall` / `allssh` command. Empty lists, booleans, and values
outside 1-65535 fail the apply with a `ValueError` instead of reaching SSH.

### Why These Aren't v4-Native

Each of these was verified against the v4 MCP tool catalog (`search_nutanix_tools`
/ `inspect_tool` across all registered namespaces) before being added as a
manual helper, to confirm no v4 Prism Central API can perform the same
operation:

- **`ad_server_pe`, `role_mapping_pe`, `open_replication_ports`,
  `ha_reservation`** -- no v4 namespace exposes an equivalent operation.
  These are PE-cluster-local settings (directory services, RBAC role
  mappings, host firewall rules, and HA host-failure reservations) with no
  PC-level v4 surface.
- **`eula_pe`** -- v4 does expose a licensing EULA operation, but its
  request body only accepts `companyName`, `jobTitle`, `loginId`, and
  `userName`; there is no cluster-targeting field (e.g. `clusterExtId`).
  That v4 API accepts a single, PC-global EULA and cannot target a
  standalone PE cluster, so `eula_pe` remains a PE-direct helper.
- **`password_pe`** was considered during this evaluation and intentionally
  **excluded**: v4's `clustermgmt` namespace already exposes
  `changeSystemUserPasswordById` for AOS/PC/AHV system accounts, which
  covers the same use case without a legacy backport.

When adding a new PE-ops helper in the future, follow this same
search -> inspect -> decide workflow against the v4 MCP gateway before
writing a manual helper, and record the verification rationale as a comment
in `manual_entities.yml` next to the new entry.

---

## 6. Foundation Central Helper Entities

Declare these under `resources:` and point the domain at Prism Central.
ZTF reaches Foundation Central through that PC. Nodes must already be
discovered in FC. Field lists come from `ztf examples`.

| Foundation Central | Cluster | Resources |
| ------------------ | ------- | --------- |
| 1.11 | HCI (hyperconverged) | `fc_v1_imaging`, `fc_v1_cluster` |
| 2.2 | Compute-only (CO) with external storage | `fc_create_cluster` |

### FC 1.11 — HCI clusters

`fc_v1_imaging` and `fc_v1_cluster` use the Foundation Central 1.x API
and select nodes by serial.

- `fc_v1_imaging` images nodes (AOS package and hypervisor ISO). The
  default `skip_cluster_creation: true` images only and needs at least
  two nodes. Set it to `false` to image and create the HCI cluster in
  one job.
- `fc_v1_cluster` forms an HCI cluster from nodes that are already
  imaged. Required fields are `cluster_name` and `nodes_list`.

`enable_lacp` applies only with Cisco top-of-rack switches on FC 1.x.
Discovery sometimes reports `node_role` as `unsupported_node`; ZTF sends
`hyperconverged` instead.

### FC 2.2 — compute-only clusters with external storage

`fc_create_cluster` creates a cluster from nodes already onboarded to
Foundation Central 2.2. Use it for a compute-only cluster whose storage
is external. Nodes are addressed by FC node extId (the same id as
`fc_node`), not by serial.

After the task succeeds (`wait_for_completion` defaults to true), state
stores the cluster extId. Reference it as `{resource_name.extId}`. The
task often lists node extIds in `entitiesAffected` before the cluster
object appears. ZTF treats an affected entity as the cluster only when
its `rel` refers to a cluster; otherwise it uses `completionDetails`,
then a node or name lookup.

### Other helpers

| Resource | What it does |
| -------- | ------------ |
| `foundation_central_service` | Enable Foundation Central on this Prism Central |
| `generate_fc_api_key` | Create an FC API key (`alias`). FC must already be enabled |
| `update_cvm_foundation` | Upgrade or downgrade Foundation on a CVM over SSH |
| `fc_v1_image_upload` | Upload an AHV or AOS installer into an existing FC image |

`update_cvm_foundation` SSHs to `cvm_ip`, downloads `foundation_build_url`,
and lands `foundation_version`. Set `downgrade: true` to replace the
installed build. An optional `nameserver` is written before the download.

Lifecycle objects (claim tokens, images, nodes, discovered nodes,
hardware providers and pools, `foundation_central_config`) come from the
Prism Central 7.6 lifecycle namespace (`ntnx-lifecycle-py-client` 4.3.1).
Other namespaces stay on the 7.5.1 SDKs. These objects are ordinary v4
resources. Run `ztf examples --namespace lifecycle` for skeletons.

### `fc_v1_image_upload`

Uploads installer bits into an **existing** Foundation Central image.
`image_extId` is optional in `helper_schema` (generated examples comment
it out), but apply still needs it: this helper does not create the image.
Create the image first with `fc_image` (v4), then pass its extId:

```yaml
resources:
  fc_image:
    ahv_installer:
      body:
        name: ahv_11.0.1.6
  fc_v1_image_upload:
    ahv_bits:
      body:
        name: ahv_11.0.1.6
        image_extId: "{ahv_installer.extId}"
        image_path: /path/to/image.iso
        metadata_path: /path/to/metadata.json
        checksum: 6bab0e04040fd98cfeb808eef2a7a58c30563d26784e9f716bdd39458a25416c
```

Update is not supported for this helper (`update_supported: false`). To
replace bits, delete and recreate, or upload into a new `fc_image`.
`ztf examples --namespace foundation_central` emits `image_extId` as a
commented optional field; uncomment it (or interpolate
`{fc_image_resource.extId}`) before apply.
