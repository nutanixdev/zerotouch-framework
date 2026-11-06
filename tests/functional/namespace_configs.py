"""Entity test configurations for functional lifecycle tests.

Each configuration defines what to create/destroy and which PC to target.
Configs are parameterised with a ``run_id`` integer to guarantee uniqueness.

Usage::

    from tests.functional.namespace_configs import get_entity_configs
    configs = get_entity_configs(run_id=12345, creds={"host": ..., ...})
"""

from __future__ import annotations

from typing import Any


def _domain_block(
    creds: dict[str, str],
    *,
    data: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single-domain config dict with credentials injected.

    Args:
        creds: Dict with ``host``, ``username``, ``password``.
        data: Optional data-source queries.
        resources: Optional resources to manage.

    Returns:
        Complete ``domains`` block for ``input.yml``.
    """
    domain: dict[str, Any] = {
        "host": creds["host"],
        "username": creds["username"],
        "password": creds["password"],
    }
    if data:
        domain["data"] = data
    if resources:
        domain["resources"] = resources
    return {"domains": {"test_domain": domain}}


# ------------------------------------------------------------------
# Per-entity config builders
# ------------------------------------------------------------------

DOMAIN_NAME = "test_domain"


def cluster_profile_config(run_id: int, creds: dict[str, str]) -> dict[str, Any]:
    """Clustermgmt cluster_profile: standalone, simple CRUD.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.
    """
    return _domain_block(
        creds,
        resources={
            "cluster_profile": {
                f"ztf_func_{run_id}": {
                    "body": {
                        "name": f"ztf-func-{run_id}-profile",
                        "description": "ZTF functional test cluster profile",
                    }
                }
            }
        },
    )


def storage_container_config(
    run_id: int,
    creds: dict[str, str],
    cluster_filter: str = "name eq 'nested-grove4-2'",
) -> dict[str, Any]:
    """Clustermgmt storage_container: requires X_Cluster_Id from data source.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.
        cluster_filter: OData filter to select target PE cluster.
    """
    return _domain_block(
        creds,
        data={
            "cluster": {
                "target_cluster": {"filter": cluster_filter},
            }
        },
        resources={
            "storage_container": {
                f"ztf_func_{run_id}": {
                    "params": {
                        "X_Cluster_Id": ("{data.cluster.target_cluster.data.0.extId}"),
                    },
                    "body": {
                        "name": f"ztf-func-{run_id}-sc",
                    },
                }
            }
        },
    )


def category_config(run_id: int, creds: dict[str, str]) -> dict[str, Any]:
    """Prism category: simple key/value CRUD.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.
    """
    return _domain_block(
        creds,
        resources={
            "category": {
                f"ztf_func_{run_id}": {
                    "body": {
                        "key": f"ZtfFunc{run_id}",
                        "value": "Testing",
                        "description": "ZTF functional test category",
                    }
                }
            }
        },
    )


def vmm_image_config(run_id: int, creds: dict[str, str]) -> dict[str, Any]:
    """VMM vmm_image: standalone ISO image, simple CRUD.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.
    """
    return _domain_block(
        creds,
        resources={
            "vmm_image": {
                f"ztf_func_{run_id}": {
                    "body": {
                        "name": f"ztf-func-{run_id}-image",
                        "description": "ZTF functional test image",
                        "type": "ISO_IMAGE",
                        "source": {
                            "$objectType": "vmm.v4.content.UrlSource",
                            "url": (
                                "http://endor.dyn.nutanix.com/GoldImages"
                                "/ISOs/CentOS-7.0-1406-x86_64-Minimal.iso"
                            ),
                            "shouldAllowInsecureUrl": True,
                        },
                    }
                }
            }
        },
    )


def role_config(run_id: int, creds: dict[str, str]) -> dict[str, Any]:
    """IAM role: needs iam_operation data source for operation ext_ids.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.
    """
    return _domain_block(
        creds,
        data={
            "iam_operation": {
                "view_role": {"filter": "displayName eq 'View_Role'"},
            }
        },
        resources={
            "role": {
                f"ztf_func_{run_id}": {
                    "body": {
                        "displayName": f"ztf-func-{run_id}-role",
                        "operations": [
                            "{data.iam_operation.view_role.data.0.extId}",
                        ],
                    }
                }
            }
        },
    )


def volume_group_config(
    run_id: int,
    creds: dict[str, str],
    cluster_filter: str = "name eq 'nested-grove4-2'",
) -> dict[str, Any]:
    """Volumes volume_group: needs cluster reference.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.
        cluster_filter: OData filter to select target PE cluster.
    """
    return _domain_block(
        creds,
        data={
            "cluster": {
                "target_cluster": {"filter": cluster_filter},
            }
        },
        resources={
            "volume_group": {
                f"ztf_func_{run_id}": {
                    "body": {
                        "name": f"ztf-func-{run_id}-vg",
                        "description": "ZTF functional test volume group",
                        "clusterReference": (
                            "{data.cluster.target_cluster.data.0.extId}"
                        ),
                        "sharingStatus": "NOT_SHARED",
                        "usageType": "USER",
                        "protocol": "ISCSI",
                    }
                }
            }
        },
    )


# ------------------------------------------------------------------
# Dependency chain: role that references a data-source resolved
# iam_operation ext_id -- verifies data-source -> resource ordering
# ------------------------------------------------------------------


def dependency_chain_config(run_id: int, creds: dict[str, str]) -> dict[str, Any]:
    """Multi-resource config: category + storage_container in the same domain.

    Creates a category (standalone) and a storage_container (depends on
    cluster data source) in a single apply. Validates that ZTF handles
    mixed-dependency ordering within the same domain correctly.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.
    """
    return _domain_block(
        creds,
        data={
            "cluster": {
                "target_cluster": {
                    "filter": "name eq 'nested-grove4-2'",
                },
            },
        },
        resources={
            "category": {
                f"ztf_dep_cat_{run_id}": {
                    "body": {
                        "key": f"ZtfDep{run_id}",
                        "value": "DepChain",
                        "description": "Dependency chain test category",
                    }
                }
            },
            "storage_container": {
                f"ztf_dep_sc_{run_id}": {
                    "params": {
                        "X_Cluster_Id": ("{data.cluster.target_cluster.data.0.extId}"),
                    },
                    "body": {
                        "name": f"ztf-dep-{run_id}-sc",
                    },
                }
            },
        },
    )


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

ENTITY_CONFIGS: list[dict[str, Any]] = [
    {
        "id": "clustermgmt__cluster_profile",
        "namespace": "clustermgmt",
        "entity": "cluster_profile",
        "pc_target": "nested_7_5",
        "crud_supported": True,
        "builder": cluster_profile_config,
    },
    {
        "id": "clustermgmt__storage_container",
        "namespace": "clustermgmt",
        "entity": "storage_container",
        "pc_target": "nested_7_5",
        "crud_supported": True,
        "builder": storage_container_config,
    },
    {
        "id": "prism__category",
        "namespace": "prism",
        "entity": "category",
        "pc_target": "nested_7_5",
        "crud_supported": True,
        "builder": category_config,
    },
    {
        "id": "vmm__vmm_image",
        "namespace": "vmm",
        "entity": "vmm_image",
        "pc_target": "nested_7_5",
        "crud_supported": True,
        "builder": vmm_image_config,
    },
    {
        "id": "iam__role",
        "namespace": "iam",
        "entity": "role",
        "pc_target": "nested_7_5",
        "crud_supported": True,
        "builder": role_config,
    },
    {
        "id": "volumes__volume_group",
        "namespace": "volumes",
        "entity": "volume_group",
        "pc_target": "nested_7_5",
        "crud_supported": True,
        "builder": volume_group_config,
    },
]

DEPENDENCY_CHAIN_CONFIGS: list[dict[str, Any]] = [
    {
        "id": "dep__category_plus_storage_container",
        "namespace": "mixed",
        "entities": ["category", "storage_container"],
        "pc_target": "nested_7_5",
        "builder": dependency_chain_config,
        "resource_names": {
            "category": "ztf_dep_cat_{run_id}",
            "storage_container": "ztf_dep_sc_{run_id}",
        },
    },
]


def get_entity_configs(
    run_id: int,
    creds: dict[str, str],
    namespace_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return entity configs with input YAML built from credentials.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict (``host``, ``username``, ``password``).
        namespace_filter: If set, return only configs for this namespace.

    Returns:
        List of dicts, each containing the original registry fields plus
        an ``input_config`` key with the complete YAML-ready dict.
    """
    result: list[dict[str, Any]] = []
    for entry in ENTITY_CONFIGS:
        if namespace_filter and entry["namespace"] != namespace_filter:
            continue
        cfg = dict(entry)
        cfg["input_config"] = cfg["builder"](run_id, creds)
        cfg["resource_name"] = f"ztf_func_{run_id}"
        cfg["domain_name"] = DOMAIN_NAME
        result.append(cfg)
    return result


def get_dependency_chain_configs(
    run_id: int,
    creds: dict[str, str],
) -> list[dict[str, Any]]:
    """Return dependency chain configs with input YAML built from credentials.

    Args:
        run_id: Unique test run identifier.
        creds: PC credentials dict.

    Returns:
        List of dicts for dependency chain tests.
    """
    result: list[dict[str, Any]] = []
    for entry in DEPENDENCY_CHAIN_CONFIGS:
        cfg = dict(entry)
        cfg["input_config"] = cfg["builder"](run_id, creds)
        cfg["resource_names_resolved"] = {
            entity: name.format(run_id=run_id)
            for entity, name in cfg["resource_names"].items()
        }
        cfg["domain_name"] = DOMAIN_NAME
        result.append(cfg)
    return result
