# Getting Started with ZTF

This guide covers project setup, global configuration, and the input file
format. For the full configuration reference, see the
[Configuration Reference](configuration-reference.md). For multi-environment
workflows, custom functions, and logging, see
[Advanced Topics](advanced-topics.md).

---

## 1. Project Structure and Config Directories

ZTF expects two configuration files by default at the project root:

```
my-project/
  global.yml            # SDK/API settings (port, timeouts, SSL)
  input.yml             # Resource definitions (domains, resources, variables)
  state.yml             # Managed automatically by ZTF
  ztfvars.yml           # Optional: auto-loaded variables (add to .gitignore)
  *.auto.ztfvars.yml    # Optional: additional auto-loaded variable files
  functions.py          # Optional: user-defined functions for {fn.*} tokens
```

You are **not** limited to this structure. ZTF accepts custom paths for every
file via CLI flags, enabling multiple config directories, environments, and
workflows.

### Custom Config Directories

Organise configs by environment, team, or any structure you prefer:

```
infrastructure/
  envs/
    dev/
      input.yml
      dev.ztfvars.yml
    staging/
      input.yml
      staging.ztfvars.yml
    prod/
      input.yml
      prod.ztfvars.yml
  shared/
    global.yml
  states/
    dev-state.yml
    staging-state.yml
    prod-state.yml
```

Run ZTF against any environment by passing the paths:

```bash
# Dev environment
ztf init -s dev-state.yml -d states/
ztf plan -i envs/dev/input.yml -g shared/global.yml -s states/dev-state.yml \
  --var-file envs/dev/dev.ztfvars.yml

# Prod environment
ztf init -s prod-state.yml -d states/
ztf apply -i envs/prod/input.yml -g shared/global.yml -s states/prod-state.yml \
  --var-file envs/prod/prod.ztfvars.yml
```

### Passing Your Own Input File

The `--input` (`-i`) flag accepts any YAML file path:

```bash
ztf plan -i /path/to/my-custom-config.yml
ztf apply -i my-input.yml -s my-state.yml
ztf plan -i my-input.yml -g my-global.yml
```

---

## 2. Global Configuration

The global configuration file (default: `global.yml`) sets SDK and
API connection settings shared across all domains:

```yaml
config:
  port: 9440
  debug: false
  verify_ssl: false
  connect_timeout: 5000 # milliseconds
  read_timeout: 300000 # milliseconds
```

| Field             | Default  | Description                           |
| ----------------- | -------- | ------------------------------------- |
| `port`            | `9440`   | Prism Central API port                |
| `debug`           | `false`  | Enable debug-level logging            |
| `verify_ssl`      | `false`  | Verify SSL certificates for API calls |
| `connect_timeout` | `5000`   | Connection timeout in milliseconds    |
| `read_timeout`    | `300000` | Read timeout in milliseconds          |

---

## 3. Input Configuration Reference

The input configuration file (default: `input.yml`) defines what
infrastructure ZTF manages.

### Full Example

```yaml
variables:
  env: prod
  cluster_vip: 10.0.28.99

defaults:
  rules:
    prevent_destroy: false
    ignore_changes: []
    create_before_destroy: false

domains:
  lab1:
    host: 10.0.28.108
    username: admin
    password: "{var.my_password}"

    data:
      cluster:
        grove_cluster:
          filter: "name eq 'grove1-3'"

    resources:
      storage_container:
        sc1:
          params:
            X_Cluster_Id: "{data.cluster.grove_cluster.data.0.extId}"
          body:
            name: "{var.env}-storage-container"
            replicationFactor: 2
          operations:
            - type: mount_storage_container
              params:
                clusterExtId: "{data.cluster.grove_cluster.data.0.extId}"

outputs:
  sc_id:
    value: "{lab1.sc1.ext_id}"
    description: "Storage container ext_id"
```

### Top-Level Sections

| Section     | Required | Description                                                  |
| ----------- | -------- | ------------------------------------------------------------ |
| `variables` | No       | Static key-value pairs for interpolation (`{var.name}`)      |
| `defaults`  | No       | Default lifecycle rules applied to every resource            |
| `domains`   | Yes      | One or more Nutanix PC domains to manage                     |
| `outputs`   | No       | Values to extract and optionally write to a file after apply |

### Domain Configuration

Each domain maps to a Nutanix Prism Central instance.

| Field       | Required | Description                       |
| ----------- | -------- | --------------------------------- |
| `host`      | Yes      | PC IP address or hostname         |
| `username`  | Yes      | Authentication username           |
| `password`  | Yes      | Authentication password           |
| `data`      | No       | Data sources (read-only lookups)  |
| `resources` | Yes      | Resources to create/update/delete |

### Resource Configuration

Each resource is nested under `resources > entity_type > resource_name`:

```yaml
resources:
  <entity_type>:
    <resource_name>:
      body: { ... } # Resource body (API fields)
      params: { ... } # Parent ID params (e.g. X_Cluster_Id)
      extId: "..." # For import only
      depends_on: [...] # Explicit dependency list
      rules: { ... } # Per-resource lifecycle rules
      operations: [...] # Post-create/update operations (Beta)
      for_each: { ... } # Dynamic resource expansion
```

> **Resource names** (`<resource_name>`) are user-defined identifiers.
> They must be **unique within a domain** and are used for state tracking
> and dependency resolution. Within a domain, reference other resources
> with `{resource_name.extId}`. In `outputs:` (which sit outside any
> domain) or when multiple domains share the same resource name, use the
> domain-qualified form: `{domain.resource_name.field}`. Choose
> meaningful, descriptive names (e.g. `prod_storage_container`,
> `grove_cluster`).

| Field        | Required               | Description                                                    |
| ------------ | ---------------------- | -------------------------------------------------------------- |
| `body`       | Yes (unless importing) | API request body fields                                        |
| `params`     | No                     | Parent entity parameters (e.g. `X_Cluster_Id`, `clusterExtId`) |
| `extId`      | No                     | External ID (used for import)                                  |
| `depends_on` | No                     | List of resource names this resource depends on                |
| `rules`      | No                     | Per-resource lifecycle rule overrides                          |
| `operations` | No                     | Post-create/update operations (Beta)                           |
| `for_each`   | No                     | Map for dynamic resource expansion                             |
