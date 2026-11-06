# v2.1.1

ZTF 2.1.1 is a packaging fix for 2.1.0. The framework, `input.yml`
format, and state format are unchanged, so upgrade in place.

## What's Fixed

- **2.1.0 cannot be installed from PyPI.** It required `urllib3>=2.6.3`
  and `certifi>=2026.7.22`, but every Nutanix v4 SDK client it pins
  requires `urllib3~=1.26` and `certifi<=2025.4.26`. pip and uv both
  report the conflict. 2.1.1 removes those two requirements from the
  published package metadata, so `pip install nutanix-ztf` resolves.
- **The Docker image builds again.** The `runtime` and `wheels-export`
  targets install from a hash-pinned export of `uv.lock` instead of resolving
  the published metadata.

## urllib3 and certifi versions

ZTF 2.1.1 installs with urllib3 1.26.20 and certifi 2025.4.26, the newest
versions the pinned SDK clients allow. Development, CI, the Docker image,
and `pip install` all resolve these same versions. Newer urllib3 and
certifi releases become available once the SDK clients relax their
upper bounds.

## Installation

Install from PyPI only:

```bash
pip install nutanix-ztf==2.1.1
uv pip install --prerelease=allow nutanix-ztf==2.1.1
```

## Upgrade notes

1. **Replace 2.1.0 pins with 2.1.1.** 2.1.0 is yanked on PyPI after
   2.1.1 is published, so new installs skip it.
2. **No configuration or state changes.**
