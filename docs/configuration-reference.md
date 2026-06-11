# ZTF Configuration Reference

Detailed reference for all ZTF configuration features. For initial setup,
see [Getting Started](getting-started.md). For multi-environment workflows,
custom functions, and logging, see [Advanced Topics](advanced-topics.md).

---

## Table of Contents

- [ZTF Configuration Reference](#ztf-configuration-reference)
  - [Table of Contents](#table-of-contents)
  - [1. Interpolation](#1-interpolation)
    - [Token Patterns](#token-patterns)
    - [Type Preservation](#type-preservation)
  - [2. Variables and Var-Files](#2-variables-and-var-files)
    - [Defining Variables](#defining-variables)
    - [CLI Overrides](#cli-overrides)
    - [Auto-Loaded Variable Files (ztfvars)](#auto-loaded-variable-files-ztfvars)
    - [Override Precedence](#override-precedence)
  - [3. Dynamic Resources (`for_each`)](#3-dynamic-resources-for_each)
    - [How It Works](#how-it-works)
    - [Examples](#examples)
      - [Scalar values](#scalar-values)
      - [Map values with nested fields](#map-values-with-nested-fields)
      - [Combining `for_each` with variables](#combining-for_each-with-variables)
      - [Combining `for_each` with functions](#combining-for_each-with-functions)
      - [Adding lifecycle rules to `for_each` resources](#adding-lifecycle-rules-to-for_each-resources)
  - [4. Lifecycle Rules](#4-lifecycle-rules)
    - [prevent\_destroy](#prevent_destroy)
    - [ignore\_changes](#ignore_changes)
    - [create\_before\_destroy (Beta)](#create_before_destroy-beta)
    - [Per-Resource Override](#per-resource-override)
  - [5. Data Sources](#5-data-sources)
    - [Examples](#examples-1)
      - [Looking up a cluster to place resources](#looking-up-a-cluster-to-place-resources)
      - [Multiple data sources for a single resource](#multiple-data-sources-for-a-single-resource)
      - [Using `metadata.totalAvailableResults`](#using-metadatatotalavailableresults)
      - [Accessing fields beyond `extId`](#accessing-fields-beyond-extid)
      - [Filtering with `orderby` and `limit`](#filtering-with-orderby-and-limit)
      - [Multi-domain data source scoping](#multi-domain-data-source-scoping)
      - [Combining data sources with `for_each`](#combining-data-sources-with-for_each)
      - [Dynamic data-source references with nested tokens](#dynamic-data-source-references-with-nested-tokens)
  - [6. Operations (Beta)](#6-operations-beta)
    - [Operations on ZTF-Managed Resources](#operations-on-ztf-managed-resources)
    - [Operations on Pre-Existing Resources](#operations-on-pre-existing-resources)
    - [Importing Pre-Existing Resources](#importing-pre-existing-resources)
      - [Step 1: Define the resource in your input file with its `extId`](#step-1-define-the-resource-in-your-input-file-with-its-extid)
      - [Step 2: Import the resource into state](#step-2-import-the-resource-into-state)
      - [Step 3: Plan and apply](#step-3-plan-and-apply)
      - [Bulk import](#bulk-import)
      - [Importing `for_each` resources](#importing-for_each-resources)
      - [Important notes](#important-notes)
  - [7. Outputs](#7-outputs)
  - [8. Commands](#8-commands)
    - [ztf init](#ztf-init)
    - [ztf plan](#ztf-plan)
    - [ztf apply](#ztf-apply)
    - [ztf refresh](#ztf-refresh)
    - [ztf destroy (Beta)](#ztf-destroy-beta)
    - [ztf import](#ztf-import)
    - [ztf examples](#ztf-examples)
    - [ztf repl](#ztf-repl)
  - [9. CLI Flags Reference](#9-cli-flags-reference)
  - [10. Confirmation Prompt](#10-confirmation-prompt)
  - [11. State Management](#11-state-management)
    - [State File Format](#state-file-format)
    - [Safety Features](#safety-features)
    - [State File Locking](#state-file-locking)
  - [12. Dependency Resolution](#12-dependency-resolution)
    - [Automatic (Interpolation-Based)](#automatic-interpolation-based)
    - [Explicit (`depends_on`)](#explicit-depends_on)
    - [Execution Order](#execution-order)
  - [13. Plan and Diff](#13-plan-and-diff)
  - [14. Schema Negotiation](#14-schema-negotiation)
  - [15. Using Example Configurations](#15-using-example-configurations)
    - [Auto-Generated Examples](#auto-generated-examples)
    - [Reading the YAML Examples](#reading-the-yaml-examples)

---

## 1. Interpolation

ZTF supports `{scope.path}` token interpolation throughout the configuration.
Tokens are resolved at different stages depending on their scope.

### Token Patterns

| Pattern                                             | Resolves To                             | When Resolved |
| --------------------------------------------------- | --------------------------------------- | ------------- |
| `{var.name}`                                        | Variable value                          | Config load   |
| `{each.key}`                                        | Current `for_each` iteration key        | Config load   |
| `{each.value}`                                      | Current `for_each` iteration value      | Config load   |
| `{each.value.field}`                                | Field from `for_each` value map         | Config load   |
| `{fn.name(args)}`                                   | User-defined function result            | Config load   |
| `{data.entity.name.data.0.field}`                   | Field from the first data source result | Plan, Apply   |
| `{data.entity.name.metadata.totalAvailableResults}` | Total results count                     | Plan, Apply   |
| `{resource_name.extId}`                             | `extId` of a resource (same domain)     | Apply         |
| `{resource_name.body.field}`                        | Body field of a resource (same domain)  | Apply         |
| `{domain.resource.field}`                           | Cross-domain resource reference         | Apply         |

### Type Preservation

When a token is the **entire string value**, the resolved Python type is
preserved (int, dict, list, bool):

```yaml
variables:
  port: 514
  tags: { env: prod }

port: "{var.port}" # var.port = 514 (int), resolves to integer 514
tags: "{var.tags}" # var.tags = {env: prod}, resolves to dict {"env": "prod"}
```

When a token is **embedded** in a larger string, the result is always a
string:

```yaml
name: "prefix-{var.env}" # Always resolves to a string like "prefix-prod"
```

## 2. Variables and Var-Files

### Defining Variables

```yaml
variables:
  env: prod
  region: us-west
  my_password: "secret123"
```

### CLI Overrides

```bash
# Inline variable (repeatable)
ztf apply --var 'env=staging' --var 'region=eu-central'

# Variable file (repeatable, YAML format)
ztf apply --var-file vars/prod.yml --var-file secrets.yml
```

### Auto-Loaded Variable Files (ztfvars)

ZTF automatically discovers and loads variable files from the working
directory, mirroring Terraform's `terraform.tfvars` convention:

1. `**ztfvars.yml**` -- Primary secrets/variables file. Loaded first if present.
2. `***.auto.ztfvars.yml**` -- Additional files, sorted alphabetically.

These files are loaded **before** any explicit `--var-file` paths. Use
`ztfvars.yml` for credentials and secrets, and add it to `.gitignore`:

```bash
# .gitignore
ztfvars.yml
*.auto.ztfvars.yml
```

Example `ztfvars.yml`:

```yaml
my_password: "supersecret"
cluster_ip: "10.0.28.108"
```

ZTF logs which files are auto-loaded:

```
Auto-loading variable file: ztfvars.yml
Auto-loading variable file: 01-network.auto.ztfvars.yml
```

### Override Precedence

Variables are merged in this order (last wins):

1. `variables:` section in `input.yml`
2. `ztfvars.yml` (auto-loaded)
3. `*.auto.ztfvars.yml` (auto-loaded, alphabetical order)
4. `--var-file` values (in order specified)
5. `--var` values (in order specified) -- **highest precedence**

---

## 3. Dynamic Resources (`for_each`)

Use `for_each` to create multiple resources from a single template:

```yaml
resources:
  storage_container:
    "{each.key}-sc": # resource name is interpolated with the key
      for_each:
        analytics: # key
          name: analytics-container # value
          replication: 3 # value
        backup: # key
          name: backup-container # value
          replication: 2 # value
      body:
        name: "{each.value.name}" # value is interpolated with the value
        replicationFactor: "{each.value.replication}" # value is interpolated with the value
```

Result:

```yaml
resources:
  storage_container:
    analytics-sc:
      body:
        name: analytics-container
        replicationFactor: 3
    backup-sc:
      body:
        name: backup-container
        replicationFactor: 2
```

This expands to two resources: `analytics-sc` and `backup-sc`, each with
their own body values.

### How It Works

- `for_each` must be a **map** (not a list).
- Each key becomes `{each.key}`, each value becomes `{each.value}`.
- The resource name itself can contain `{each.key}` / `{each.value}` tokens.
- All other fields in the resource block form the template.
- Each iteration produces one independent resource.
- `{var.*}` and `{fn.*}` tokens are also available within `for_each` templates.

### Examples

#### Scalar values

When each value is a simple scalar, use `{each.key}` for the map key and
`{each.value}` for the scalar itself:

```yaml
resources:
  category:
    "env_{each.value}":
      for_each:
        dev: development
        stg: staging
        prd: production
      body:
        key: "Environment"
        value: "{each.value}"
```

Result:

```yaml
resources:
  category:
    env_development:
      body:
        key: Environment
        value: development
    env_staging:
      body:
        key: Environment
        value: staging
    env_production:
      body:
        key: Environment
        value: production
```

#### Map values with nested fields

When each value is a map, drill into fields with `{each.value.field}`:

```yaml
resources:
  subnet:
    "{each.key}-subnet":
      for_each:
        web:
          cidr: "10.0.1.0/24"
          gateway: "10.0.1.1"
          vlan_id: 100
        db:
          cidr: "10.0.2.0/24"
          gateway: "10.0.2.1"
          vlan_id: 200
      body:
        name: "{each.key}-subnet"
        subnetType: VLAN
        ipConfig:
          ipv4:
            ipSubnet:
              ip: "{each.value.cidr}"
            defaultGatewayIp: "{each.value.gateway}"
        networkId: "{each.value.vlan_id}"
```

Result — two subnets with their own IP configurations:

```yaml
resources:
  subnet:
    web-subnet:
      body:
        name: web-subnet
        subnetType: VLAN
        ipConfig:
          ipv4:
            ipSubnet:
              ip: "10.0.1.0/24"
            defaultGatewayIp: "10.0.1.1"
        networkId: 100
    db-subnet:
      body:
        name: db-subnet
        subnetType: VLAN
        ipConfig:
          ipv4:
            ipSubnet:
              ip: "10.0.2.0/24"
            defaultGatewayIp: "10.0.2.1"
        networkId: 200
```

#### Combining `for_each` with variables

Variables are resolved alongside `for_each` tokens:

```yaml
variables:
  env: prod
  replication: 2

resources:
  storage_container:
    "{var.env}-{each.key}-sc":
      for_each:
        logs:
          capacity_gb: 500
        metrics:
          capacity_gb: 200
      body:
        name: "{var.env}-{each.key}-container"
        replicationFactor: "{var.replication}"
        logicalAdvertisedCapacityBytes: "{each.value.capacity_gb}"
```

Result:

```yaml
resources:
  storage_container:
    prod-logs-sc:
      body:
        name: prod-logs-container
        replicationFactor: 2
        logicalAdvertisedCapacityBytes: 500
    prod-metrics-sc:
      body:
        name: prod-metrics-container
        replicationFactor: 2
        logicalAdvertisedCapacityBytes: 200
```

#### Combining `for_each` with functions

Custom functions can transform `for_each` values. Use `{fn.name(each.value)}`
to pass iteration values as function arguments:

```yaml
functions:
  pad:
    module: builtins
    callable: str.zfill

resources:
  category:
    "cat_{fn.pad(each.value, 4)}":
      for_each:
        c1: 1
        c2: 2
      body:
        key: "AppType"
        value: "App{fn.pad(each.value, 4)}"
```

Result:

```yaml
resources:
  category:
    cat_0001:
      body:
        key: AppType
        value: App0001
    cat_0002:
      body:
        key: AppType
        value: App0002
```

#### Adding lifecycle rules to `for_each` resources

Rules defined alongside `for_each` apply to every expanded resource:

```yaml
resources:
  storage_container:
    "{each.key}-sc":
      for_each:
        critical:
          name: critical-data
        archive:
          name: archive-data
      body:
        name: "{each.value.name}"
      rules:
        prevent_destroy: true
        ignore_changes:
          - replicationFactor
```

Result:

```yaml
resources:
  storage_container:
    critical-sc:
      body:
        name: critical-data
      rules:
        prevent_destroy: true
        ignore_changes: [replicationFactor]
    archive-sc:
      body:
        name: archive-data
      rules:
        prevent_destroy: true
        ignore_changes: [replicationFactor]
```

Both `critical-sc` and `archive-sc` inherit `prevent_destroy: true` and
`ignore_changes: [replicationFactor]`.

---

## 4. Lifecycle Rules

Lifecycle rules control how ZTF handles resource changes. Set them globally
in `defaults.rules` or override per-resource.

| Rule                    | Type | Default | Description                                      |
| ----------------------- | ---- | ------- | ------------------------------------------------ |
| `prevent_destroy`       | bool | `false` | Skip deletion during apply and destroy           |
| `ignore_changes`        | list | `[]`    | Body fields to ignore when comparing for updates |
| `create_before_destroy` | bool | `false` | Create new resource before deleting old (Beta)   |

### prevent_destroy

Protects critical resources from accidental deletion. When enabled, ZTF
skips deletion during both `apply` (when a resource is removed from config)
and `destroy`. The resource remains in state.

```yaml
rules:
  prevent_destroy: true
```

> **Persisted in state:** `prevent_destroy` is saved to `state.yml`
> when the resource is created, updated, or imported. This means the
> protection survives even if the resource is later removed or commented
> out of the input file -- ZTF will refuse to delete it and log a
> warning.
>
> To delete a protected resource, explicitly set `prevent_destroy: false`
> in your input file and run `ztf apply` first. This clears the rule
> from state, after which you can remove the resource from config.

### ignore_changes

Fields listed here are excluded from comparison when determining whether a
resource needs updating. Useful for fields managed externally or that change
frequently.

```yaml
rules:
  ignore_changes:
    - description
    - config.pulseStatus
```

**Path matching:** `ignore_changes` supports dotted paths with prefix
matching. `config.pulseStatus` also ignores `config.pulseStatus.isEnabled`
and any deeper nested fields.

### create_before_destroy (Beta)

> **Beta:** This rule is for advanced use cases. Test thoroughly before using
> in production.

For entities that don't support in-place updates, this rule creates the
replacement resource first, then deletes the old one. This minimises downtime
during replacements.

```yaml
rules:
  create_before_destroy: true
```

### Per-Resource Override

```yaml
resources:
  subnet:
    critical_subnet:
      rules:
        prevent_destroy: true
        ignore_changes:
          - description
      body:
        name: do-not-delete
```

---

## 5. Data Sources

Data sources fetch existing resources without managing them. They are **list-only**
and always return a list-shaped response with `data` and `metadata`.

```yaml
data:
  cluster:
    grove_cluster:
      filter: "name eq 'grove1-3'"
      select: "extId,name"
  subnet:
    prod_subnet:
      filter: "name eq 'prod-network'"
```

Reference in resources:

```yaml
body:
  clusterExtId: "{data.cluster.grove_cluster.data.0.extId}"
  subnetExtId: "{data.subnet.prod_subnet.data.0.extId}"
```

Data sources are fetched at both **plan time** and **apply time** so that
interpolation values are accurate in the plan preview. They are read-only --
ZTF never creates, updates, or deletes data source entities.

**Response shape (always list):**

- `data`: List of results (use list indexing like `.data.0`).
- `metadata.totalAvailableResults`: Total results count.

**Top-level list args (no `params`):**

- `filter`, `select`, `orderby`, `limit`, `page`
- Underscore variants (`_filter`, `_select`, ...) are also accepted.

### Examples

#### Looking up a cluster to place resources

The most common data source pattern — look up a cluster by name and use its
`extId` as a parameter or body field:

```yaml
data:
  cluster:
    target_cluster:
      filter: "name eq 'production-cluster'"
      select: "extId,name"

resources:
  storage_container:
    logs_sc:
      params:
        X_Cluster_Id: "{data.cluster.target_cluster.data.0.extId}"
      body:
        name: logs-container
        replicationFactor: 2
```

#### Multiple data sources for a single resource

A resource can reference several data sources. Here a VM needs both a
cluster and a subnet:

```yaml
data:
  cluster:
    compute_cluster:
      filter: "name eq 'compute-01'"
      select: "extId"
  subnet:
    app_subnet:
      filter: "name eq 'app-network'"
      select: "extId,name"

resources:
  vm:
    web_server:
      body:
        name: web-server-01
        cluster:
          extId: "{data.cluster.compute_cluster.data.0.extId}"
        nics:
          - subnet:
              extId: "{data.subnet.app_subnet.data.0.extId}"
```

#### Using `metadata.totalAvailableResults`

The metadata field tells you how many results matched the filter. Useful
for validation or conditional logic in outputs:

```yaml
data:
  subnet:
    all_prod_subnets:
      filter: "name eq 'prod-subnet'"

outputs:
  prod_subnet_count:
    value: "{data.subnet.all_prod_subnets.metadata.totalAvailableResults}"
    description: "Number of prod subnets found"
```

#### Accessing fields beyond `extId`

Data source results contain all fields returned by the API (after
sanitization). Access any field by its path:

```yaml
data:
  cluster:
    my_cluster:
      filter: "name eq 'grove1-3'"

resources:
  category:
    cluster_label:
      body:
        key: "ClusterName"
        value: "{data.cluster.my_cluster.data.0.name}"
```

#### Filtering with `orderby` and `limit`

Use `orderby` and `limit` to control which results come back:

```yaml
data:
  image:
    latest_centos:
      filter: "name eq 'CentOS-Stream-9'"
      orderby: "name desc"
      limit: 1
      select: "extId,name"

resources:
  vm:
    app_server:
      body:
        name: app-server
        disks:
          - backingInfo:
              imageReference:
                extId: "{data.image.latest_centos.data.0.extId}"
```

#### Multi-domain data source scoping

When your config has multiple domains, data sources are fetched per-domain.
In outputs or cross-domain references where the domain is ambiguous, prefix
with the domain name:

```yaml
domains:
  lab1:
    host: 10.0.0.1
    data:
      cluster:
        local_cluster:
          filter: "name eq 'lab1-cluster'"
    resources:
      storage_container:
        sc1:
          params:
            X_Cluster_Id: "{data.cluster.local_cluster.data.0.extId}"
          body:
            name: lab1-sc

  lab2:
    host: 10.0.0.2
    data:
      cluster:
        local_cluster:
          filter: "name eq 'lab2-cluster'"
    resources:
      storage_container:
        sc2:
          params:
            X_Cluster_Id: "{data.cluster.local_cluster.data.0.extId}"
          body:
            name: lab2-sc

# Within a domain's resources, {data.entity.name...} resolves to that
# domain's own data source.  In outputs, use the domain-scoped form:
outputs:
  lab1_cluster_id:
    value: "{data.lab1.cluster.local_cluster.data.0.extId}"
  lab2_cluster_id:
    value: "{data.lab2.cluster.local_cluster.data.0.extId}"
```

#### Combining data sources with `for_each`

Data source values can be used alongside `for_each` tokens:

```yaml
data:
  cluster:
    target:
      filter: "name eq 'production'"
      select: "extId"

resources:
  storage_container:
    "{each.key}-sc":
      for_each:
        analytics:
          name: analytics-data
        logging:
          name: log-data
      params:
        X_Cluster_Id: "{data.cluster.target.data.0.extId}"
      body:
        name: "{each.value.name}"
```

#### Dynamic data-source references with nested tokens

When the data-source **name itself** depends on iteration values,
use nested tokens. ZTF resolves inner tokens (like `{fn.*}` and
`{each.*}`) first, producing a clean data-source path for later
resolution at plan/apply time:

```yaml
data:
  category:
    dr_gold_01:
      filter: "key eq 'DR-Gold-01'"
      select: "extId"
    dr_gold_02:
      filter: "key eq 'DR-Gold-02'"
      select: "extId"

resources:
  category:
    "dr_gold_{fn.pad(each.value, 2)}":
      extId: "{data.category.dr_gold_{fn.pad(each.value, 2)}.data.0.extId}"
      for_each:
        g1: 1
        g2: 2
      body:
        key: "DR-Gold-{fn.pad(each.value, 2)}"
        value: "RPOZero"
```

After `for_each` expansion, the `extId` for `dr_gold_01` becomes
`{data.category.dr_gold_01.data.0.extId}` — the inner `{fn.pad(...)}` is
resolved during config loading, and the outer `{data.*}` token is resolved
at plan/apply time when data sources are fetched.

One level of nesting is supported: `{outer.{inner}.path}` works, but
deeper nesting like `{a.{b.{c}}.d}` does not.

---

## 6. Operations (Beta)

> **Beta:** Operations mutate infrastructure beyond standard CRUD. Review
> the entity reference docs and test in a non-production environment first.

Some entities support custom operations that run after the resource is
created or updated. All parameters — including resource IDs — must be
provided explicitly in `params`. Use data sources to look up IDs
dynamically instead of hardcoding UUIDs.

Each operation specifies:

| Field    | Required | Description                          |
| -------- | -------- | ------------------------------------ |
| `type`   | Yes      | SDK method name for the operation    |
| `params` | No       | Keyword arguments for the SDK method |
| `body`   | No       | Request body for the operation       |

Available operations per entity are documented in the generated reference
files at `examples/<namespace>/<entity>.md`.

### Operations on ZTF-Managed Resources

When the resource is created by ZTF, reference its `extId` directly
using `{resource_name.extId}`. ZTF populates the resource state after
create/update, so the ID is available when operations run:

```yaml
domains:
  lab1:
    host: 10.0.0.1
    username: admin
    password: "{var.password}"
    data:
      category:
        prod_cat:
          filter: "name eq 'production'"
    resources:
      volume_group:
        my_vg:
          body:
            name: my-volume-group
          operations:
            - type: attach_iscsi_client
              params:
                extId: "{my_vg.extId}"
              body:
                iscsiInitiatorName: "iqn.2024-01.com.example:init1"
            - type: associate_category
              params:
                extId: "{my_vg.extId}"
              body:
                categories:
                  - extId: "{data.category.prod_cat.data.0.extId}"
```

### Operations on Pre-Existing Resources

Operations are **stateless** — they do not require the resource to be
managed by ZTF or present in state. You can run operations on any
resource by looking it up with a data source:

```yaml
domains:
  lab1:
    host: 10.0.0.1
    username: admin
    password: "{var.password}"
    data:
      volume_group:
        vg_lookup:
          filter: "name eq 'existing-volume-group'"
    resources:
      volume_group:
        existing_vg:
          operations:
            - type: attach_iscsi_client
              params:
                extId: "{data.volume_group.vg_lookup.data.0.extId}"
              body:
                iscsiInitiatorName: "iqn.2024-01.com.example:init1"
```

Since operations supply their own IDs through `params`, the resource
block only needs the `operations` list — no `body` or `extId` is
required on the resource itself.

```bash
ztf plan      # shows the operations to run
ztf apply     # executes the operations
```

### Importing Pre-Existing Resources

If you want ZTF to **fully manage** a pre-existing resource (track
drift, apply updates, destroy on removal), you need to import it into
state. This is not required for operations-only use cases.

#### Step 1: Define the resource in your input file with its `extId`

The `extId` can be a literal UUID or a data-source interpolation token.
Data-source tokens are resolved at import time using the same
interpolation engine as `plan` and `apply`:

```yaml
# Literal extId
existing_vg:
  extId: "550e8400-e29b-41d4-a716-446655440000"

# Data-source interpolation
existing_vg:
  extId: "{data.volume_group.vg_lookup.data.0.extId}"
```

Variable (`{var.*}`) and function (`{fn.*}`) tokens are also supported
in `extId`. ZTF auto-loads `ztfvars.yml` and function files during
import, just like `plan` and `apply`.

#### Step 2: Import the resource into state

```bash
# -i and -s are required when config/state files are not in the
# default locations (input.yml, state.yml)
ztf import existing_vg lab1 \
  -i config/prod/input.yml \
  -g config/global.yml \
  -s config/prod/state.yml
```

ZTF fetches the resource from the API using the resolved `extId`,
sanitizes the response, and writes it into state. It also prints a
suggested config snippet you can use to update your input file with the
full body from the API.

#### Step 3: Plan and apply

After import, the resource is in state and ZTF can manage it normally:

```bash
ztf plan      # shows updates if input body differs from live state
ztf apply     # applies changes and runs operations
```

#### Bulk import

To import multiple pre-existing resources at once, create a YAML manifest
file:

```yaml
# import-manifest.yml
- resource_name: existing_vg
  domain_name: lab1
- resource_name: legacy_subnet
  domain_name: lab1
- resource_name: old_vm
  domain_name: lab2
```

Then run:

```bash
ztf import --file import-manifest.yml \
  -i config/prod/input.yml \
  -g config/global.yml \
  -s config/prod/state.yml
```

A single Provider and SDK session is reused across all entries in the
manifest. Data sources are fetched lazily on first use and cached, so
bulk imports with data-source tokens are efficient.

#### Importing `for_each` resources

When a resource is defined with `for_each`, the template expands to
multiple concrete resources during config loading. Use the **expanded
resource names** (not the template name) in import commands and manifests:

```yaml
# input.yml
resources:
  category:
    "dr_gold_{fn.pad(each.value, 2)}":
      extId: "{data.category.dr_gold_{fn.pad(each.value, 2)}.data.0.extId}"
      for_each:
        g1: 1
        g2: 2
      body:
        key: "DR-Gold-{fn.pad(each.value, 2)}"
        value: "RPOZero"
```

This expands to `dr_gold_01` and `dr_gold_02`. The `extId` data-source
references also resolve their inner `{fn.*}` tokens during expansion,
producing clean paths like `{data.category.dr_gold_01.data.0.extId}`.

To import these resources, use the expanded names:

```yaml
# import-manifest.yml
- resource_name: dr_gold_01
  domain_name: lab1
- resource_name: dr_gold_02
  domain_name: lab1
```

```bash
# Or import individually
ztf import dr_gold_01 lab1 -i config/input.yml -s config/state.yml
```

#### Important notes

- The resource **must** be defined in your input file before importing.
  ZTF uses the input config to determine the entity type and where to
  look up the resource.
- The `extId` in the input file must match a real resource in the
  infrastructure. ZTF will fail if the resource is not found.
- After import, `ztf plan` may show updates if the input body differs
  from the live state. This is expected — review the diff and adjust
  your input file or apply the changes.
- Import only writes to state. It never creates, updates, or deletes
  infrastructure.
- ZTF auto-loads `ztfvars.yml`, `*.auto.ztfvars.yml`, and `functions.py`
  during import. This means `{var.*}` and `{fn.*}` tokens in `extId`
  work without extra flags.

---

## 7. Outputs

Extract values after apply using the `outputs:` section:

```yaml
outputs:
  cluster_id:
    value: "{lab1.my_cluster.ext_id}"
    description: "Production cluster ID"
  environment:
    value: "{var.env}"
    description: "Current environment"
```

Write outputs to a file:

```bash
ztf apply --output-file outputs.yml    # YAML format
ztf apply --output-file outputs.json   # JSON format
```

Outputs support all interpolation patterns and are resolved after apply
completes using the final resource state.

---

## 8. Commands

### ztf init

Creates an empty state file.

| Option    | Short | Default     | Description                                              |
| --------- | ----- | ----------- | -------------------------------------------------------- |
| `--state` | `-s`  | `state.yml` | State file name (combined with `--path` when both given) |
| `--path`  | `-d`  |             | Directory to create the state file in (created if needed)|
| `--force` | `-f`  | `false`     | Overwrite existing state without prompting (backs up first) |

```bash
# Create state.yml in current directory
ztf init

# Create in a specific directory
ztf init -d config/categories

# Overwrite existing state
ztf init --force
```

### ztf plan

Dry-run that shows what will be created, updated, or deleted. **Always run
plan before apply** to review changes.

| Option         | Short | Default       | Description                                           |
| -------------- | ----- | ------------- | ----------------------------------------------------- |
| `--input`      | `-i`  | `input.yml`   | Path to input configuration file                      |
| `--global-file`| `-g`  | `global.yml`  | Path to global SDK configuration file                 |
| `--state`      | `-s`  | `state.yml`   | Path to state file                                    |
| `--parallel`   | `-p`  | `cpu_count+4` | Maximum parallel workers                              |
| `--var`        |       |               | Variable override (repeatable)                        |
| `--var-file`   |       |               | Path to YAML variable file (repeatable)               |
| `--functions`  |       | auto-discover | Path to Python functions file for `{fn.*}` tokens     |
| `--no-refresh` |       | `false`       | Skip automatic state refresh before plan              |
| `--strict`     |       | `false`       | Fail on refresh errors (recommended for CI/CD)        |

By default, plan refreshes state from infrastructure first (like Terraform)
and persists the refreshed state to disk. Live data sources are also fetched
so that interpolation values are accurate.

```bash
# Basic plan
ztf plan

# Plan with custom paths
ztf plan -i config/prod/input.yml -g config/global.yml -s config/prod/state.yml

# Plan with variable overrides
ztf plan --var 'env=staging' --var-file secrets.yml

# Skip refresh (faster, uses cached state)
ztf plan --no-refresh

# Strict mode for CI/CD (fail on refresh errors)
ztf plan --strict
```

**Field-level diff:** For resources marked as UPDATE, the plan shows exactly
which fields changed:

```
  [UPDATE] lab1 > storage_container/sc1
    ~ replicationFactor: 2 -> 3
    + newField: value
    - removedField: old_value

Plan: 0 to create, 1 to update, 0 to delete.
```

### ztf apply

Applies the planned changes with a confirmation prompt.

| Option           | Short | Default       | Description                                           |
| ---------------- | ----- | ------------- | ----------------------------------------------------- |
| `--input`        | `-i`  | `input.yml`   | Path to input configuration file                      |
| `--global-file`  | `-g`  | `global.yml`  | Path to global SDK configuration file                 |
| `--state`        | `-s`  | `state.yml`   | Path to state file                                    |
| `--parallel`     | `-p`  | `cpu_count+4` | Maximum parallel workers                              |
| `--var`          |       |               | Variable override (repeatable)                        |
| `--var-file`     |       |               | Path to YAML variable file (repeatable)               |
| `--functions`    |       | auto-discover | Path to Python functions file for `{fn.*}` tokens     |
| `--output-file`  |       |               | Path to write resolved outputs (YAML or JSON)         |
| `--no-refresh`   |       | `false`       | Skip automatic state refresh before apply             |
| `--strict`       |       | `false`       | Fail on refresh errors (recommended for CI/CD)        |
| `--auto-approve` |       | `false`       | Skip interactive confirmation prompt                  |

Before executing, ZTF auto-refreshes state, computes and displays the plan,
then prompts for `"yes"` confirmation. State is written incrementally after
each domain completes -- a `.bak` backup is created before every write.

```bash
# Basic apply
ztf apply

# Apply with auto-approve (CI/CD)
ztf apply --auto-approve --strict

# Apply with outputs
ztf apply --output-file outputs.yml

# Apply with custom config paths
ztf apply -i config/prod/input.yml -s config/prod/state.yml --var 'env=prod'
```

### ztf refresh

Syncs state from live infrastructure to detect out-of-band changes (drift).

| Option         | Short | Default       | Description                                           |
| -------------- | ----- | ------------- | ----------------------------------------------------- |
| `--input`      | `-i`  | `input.yml`   | Path to input configuration file                      |
| `--global-file`| `-g`  | `global.yml`  | Path to global SDK configuration file                 |
| `--state`      | `-s`  | `state.yml`   | Path to state file                                    |
| `--parallel`   | `-p`  | `cpu_count+4` | Maximum parallel workers                              |
| `--var`        |       |               | Variable override (repeatable)                        |
| `--var-file`   |       |               | Path to YAML variable file (repeatable)               |
| `--functions`  |       | auto-discover | Path to Python functions file for `{fn.*}` tokens     |

Refresh stores the full API response body (not just fields you defined).
If a resource fetch fails, the previous state entry is kept.

```bash
# Refresh state
ztf refresh

# Refresh with custom paths
ztf refresh -i config/prod/input.yml -s config/prod/state.yml
```

After refreshing, ZTF displays a diff summary:

```
  [CHANGED] lab1 > storage_container/sc1
  [REMOVED] lab1 > subnet/old_subnet

Refreshed 3 resource(s): 1 changed, 1 removed, 1 unchanged.
```

### ztf destroy (Beta)

> **Beta:** Destroy deletes managed infrastructure resources. Always review
> what will be destroyed and ensure you have backups.

| Option           | Short | Default       | Description                                           |
| ---------------- | ----- | ------------- | ----------------------------------------------------- |
| `--input`        | `-i`  | `input.yml`   | Path to input configuration file                      |
| `--global-file`  | `-g`  | `global.yml`  | Path to global SDK configuration file                 |
| `--state`        | `-s`  | `state.yml`   | Path to state file                                    |
| `--parallel`     | `-p`  | `cpu_count+4` | Maximum parallel workers                              |
| `--var`          |       |               | Variable override (repeatable)                        |
| `--var-file`     |       |               | Path to YAML variable file (repeatable)               |
| `--functions`    |       | auto-discover | Path to Python functions file for `{fn.*}` tokens     |
| `--auto-approve` |       | `false`       | Skip interactive confirmation prompt                  |
| `--target`       |       |               | Destroy only named resource(s) (repeatable)           |

Resources with `prevent_destroy: true` are skipped. State is written
incrementally.

```bash
# Destroy all managed resources
ztf destroy

# Destroy specific resources
ztf destroy --target my_container --target old_subnet

# Destroy with auto-approve (CI/CD)
ztf destroy --auto-approve --target temp_vm
```

**Removing resources via apply (recommended for selective cleanup):**

Instead of `ztf destroy`, remove resources declaratively from `input.yml`
and run `ztf apply`. ZTF treats the config as the desired state -- any
resources in state but absent from config are scheduled for deletion:

```yaml
domains:
  lab1:
    host: 10.0.0.1
    username: admin
    password: "{var.my_password}"
    resources:
      subnet:
        keep_this_subnet:
          body:
            name: keep-me
      # storage_container section removed -> those resources are deleted
```

```bash
ztf plan      # preview what will be deleted
ztf apply     # execute
```

### ztf import

Imports pre-existing resource(s) into state for full lifecycle management.

| Option         | Short | Default       | Description                                           |
| -------------- | ----- | ------------- | ----------------------------------------------------- |
| `--input`      | `-i`  | `input.yml`   | Path to input configuration file                      |
| `--global-file`| `-g`  | `global.yml`  | Path to global SDK configuration file                 |
| `--state`      | `-s`  | `state.yml`   | Path to state file                                    |
| `--parallel`   | `-p`  | `cpu_count+4` | Maximum parallel workers                              |
| `--var`        |       |               | Variable override (repeatable)                        |
| `--var-file`   |       |               | Path to YAML variable file (repeatable)               |
| `--functions`  |       | auto-discover | Path to Python functions file for `{fn.*}` tokens     |
| `--file`       |       |               | YAML manifest for bulk import                         |

Each resource must be defined in `input.yml` with an `extId` field.
Import updates state only -- it never modifies infrastructure.

```bash
# Import a single resource
ztf import my_vg lab1

# Import with custom paths
ztf import my_vg lab1 -i config/prod/input.yml -s config/prod/state.yml

# Bulk import from a YAML manifest
ztf import --file imports.yml
```

After a successful import, ZTF prints a suggested config snippet:

```
Suggested config for your input file (under domains > lab1 > resources > storage_container):

res1:
  extId: abc-123-def
  body:
    name: existing-container
    replicationFactor: 2
```

> **Note:** `--file` cannot be combined with positional `RESOURCE_NAME` /
> `DOMAIN_NAME` arguments.

### ztf examples

Generates per-entity YAML example configs and Markdown reference docs.

| Option         | Default      | Description                                     |
| -------------- | ------------ | ----------------------------------------------- |
| `--namespace`  |  all         | Generate examples for a single namespace only   |
| `--output-dir` | `./examples` | Output directory                                |

```bash
# Generate all examples
ztf examples

# Generate for a single namespace
ztf examples --namespace vmm

# Generate to a custom directory
ztf examples --output-dir config/examples
```

Also writes a starter `functions.py` file and an `INDEX.md` with a table
of all entities. See
[Using Example Configurations](#15-using-example-configurations).

### ztf repl

Starts a read-only Python REPL with ZTF config and data sources loaded.

| Option         | Short | Default       | Description                                           |
| -------------- | ----- | ------------- | ----------------------------------------------------- |
| `--input`      | `-i`  | `input.yml`   | Path to input configuration file                      |
| `--global-file`| `-g`  | `global.yml`  | Path to global SDK configuration file                 |
| `--var`        |       |               | Variable override (repeatable)                        |
| `--var-file`   |       |               | Path to YAML variable file (repeatable)               |
| `--exec`       |       |               | Execute one-line code and exit                        |
| `--script`     |       |               | Run a Python script file and exit                     |

The session exposes `ctx` (config/handlers) and `data` (data sources).
`--exec` and `--script` are mutually exclusive.

```bash
# Interactive REPL
ztf repl

# One-liner
ztf repl --exec "print(data.cluster.list(domain='lab1'))"

# Run a script
ztf repl --script scripts/audit.py
```

---

## 9. CLI Flags Reference

| Flag             | Short | Default         | Commands                                       | Description                                                             |
| ---------------- | ----- | --------------- | ---------------------------------------------- | ----------------------------------------------------------------------- |
| `--input`        | `-i`  | `input.yml`     | plan, apply, refresh, destroy, import, repl     | Path to input configuration file                                        |
| `--global-file`  | `-g`  | `global.yml`    | plan, apply, refresh, destroy, import, repl     | Path to global SDK configuration                                        |
| `--state`        | `-s`  | `state.yml`     | init, plan, apply, refresh, destroy, import     | Path to state file                                                      |
| `--parallel`     | `-p`  | `cpu_count + 4` | plan, apply, refresh, destroy                   | Maximum parallel workers                                                |
| `--var`          |       |                 | plan, apply, refresh, destroy, import, repl     | Variable override: `--var 'key=value'` (repeatable)                     |
| `--var-file`     |       |                 | plan, apply, refresh, destroy, import, repl     | Path to a YAML variable file (repeatable)                               |
| `--functions`    |       | auto-discover   | plan, apply, refresh, destroy, import            | Path to Python functions file for `{fn.*}` tokens                       |
| `--output-file`  |       |                 | apply                                           | Path to write resolved outputs (YAML or JSON)                           |
| `--no-refresh`   |       | `false`         | plan, apply                                     | Skip automatic state refresh before computing plan                      |
| `--strict`       |       | `false`         | plan, apply                                     | Fail on refresh errors instead of proceeding with stale state           |
| `--auto-approve` |       | `false`         | apply, destroy                                  | Skip interactive approval prompt                                        |
| `--target`       |       |                 | destroy                                         | Destroy only named resource(s) (repeatable)                             |
| `--file`         |       |                 | import                                          | YAML manifest for bulk import                                           |
| `--path`         | `-d`  |                 | init                                            | Directory to create the state file in                                   |
| `--force`        | `-f`  | `false`         | init                                            | Overwrite existing state without prompting                              |
| `--namespace`    |       | all             | examples                                        | Generate for a single namespace only                                    |
| `--output-dir`   |       | `./examples`    | examples                                        | Output directory for generated files                                    |
| `--exec`         |       |                 | repl                                            | Execute one-line code and exit                                          |
| `--script`       |       |                 | repl                                            | Run a Python script file and exit                                       |

---

## 10. Confirmation Prompt

Before executing `apply` or `destroy`, ZTF displays the planned changes and
prompts for explicit confirmation:

```
Do you want to perform these actions?
  ZTF will perform the actions described above.
  Only 'yes' will be accepted to apply.

  Enter a value:
```

- Only typing `yes` (case-insensitive) proceeds.
- Any other input, `Ctrl+C`, or `EOF` cancels the operation.
- If the plan shows **no changes**, apply exits without prompting.

To skip the prompt (e.g. in CI/CD pipelines):

```bash
ztf apply --auto-approve
ztf destroy --auto-approve
```

---

## 11. State Management

ZTF maintains infrastructure state in a YAML file (default: `state.yml`).

### State File Format

```yaml
domains:
  lab1:
    host: 10.0.28.108
    _entity_order:
      - storage_container
      - subnet
    resources:
      storage_container:
        sc1:
          ext_id: "abc-123-def"
          body:
            name: example-storage-container
            replicationFactor: 2
          params:
            X_Cluster_Id: "cluster-uuid"
```

### Safety Features

| Feature                      | Description                                                        |
| ---------------------------- | ------------------------------------------------------------------ |
| **Per-resource writes**      | State persisted after every resource operation completes            |
| **Automatic backups**        | `.bak` copy of state file created before every write               |
| **Advisory file locking**    | Cross-platform locking prevents concurrent writes                  |
| **Read-only permissions**    | State file set to `0o444` after writes to prevent accidental edits |
| **Domain failure isolation** | If one domain fails, its previous state is preserved               |
| **Entity ordering**          | Topological order stored in state for consistent delete operations |
| **Graceful interrupts**      | Ctrl+C saves partial state; only in-flight operation may be lost   |

### Graceful Interrupts

ZTF handles Ctrl+C gracefully during `apply` and `destroy`:

- **First Ctrl+C**: ZTF finishes the currently running resource operation,
  saves all completed resources to state, then exits. Resources that were
  not yet attempted will show as pending changes on the next run.
- **Second Ctrl+C**: Force-quits immediately. Because state is written after
  every resource, only the single in-flight operation may be lost.

This behaviour matches Terraform's interrupt handling. You never need to
manually reconcile orphaned resources after an interrupted run -- just run
`ztf plan` to see remaining work, then `ztf apply` again.

### State File Locking

ZTF uses advisory file locking to prevent concurrent processes from
corrupting the state file:

| Platform   | Mechanism                                         |
| ---------- | ------------------------------------------------- |
| Unix/macOS | `fcntl.flock(LOCK_EX)` -- exclusive advisory lock |
| Windows    | `msvcrt.locking(LK_LOCK)` -- byte-range lock      |

If you run multiple ZTF processes against the same state file, the lock
ensures only one writes at a time. Use separate state files for independent
environments.

---

## 12. Dependency Resolution

ZTF automatically determines the order in which resources are created,
updated, and deleted.

### Automatic (Interpolation-Based)

When a resource body references another resource via `{resource_name.field}`,
ZTF infers a dependency and processes the referenced resource first:

```yaml
resources:
  vpc:
    my_vpc:
      body:
        name: prod-vpc
  subnet:
    my_subnet:
      body:
        name: prod-subnet
        vpcReference: "{my_vpc.ext_id}" # Inferred dependency on my_vpc
```

### Explicit (`depends_on`)

For dependencies not expressed through interpolation, use `depends_on`:

```yaml
resources:
  vpc:
    my_vpc:
      body:
        name: prod-vpc
  subnet:
    my_subnet:
      depends_on:
        - my_vpc
      body:
        name: prod-subnet
```

### Execution Order

- **Create/Update**: Topological order (dependencies first).
- **Delete**: Reverse topological order (dependents first).
- Circular dependencies raise an error immediately.

---

## 13. Plan and Diff

The `plan` command computes a diff between your configuration and the current
state, showing exactly what will change:

```
  [CREATE] lab1 > subnet/my_subnet
  [UPDATE] lab1 > vm/my_vm
    + newField: value
    - removedField: value
    ~ changedField: old_value -> new_value
  [DELETE] lab1 > vm/old_vm
  [OPERATIONS] lab1 > vm/my_vm: power_on

Plan: 1 to create, 1 to update, 1 to delete, 1 operation(s) to run.
```

| Symbol | Meaning                                  |
| ------ | ---------------------------------------- |
| `+`    | Field added                              |
| `-`    | Field removed                            |
| `~`    | Field changed (shows old and new values) |

The comparison uses deep recursive equality that ignores list ordering and
SDK metadata fields (`$objectType`, `$dataItemDiscriminator`). Fields in
`ignore_changes` are excluded from the diff.

---

## 14. Schema Negotiation

ZTF supports multiple Prism Central versions from a single codebase. Before
sending API requests, the framework filters the request body against a
compatibility map that records which fields are available in which API
versions.

This means:

- Fields unsupported by the target PC version are automatically stripped.
- Read-only fields are removed from request bodies.
- OneOf/polymorphic fields are handled by matching `$objectType` discriminators.
- You can write configs that work across PC versions without manual field management.

Schema negotiation happens transparently during `create` and `update`
operations.

---

## 15. Using Example Configurations

ZTF provides two types of example configurations to help you get started.

### Auto-Generated Examples

Located in output directory or default `examples/`, organised by namespace:

```
examples/
  INDEX.md                    # Master index of all entities
  functions.py                # Starter functions file
  clustermgmt/
    storage_container.yml     # YAML example with all fields
    storage_container.md      # Full Markdown reference
  networking/
    vpc.yml
    subnet.yml
  vmm/
    vm.yml
    image.yml
```

**How to use them:**

1. Run `ztf examples` to generate (or regenerate) examples.
2. Browse `examples/INDEX.md` for a table of all available entities.
3. Open the `.yml` file for the entity you want to create.
4. Copy the relevant fields into your `input.yml` under the appropriate
   domain and entity type.
5. Uncomment optional fields as needed and fill in your values.
6. Check the `.md` reference for field descriptions, enum values, version
   availability, and links to the Nutanix developer documentation.
7. Copy `functions.py` alongside your `input.yml` if you need custom
   functions (`{fn.*}` tokens).

**Regenerate examples** after updating entity definitions:

```bash
ztf examples                     # All namespaces
ztf examples --namespace vmm     # Single namespace
```

### Reading the YAML Examples

```yaml
name: "example-name" # REQUIRED | string     (uncommented = required)
# description: "Example ..."  # string                (commented = optional)
# erasureCode: "OFF"          # enum: OFF, ON         (enum values listed)
# isShared: true              # boolean | v4.2        (version-gated)
```

| Convention           | Meaning                                       |
| -------------------- | --------------------------------------------- |
| Uncommented line     | Required field with example value             |
| Commented line (`#`) | Optional field                                |
| `# REQUIRED`         | Explicitly marked as required                 |
| `# enum: A, B, C`    | Allowed enum values                           |
| `# v4.2`             | Field only available in specific API versions |
