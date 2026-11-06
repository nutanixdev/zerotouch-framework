# ZTF: Zero Touch Framework

ZTF is a Python-based Infrastructure as Code (IaC) framework for managing resources across multiple Nutanix Prism Central domains. It uses declarative YAML configuration files and Nutanix v4 SDKs to orchestrate creation, update, deletion, and custom operations on infrastructure entities. ZTF runs on Python 3.10 through 3.14. Nutanix Files APIs remain unavailable because of a dependency conflict with the published Files package.


> **Migrating from ZTF 1.x?** ZTF 2.x is a ground-up rewrite on Nutanix v4 SDKs. 2.1.0 ports Foundation Central imaging and cluster create, and a few PE cluster-local helpers. NCM / Calm DSL workflows, NDB scripts, NKE, and the Pod conceptual workflows remain on the [1.x branch](https://github.com/nutanixdev/zerotouch-framework/tree/1.5.2) (last 1.x release: [`v1.5.2`](https://github.com/nutanixdev/zerotouch-framework/releases/tag/v1.5.2)). See [Migrating from ZTF 1.x](#migrating-from-ztf-1x).

## Table of Contents

- [ZTF: Zero Touch Framework](#ztf-zero-touch-framework)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Concepts at a Glance](#concepts-at-a-glance)
  - [Migrating from ZTF 1.x](#migrating-from-ztf-1x)
  - [Known Limitations](#known-limitations)
    - [Nutanix Files APIs Not Supported](#nutanix-files-apis-not-supported)
  - [Installation](#installation)
    - [Local](#local)
    - [Docker](#docker)
  - [Minimal Configuration](#minimal-configuration)
  - [Quick Start](#quick-start)
    - [Discovering values for `data` filters](#discovering-values-for-data-filters)
  - [Commands](#commands)
  - [CLI Flags](#cli-flags)
  - [Simple Project Layout](#simple-project-layout)
  - [Custom Config Directories](#custom-config-directories)
  - [Interpolation](#interpolation)
  - [Lifecycle Rules](#lifecycle-rules)
  - [Using Example Configurations](#using-example-configurations)
  - [Documentation](#documentation)
  - [License](#license)

## Features

- **Multi-domain orchestration** -- manage resources across many Prism Central instances in parallel. Foundation Central is reached through the PC domain
- **Dependency resolution** -- automatic topological ordering via interpolation analysis (extId dependancy) and provision for explicit dependancy mapping using `depends_on`
- **State management** -- YAML state file with advisory locking, backups, incremental writes, and atomic replace (a crash during serialization cannot leave a truncated `state.yml`)
- **Plan before apply** -- preview creates, updates (field-level diff), and deletes with live data sources
- **Auto-refresh** -- plan and apply refresh state from infrastructure automatically before computing changes
- **Apply progress** -- long-running Prism Central tasks log child subtasks while ZTF waits
- **Confirmation prompt** -- interactive `"yes"` confirmation before apply/destroy with post-apply summary
- **Interpolation** -- reference variables, data sources, resources, and cross-domain state
- **Variables and var-files** -- multi-source variables with auto-loading (`ztfvars.yml`)
- **Dynamic resources** -- `for_each` expansion for repeatable resource patterns
- **Lifecycle rules** -- `prevent_destroy`, `ignore_changes`, `create_before_destroy`
- **Data sources** -- fetch existing infrastructure; a source may reference another source with `{data.<entity>.<source>...}` or `depends_on`
- **Foundation Central 1.11** -- HCI clusters (`fc_v1_imaging`, `fc_v1_cluster`)
- **Foundation Central 2.2** -- compute-only clusters with external storage (`fc_create_cluster`)
- **Foundation Central helpers** -- `foundation_central_service`, `generate_fc_api_key`, `update_cvm_foundation`, and `fc_v1_image_upload`
- **PE cluster-local helpers** -- `eula_pe`, `ad_server_pe`, `role_mapping_pe`, `open_replication_ports`, `ha_reservation`
- **Schema negotiation** -- version-aware request body filtering so one `input.yml` can target mixed Prism Central minors
- **Import** -- bring existing infrastructure under management, with config snippet generation and bulk import. `refresh` and `import` omit server-managed fields (`createTime`, `ownerExtId`, `sizeBytes`, and similar) so they are not reported as drift
- **Outputs** -- extract and export values after apply
- **Operations** -- custom post-CRUD operations (Beta)
- **Reviewed entity catalog** -- OpenAPI-backed identities, exact operation IDs, per-operation SDK adapters, and compatible entity aliases. Several 2.0.0 headings remain accepted with a deprecation warning; `ztf migrate entity-registry` rewrites them to the 7.5.1 names
- **Custom functions** -- user-defined Python functions (`{fn.*}` tokens) for computed values, templates, and base64 encoding
- **Example generation** -- auto-generated per-entity YAML examples, Markdown reference docs, and starter functions file

## Concepts at a Glance

- **variables**: static inputs you define once and reuse within the input file; referenced as `{var.name}`.
- **ztfvars.yml**: auto-loaded variable file intended for secrets; keep out of git.
- **domains**: one or more Prism Central targets. Foundation Central is reached through that PC. Each domain has its own `data` and `resources`. Starting with ZTF 2.1.0, `location`, `registered_domain`, and `local_domain` are ordinary resources.
- **data**: read-only lookups of existing entities (resolved at plan and apply time); used to fetch IDs for resources. A source may reference another source. Source names must be unique within a domain.
- **resources**: entities ZTF creates/updates/deletes; grouped by entity type.
- **resource_name**: user-defined identifier under a resource type; used for interpolation and state tracking. Must be unique within a domain.
- **outputs**: values computed after apply; good for surfacing IDs or sharing with other tools.
- **functions.py**: optional user-defined Python functions; referenced as `{fn.name(args)}` in YAML.
- **state.yml**: ZTF-managed state file; DO NOT edit manually.

## Migrating from ZTF 1.x

ZTF 2.x is a ground-up rewrite on Nutanix v4 SDKs. 2.1.0 ports Foundation Central 1.11 HCI imaging and cluster create (`fc_v1_imaging`, `fc_v1_cluster`), and Foundation Central 2.2 compute-only clusters with external storage (`fc_create_cluster`). It also ports `foundation_central_service`, `generate_fc_api_key`, `update_cvm_foundation`, and `fc_v1_image_upload`, and the PE helpers `eula_pe`, `ad_server_pe`, `role_mapping_pe`, `open_replication_ports`, and `ha_reservation`. See [v2.1.0](releases/2.1.0/README.md) and [Advanced Topics](docs/advanced-topics.md). The surfaces below are still only on [ZTF 1.5.2](https://github.com/nutanixdev/zerotouch-framework/tree/1.5.2) (last 1.x release: [`v1.5.2`](https://github.com/nutanixdev/zerotouch-framework/releases/tag/v1.5.2)).

**Features only available on the 1.x branch**

- **Prism Element (v2) operations:** `CreateContainerPe`, `CreateVmPe`, `UploadImagePe`, `PowerTransitionVmPe`, `UpdateDsip`, `RebuildCapacityReservation`, `UpdatePulsePe`, `AddNameServersPe`, `AddNtpServersPe`, `DeleteSubnetsPe`, and the rest of the `*Pe` script family that has no 2.x helper.
- **Pod / pod-block conceptual workflows:** `imaging`, `sites-deploy`, `pod-config`, `deploy-management-pc`, `config-management-pc`, `deploy-pc`, `config-pc`, `config-cluster`. `imaging` and `sites-deploy` stay on 1.x; the Foundation Central operations they call are the 2.x helpers above.
- **NCM / Calm DSL workloads:** `calm-vm-workloads`, `calm-edgeai-vm-workload`, `CreateAppFromDsl`, `CreateNcmProject`, `CreateNcmAccount`, `CreateNcmUser`, `InitCalmDsl`.
- **NDB:** Deploy and configure the NDB management VM (`ndb` workflow: password change, pulse, multi-cluster, compute / network profiles, HA).
- **NKE / Karbon:** `EnableNke`, `CreateKarbonClusterPc`.
- **Objects (legacy script-based flow):** `EnableObjects`, `CreateObjectStore`, `CreateBuckets`, `ShareBucket`,
  `AddAdUsersOss`. (v4 SDK coverage for `objects` is partial; track parity in the roadmap.)

**Using the 1.x tree:**

```bash
git clone -b 1.5.2 https://github.com/nutanixdev/zerotouch-framework.git
cd zerotouch-framework
# Follow dev-setup-README.md from the 1.x branch for the venv + run loop
python main.py --workflow <workflow-name> -f config/<your-config>.yml
```

New features land on 2.x first; no further functional changes are planned for the 1.x line beyond critical fixes.

## Known Limitations

### Nutanix Files APIs Not Supported

Nutanix Files APIs are currently not included in ZTF due to a dependency conflict with the published Files package. We are tracking this with Nutanix for resolution. Please monitor the [Nutanix Python SDK releases](https://pypi.org/project/ntnx-files-py-client/) for updates.

Files registry corrections are recorded but remain unavailable until the
published Files SDK can resolve with the complete pinned SDK set. For current
entity aliases and the optional one-time correction command, see
[Entity Registry Corrections and One-Time Migration](docs/entity-registry-migration.md).

## Installation

ZTF supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

### Local

Create a virtual environment first:

```bash
# With uv (recommended)
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Or with standard Python
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Then install:

```bash
# Use any of these below ways to install ztf

# From PyPI (with uv)
uv pip install nutanix-ztf --prerelease=allow

# From PyPI (with pip)
pip install nutanix-ztf
```

Dependencies are resolved from PyPI. `--prerelease=allow` is required with `uv pip install` because ZTF pins two pre-release Nutanix SDK clients; `pip` needs no extra flag.

### Docker

ZTF ships a multi-stage [`Dockerfile`](https://github.com/nutanixdev/zerotouch-framework/blob/main/Dockerfile)
with two consumer-facing targets: `runtime` (a self-contained image with the `ztf` CLI on the PATH) and `wheels-export` (a scratch image used to extract an offline wheel bundle for dark-site installs).

**Build the runtime image:**

```bash
docker build --target runtime -t ztf:2.1.1 .
```

**Run against a project on the host** (mount your `input.yml`, `global.yml`, `state.yml`, and `ztfvars.yml` into the container's working directory):

```bash
docker run --rm -it \
  -v "$PWD:/home/ztf" \
  ztf:2.1.1 plan
```

The image's entrypoint is already `ztf`, the working directory is `/home/ztf`, and it runs as a non-root `ztf` user. Append any subcommand and flags after the image name (e.g. `ztf:2.1.1 apply --auto-approve`).

**Pass secrets via env file or a read-only** `ztfvars.yml` **mount:**

```bash
docker run --rm -it \
  --env-file .env \
  -v "$PWD:/home/ztf" \
  -v "$PWD/ztfvars.yml:/home/ztf/ztfvars.yml:ro" \
  ztf:2.1.1 apply
```

**Dark-site / offline wheel bundle.** Build the `wheels-export` target on a connected machine, then `pip install --no-index` from the exported wheels on the air-gapped target:

```bash
# On the connected machine — produces ./offline-wheels/ with ZTF + every dep
docker build --target wheels-export \
  --output type=local,dest=./offline-wheels .

# On the dark-site target — no network required
pip install --no-index --find-links=./offline-wheels --require-hashes \
  -r ./offline-wheels/requirements.txt
pip install --no-index --find-links=./offline-wheels nutanix-ztf
```

## Minimal Configuration

ZTF expects two files by default at the project root: `global.yml` (API settings) and `input.yml` (resource definitions). Both paths are overridable via CLI flags.

**global.yml:**

```yaml
config:
  port: 9440
  verify_ssl: false
  connect_timeout: 5000 # in milliseconds (default: 5000)
  read_timeout: 300000 # in milliseconds (default: 300000)
  debug: false # enable debug-level logging (default: false)
```

**input.yml:**

```yaml
# This is just an example input file. You can use the generated examples as reference.
# local Variables: static inputs you define once and reuse within the input file; referenced as `{var.name}`.
variables:
  env: prod # this is a variable that you can reuse within the input file

# Domains are one or more Prism Central targets; Foundation Central is reached through that PC.
# Each domain has its own `data` and `resources`.
domains:
  # Domain name: unique identifier for the domain
  lab1:
    # Prism Central configuration. Foundation Central is reached through this PC.
    host: 10.10.0.1 # IP or FQDN
    username: admin
    password: "{var.lab1_password}" # fetched from the ztfvars.yml file

    # Resources are the entities to create/update/delete
    # Here we are managing a storage container in the cluster named 'grove1-3'
    # and a category in the domain
    resources:
      storage_container: # resource type -> storage_container
        my_container: # user-defined resource name -> my_container (must be unique within the domain)
          params: # parameters to pass to the API call
            X_Cluster_Id: "{data.cluster.grove_cluster.data.0.extId}" # extId of the cluster as fetched from data-source
          body: # body of the API call
            name: "{var.env}-storage-container" # using the variable env to create a name for the storage container. i.e prod-storage-container
            replicationFactor: 2

      category: # resource type -> category
        my_category: # user-defined resource name -> my_category (must be unique within the domain)
          body: # body of the API call
            key: "{var.env}-category" # key of the category. i.e prod-category
            value: "{var.env}" # value of the category. i.e prod

# Outputs are values to export after apply
outputs:
  # Here we are exporting the extId of the storage container
  container_id: # user-defined output name -> container_id
    value: "{lab1.my_container.extId}" # extId of the storage container
    description: "Storage container ext_id"
```

If you want to clear all resources from `input.yml`, keep the file structure and set 'resources: {}' or delete the resources section under the domain.

**Resource names** like `my_container`, **Data-Source** **names** like `grove_cluster` are user-defined identifiers. They must be **unique within a domain** and are used for interpolation references, state tracking, and dependency resolution. Within a domain body, use `{resource_name.extId}`. In outputs or when multiple domains share the same resource name, qualify with the domain: `{domain.resource_name.field}`.

Credentials should live in `ztfvars.yml` (auto-loaded, add to `.gitignore`):

```yaml
my_password: "supersecret"
```

## Quick Start

```bash
# 1. Initialise an empty state file
ztf init

# 1.5. Create ztfvars.yml for secrets if not already present (auto-loaded; add to .gitignore)
echo 'lab1_password: "supersecret123!"' > ztfvars.yml
echo 'ztfvars.yml' >> .gitignore

# 2. Generate examples for the entities in all namespaces
ztf examples

# 3. Create input.yml using the generated examples as reference
#    Create global.yml using the above global.yml as reference
#    (see examples/INDEX.md or the User Guide for details)

# 4. Plan before apply -- always preview changes first
ztf plan

# 4.5. Use --strict in CI to fail on refresh errors
ztf plan --strict

# 5. Apply changes (will prompt for confirmation)
ztf apply

# 6. Sync state with live infrastructure. If there are changes outside of ZTF's control (shows what changed)
ztf refresh

# 7. Destroy all managed resources (will prompt for confirmation)
ztf destroy

# 7.5. Or destroy specific resources only
ztf destroy --target my_container  # my_container is resource name
```

### Discovering values for `data` filters

ZTF data sources need live values (cluster names, `extId`s). Discover them
with `ztf repl`, then paste the same OData `filter` into YAML:

```bash
ztf repl -i config/input.yml
```

```python
data.cluster.list(domain='lab1')
data.cluster.list(domain='lab1', filter="name eq 'nested-grove4-2'", select="extId,name")
```

`data.<entity>` uses the YAML entity-type heading (`cluster`, `vm`,
`subnet`, `storage_container`, ...). Arguments are `filter`, `select`,
`orderby`, `limit`, and `page` — the same keys as a YAML `data:` block.
There is no `sortby`; use `orderby="name asc"`. You can query an entity
type that is not in the current `input.yml`; the REPL creates the client
on first use. See
[ztf repl](docs/configuration-reference.md#ztf-repl) in the configuration
reference.

## Commands

| Command | Description |
| --- | --- |
| `ztf init` | Create an empty state. Statefile manages the state of the resources in the domain |
| `ztf plan` | Preview what will change (auto-refreshes state first, fetches live data sources)  |
| `ztf apply` | Apply changes with confirmation prompt, Prism Central subtask logs, and a post-apply summary |
| `ztf refresh` | Sync current state with live infrastructure. Server-managed fields are omitted so they are not reported as drift |
| `ztf destroy` | Delete managed resources with detailed plan (supports `--target`) |
| `ztf import <resource> <domain>` | Import resource into state (prints suggested config, supports `--file` for bulk). Omits the same server-managed fields as `refresh` |
| `ztf migrate entity-registry` | Rewrite 2.0.0 entity headings and rejected operations to the 7.5.1 catalog (dry-run by default; `--write` to apply) |
| `ztf examples` | Generate per-entity YAML examples and Markdown docs |
| `ztf repl` | Start a read-only Python REPL with data sources loaded |

Run `ztf <command> --help` for per-command flags and defaults.

## CLI Flags

| Flag | Short | Default | Commands | Description |
| --- | --- | --- | --- | --- |
| `--input` | `-i`  | `input.yml` | all except init | Path to input configuration file |
| `--global-file` | `-g` | `global.yml` | all except init | Path to global SDK configuration |
| `--state` | `-s`  | `state.yml` | all | Path to state file (init auto-creates parent directories) |
| `--parallel` | `-p` | `cpu_count + 4` | all except init | Maximum parallel workers |
| `--var` | | | all except init | Variable override: `--var 'key=value'` (repeatable) |
| `--var-file` | | | all except init | Path to a YAML variable file (repeatable) |
| `--functions` | | | all except init | Path to functions file for `{fn.*}` tokens (auto-discovered) |
| `--output-file`  | | | apply | Path to write resolved outputs (YAML or JSON) |
| `--no-refresh` | | `false` | plan, apply, destroy | Skip automatic state refresh                                 |
| `--strict` | | `false` | plan, apply, destroy | Fail on refresh errors instead of using stale state |
| `--auto-approve` | | `false` | apply, destroy | Skip confirmation prompt |
| `--target` | | | destroy | Destroy only named resource(s) (repeatable) |
| `--file` | | | import | YAML manifest for bulk import |
| `--write` | | `false` | migrate entity-registry | Apply the entity-registry rewrite (dry-run is the default) |

## Simple Project Layout

```txt
my-project/
  global.yml          # SDK settings  (--global-file default)
  input.yml           # Resource definitions  (--input default)
  functions.py        # Optional: user-defined {fn.*} functions
  state.yml           # Managed by ZTF  (--state default)
  ztfvars.yml         # Secrets — add to .gitignore
  *.auto.ztfvars.yml  # Additional auto-loaded var files (alphabetical)
  examples/           # Generated by ztf examples
```

## Custom Config Directories

```txt
my-project
├── prod
│   ├── input.yml
│   ├── state.yml
│   └── ztfvars.yml
├── dev
│   └── input.yml
├── shared
    └── global.yml
    └── ztfvars.yml
```

You are not limited to the default layout. Pass any paths via flags:

```bash
# Per-environment configs. Manage from the root directory. Keep the global.yml and ztfvars.yml in the shared directory.
ztf init -s prod/state.yml # create the state file in the prod directory

ztf plan -i prod/input.yml -g shared/global.yml -s prod/state.yml # plan the changes in the prod environment

(or)

# Manage from the prod directory
cd prod

ztf init # create the state file in the prod directory, no need to specify the directory

ztf plan -g ../shared/global.yml # plan the changes in the prod environment, no need to specify the input file and state file as you are in the prod directory
```

```txt
# Example project layout
my-project
├── configs # config files based on entity type
│   ├── network.yml
│   ├── vms.yml
│   ├── vpc.yml
│   ├── subnets.yml
│   ├── security-groups.yml
│   ├── load-balancers.yml
│   ├── databases.yml
|   └── ztfvars.yml
├── states/ # state files based on entity type
|    ├── network.yml
|    ├── vms.yml
|    ├── vpc.yml
|    ├── subnets.yml
|    ├── security-groups.yml
|    ├── load-balancers.yml
|    ├── databases.yml
├── shared
    └── global.yml
    └── ztfvars.yml
```

```bash
# Create the state files in the states directory
ztf init -s states/network.yml # create the state file for the network entity
ztf init -s states/vms.yml # create the state file for the vms entity
... # create the state files for the other entities

ztf plan -i configs/network.yml -s states/network.yml -g shared/global.yml --var-file shared/ztfvars.yml # plan the changes for the network entity
ztf plan -i configs/compute.yml -s states/compute.yml -g shared/global.yml --var-file shared/ztfvars.yml # plan the changes for the vms entity

... # plan the changes for the other entities
```

## Interpolation

| Pattern | Resolves To |
| --- | --- |
| `{var.name}` | Variable value |
| `{each.key}` / `{each.value}` | `for_each` iteration key/value  |
| `{fn.name(args)}` | User-defined function result |
| `{data.entity.name.field}` | Data source field (for example `{data.cluster.grove.data.0.extId}`) |
| `{resource_name.extId}` | Resource extId (same domain) |
| `{domain.resource.field}` | Cross-domain resource reference |

Full-string tokens preserve the resolved Python type (int, dict, list).
Embedded tokens are always stringified.

A data source may interpolate another source in `filter` or in a list
parameter. ZTF infers the fetch order from `{data.<entity>.<source>...}`
tokens. Use `depends_on` when you need that edge without a token. Source
names share one namespace per domain and must be unique there. See
[Data Sources](docs/configuration-reference.md#5-data-sources).

## Lifecycle Rules

```yaml
defaults:
  rules:
    prevent_destroy: false # Protect resources from deletion
    ignore_changes: [] # Fields to skip during update comparison
    create_before_destroy: false # Replace without downtime (Beta)
```

Rules can be overridden per-resource under the `rules:` key.

## Using Example Configurations

After running `ztf examples`, browse `examples/INDEX.md` for
all available entities. Each entity has a `.yml` example and a `.md` reference
with field descriptions, enum values, and version availability. Extra method
parameters are nested under `params:`, which is where apply reads them. For
Prism Central 7.6 Lifecycle skeletons, run `ztf examples --namespace lifecycle`. For
multi-domain registration, run `ztf examples --namespace multidomain`.

## Documentation

|Document | Description |
| --- | --- |
| [Getting Started](https://github.com/nutanixdev/zerotouch-framework/blob/main/docs/getting-started.md) | Project setup, global config, input file reference |
| [Configuration Reference](https://github.com/nutanixdev/zerotouch-framework/blob/main/docs/configuration-reference.md) | Interpolation, variables, for_each, lifecycle, data sources, commands |
| [Advanced Topics](https://github.com/nutanixdev/zerotouch-framework/blob/main/docs/advanced-topics.md) | Multi-environment workflows, logging, custom functions, PE and Foundation Central helpers |
| [Entity Registry Corrections](docs/entity-registry-migration.md) | 2.1.0 entity aliases, rejected operations, and `ztf migrate entity-registry` |

## License

Copyright 2026 Nutanix, Inc. Licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).  
See [LICENSE.txt](LICENSE.txt) for the full text.
