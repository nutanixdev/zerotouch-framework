# ZTF Advanced Topics

Multi-environment workflows, logging, and custom Python functions.
For initial setup, see [Getting Started](getting-started.md).
For the full configuration reference, see
[Configuration Reference](configuration-reference.md).

---

## Table of Contents

- [1. Multi-Config and Multi-Environment Workflows](#1-multi-config-and-multi-environment-workflows)
- [2. Logging and Audit](#2-logging-and-audit)
- [3. Custom Functions](#3-custom-functions)
- [4. Interrupt Handling and Recovery](#4-interrupt-handling-and-recovery)

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
