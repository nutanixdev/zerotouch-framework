"""Tests for ztf.provider.provider (new domain-grouped format)."""

import logging
import threading
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from ztf.config.config_loader import load_config
from ztf.config.interpolation import (
    InterpolationContext,
    extract_cross_domain_data_refs,
    extract_cross_domain_refs,
    resolve,
)
from ztf.provider.provider import (
    Provider,
    _apply_ignore_changes,
    _compute_field_diff,
    _extract_parent_kwargs,
    _merge_ignored_fields,
    set_entity_thread_name,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_global_config():
    return {
        "config": {
            "port": 9440,
            "debug": False,
            "verify_ssl": True,
            "dry_run": False,
            "connect_timeout": 10,
            "read_timeout": 60,
        }
    }


@pytest.fixture
def entity_map_patch(monkeypatch):
    """Patch entity_metadata_map with a minimal valid structure."""
    monkeypatch.setattr(
        "ztf.provider.provider.entity_metadata_map",
        {
            "entityA": {
                "sdk_name": "sdk_mod",
                "model_class_path": "ModelA",
                "api_class_path": "api_a",
                "create_method_name": "create_entityA",
                "update_method_name": "update_entityA_by_id",
                "list_method_name": "list_entityAs",
                "operations": [],
                "filter_format": "name eq '{name}'",
                "update_supported": True,
            },
            "prism_task": {
                "api_class_path": "tasks_api",
                "api_instance": None,
                "sdk_name": "ntnx_prism_py_client",
                "model_class_path": "prism.v4.config.Task",
                "filter_format": "ext_id eq '{ext_id}'",
            },
        },
    )


@pytest.fixture
def new_config():
    """Minimal valid new-format config (already processed by load_config)."""
    return load_config(
        {
            "variables": {"env": "prod"},
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "pass",
                    "resources": {
                        "entityA": {
                            "res1": {"body": {"foo": "bar"}},
                        }
                    },
                }
            },
        }
    )


@pytest.fixture
def new_config_with_ops():
    """Config with operations on a resource."""
    return load_config(
        {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "pass",
                    "resources": {
                        "entityA": {
                            "res1": {
                                "body": {"foo": "bar"},
                                "operations": [
                                    {"type": "do_something", "body": {"x": 1}},
                                ],
                            },
                        }
                    },
                }
            },
        }
    )


@pytest.fixture
def new_state():
    """Minimal previous state in new format."""
    return {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {
                    "entityA": {
                        "res1": {
                            "extId": "abc123",
                            "body": {"foo": "baz"},
                        }
                    }
                },
            }
        }
    }


@pytest.fixture
def matching_state():
    """State matching the input (no change needed)."""
    return {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {
                    "entityA": {
                        "res1": {
                            "extId": "abc123",
                            "body": {"foo": "bar"},
                        }
                    }
                },
            }
        }
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(global_cfg, config, state=None):
    """Create a Provider with DomainEntityHandler mocked.

    ``strip_readonly_fields`` defaults to a passthrough so existing
    callers' ``sanitize_entity_data``/``latest`` bodies flow through
    unchanged unless a test explicitly overrides it to assert on
    readOnly-stripping behavior.
    """
    with patch("ztf.provider.provider.DomainEntityHandler", autospec=True):
        provider = Provider(deepcopy(global_cfg), deepcopy(config), deepcopy(state))
    for handler in provider.domain_entity_handler_map.values():
        handler.strip_readonly_fields.side_effect = (
            lambda _entity, body, operation="create": body
        )
    return provider


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestProviderInit:
    def test_init_creates_handler(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        assert "lab1" in provider.domain_entity_handler_map

    def test_init_maps_domain_name_to_host(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        assert provider.domain_name_to_host["lab1"] == "1.2.3.4"

    def test_init_populates_resource_map(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        assert "res1" in provider.domain_entity_resource_map["lab1"]["entityA"]

    def test_init_populates_resource_name_map(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        assert "res1" in provider.domain_resource_name_map["lab1"]

    def test_init_with_previous_state(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        assert "res1" in provider.previous_domain_resource_name_map["lab1"]
        prev_res = provider.previous_domain_entity_resource_map["lab1"]["entityA"][
            "res1"
        ]
        assert prev_res["extId"] == "abc123"

    def test_init_missing_credentials_raises(self, minimal_global_config):
        config = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                }
            }
        }
        with pytest.raises(ValueError, match="username"):
            _make_provider(minimal_global_config, config)

    def test_init_without_config_subdict_does_not_crash(self):
        """``global_config_data`` without a ``config`` sub-dict must not KeyError.

        Regression for Phase B fix: earlier code assumed the caller always
        built ``{"config": {...}}`` and crashed with ``KeyError: 'config'``
        when handed a bare dict.
        """
        bare_global = {}  # deliberately missing "config"
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                    }
                }
            }
        )
        provider = _make_provider(bare_global, config)
        # setdefault populated "config" during domain_api_config build
        built = provider.domain_global_config_map["lab1"]
        assert built["config"]["host"] == "1.2.3.4"
        assert built["config"]["username"] == "admin"
        assert built["config"]["password"] == "pass"

    def test_init_empty_resources_allowed(self, minimal_global_config):
        """A domain with empty resources registers an empty resource-name set."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {},
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        assert provider.domain_resource_name_map["lab1"] == set()

    def test_init_empty_resources_with_prev_state_creates_handler(
        self, minimal_global_config
    ):
        """A domain with empty resources but previous state gets a handler."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                    }
                }
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "entityA": {"res1": {"extId": "abc", "body": {"x": 1}}}
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        assert "lab1" in provider.domain_entity_handler_map

    def test_init_restores_entity_order_from_state(self, minimal_global_config):
        """Entity ordering stored in state is restored on init."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                    }
                }
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "_entity_order": ["entityB", "entityA"],
                    "resources": {"entityA": {"r": {"extId": "abc", "body": {"x": 1}}}},
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        assert provider.domain_entity_order["lab1"] == ["entityB", "entityA"]

    def test_init_output_skeleton(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        assert "lab1" in provider.output_skeleton["domains"]

    def test_state_only_domain_gets_credentials(self, minimal_global_config):
        """A domain in state but not config gets credentials via host match."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                    }
                }
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {"entityA": {"r": {"extId": "a1", "body": {"x": 1}}}},
                },
                "old-domain": {
                    "host": "1.2.3.4",
                    "resources": {"entityA": {"r2": {"extId": "a2", "body": {"y": 2}}}},
                },
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        assert "old-domain" in provider.domain_entity_handler_map

    def test_shared_host_reuses_handler(self, minimal_global_config):
        """Two domains on the same host share a single handler."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r1": {"body": {"x": 1}}}},
                    },
                    "lab2": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r2": {"body": {"y": 2}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        assert (
            provider.domain_entity_handler_map["lab1"]
            is provider.domain_entity_handler_map["lab2"]
        )


# ---------------------------------------------------------------------------
# Dependency graph and topological sort
# ---------------------------------------------------------------------------


class TestDependencyGraph:
    def test_no_tokens_no_edges(self):
        domain_entities = {
            "entityA": {"res_a": {"body": {"name": "plain"}}},
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        assert in_degree["res_a"] == 0
        sorted_resources = Provider._topological_sort(graph, in_degree, domain_entities)
        assert sorted_resources == ["res_a"]

    def test_inferred_from_tokens(self):
        domain_entities = {
            "entityA": {
                "res_a": {
                    "body": {"ref": "{res_b.ext_id}", "ref2": "{res_c.ext_id}"},
                },
            },
            "entityB": {"res_b": {"body": {"name": "b"}}},
            "entityC": {"res_c": {"body": {"name": "c"}}},
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        assert in_degree["res_a"] == 2
        sorted_resources = Provider._topological_sort(graph, in_degree, domain_entities)
        assert sorted_resources.index("res_b") < sorted_resources.index("res_a")
        assert sorted_resources.index("res_c") < sorted_resources.index("res_a")

    def test_same_entity_type_dependency(self):
        domain_entities = {
            "entityA": {
                "res_a1": {"body": {"ref": "{res_a2.ext_id}"}},
                "res_a2": {"body": {"name": "second"}},
            },
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        assert in_degree["res_a1"] == 1
        assert in_degree["res_a2"] == 0

    def test_explicit_depends_on(self):
        domain_entities = {
            "entityA": {
                "res_a": {
                    "depends_on": ["res_b"],
                    "body": {"name": "a"},
                },
            },
            "entityB": {"res_b": {"body": {"name": "b"}}},
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        assert in_degree["res_a"] == 1
        sorted_resources = Provider._topological_sort(graph, in_degree, domain_entities)
        assert sorted_resources.index("res_b") < sorted_resources.index("res_a")

    def test_depends_on_and_tokens_combined(self):
        domain_entities = {
            "entityA": {
                "res_a": {
                    "depends_on": ["res_c"],
                    "body": {"ref": "{res_b.ext_id}"},
                },
            },
            "entityB": {"res_b": {"body": {"name": "b"}}},
            "entityC": {"res_c": {"body": {"name": "c"}}},
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        assert in_degree["res_a"] == 2

    def test_depends_on_unknown_warns(self, caplog):
        domain_entities = {
            "entityA": {
                "res_a": {
                    "depends_on": ["nonexistent"],
                    "body": {"name": "a"},
                },
            },
        }
        Provider._build_dependency_graph(domain_entities)
        assert "does not match any known resource" in caplog.text

    def test_cycle_detection(self):
        domain_entities = {
            "entityA": {
                "res_a": {"body": {"ref": "{res_b.ext_id}"}},
            },
            "entityB": {
                "res_b": {"body": {"ref": "{res_a.ext_id}"}},
            },
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        with pytest.raises(ValueError, match="Circular dependency"):
            Provider._topological_sort(graph, in_degree, domain_entities)

    def test_cross_entity_type_chain_no_false_cycle(self):
        """subnet -> vpc -> subnet should NOT be a cycle (resource-level graph)."""
        domain_entities = {
            "subnet": {
                "ext_subnet": {"body": {"name": "ext"}},
                "overlay": {"body": {"vpcRef": "{my_vpc.ext_id}"}},
            },
            "vpc": {
                "my_vpc": {"body": {"subnetRef": "{ext_subnet.ext_id}"}},
            },
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        sorted_resources = Provider._topological_sort(graph, in_degree, domain_entities)
        assert sorted_resources.index("ext_subnet") < sorted_resources.index("my_vpc")
        assert sorted_resources.index("my_vpc") < sorted_resources.index("overlay")

    def test_inferred_from_operations(self):
        """Refs inside an operations block order the resource after its deps."""
        domain_entities = {
            "category": {
                "cat_a": {"body": {"key": "A"}},
                "cat_b": {"body": {"key": "B"}},
            },
            "cluster": {
                "cluster_ops": {
                    "operations": [
                        {
                            "type": "associate_categories_to_cluster",
                            "body": {
                                "categories": [
                                    "{cat_a.extId}",
                                    "{cat_b.extId}",
                                ]
                            },
                        }
                    ],
                },
            },
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        assert in_degree["cluster_ops"] == 2
        sorted_resources = Provider._topological_sort(graph, in_degree, domain_entities)
        assert sorted_resources.index("cat_a") < sorted_resources.index("cluster_ops")
        assert sorted_resources.index("cat_b") < sorted_resources.index("cluster_ops")

    def test_inferred_from_params(self):
        """Refs inside a params block create dependency edges."""
        domain_entities = {
            "entityA": {"res_a": {"body": {"name": "a"}}},
            "entityB": {
                "res_b": {
                    "params": {"parentId": "{res_a.extId}"},
                    "body": {"name": "b"},
                },
            },
        }
        graph, in_degree = Provider._build_dependency_graph(domain_entities)
        assert in_degree["res_b"] == 1
        sorted_resources = Provider._topological_sort(graph, in_degree, domain_entities)
        assert sorted_resources.index("res_a") < sorted_resources.index("res_b")


class TestExtractCrossDomainRefs:
    """Tests for extract_cross_domain_refs."""

    def test_detects_cross_domain_token(self):
        data = {"value": "{site_a.uat_source.extId}"}
        refs = extract_cross_domain_refs(data, {"site_a", "site_b"})
        assert refs == {"site_a"}

    def test_ignores_scoped_prefixes(self):
        data = {"ref": "{data.entity.source.data.0.extId}"}
        refs = extract_cross_domain_refs(data, {"data", "site_a"})
        assert refs == set()

    def test_ignores_same_domain_resource_refs(self):
        data = {"ref": "{my_vpc.ext_id}"}
        refs = extract_cross_domain_refs(data, {"site_a"})
        assert refs == set()

    def test_multiple_domains(self):
        data = {
            "a": "{site_a.res1.body.key}",
            "b": "{site_c.res2.extId}",
        }
        refs = extract_cross_domain_refs(data, {"site_a", "site_b", "site_c"})
        assert refs == {"site_a", "site_c"}

    def test_nested_list(self):
        data = [{"x": "{other.res.body.val}"}]
        refs = extract_cross_domain_refs(data, {"other"})
        assert refs == {"other"}

    def test_no_braces_short_circuits(self):
        refs = extract_cross_domain_refs("plain string", {"site_a"})
        assert refs == set()


class TestExtractCrossDomainDataRefs:
    """Tests for extract_cross_domain_data_refs."""

    def test_detects_domain_scoped_data_token(self):
        data = {"value": "{data.site_a.entityA.src.data.0.extId}"}
        refs = extract_cross_domain_data_refs(data, {"site_a", "site_b"})
        assert refs == {"site_a"}

    def test_ignores_flat_data_token(self):
        """A flat {data.entity.source.field} token has no domain segment."""
        data = {"value": "{data.entityA.src.data.0.extId}"}
        refs = extract_cross_domain_data_refs(data, {"site_a"})
        assert refs == set()

    def test_ignores_unknown_domain(self):
        data = {"value": "{data.unknown.entityA.src.data.0.extId}"}
        refs = extract_cross_domain_data_refs(data, {"site_a"})
        assert refs == set()

    def test_no_braces_short_circuits(self):
        refs = extract_cross_domain_data_refs("plain string", {"site_a"})
        assert refs == set()


class TestDomainDependencyOrder:
    """Tests for _build_domain_dependency_order."""

    def test_no_cross_refs_single_wave(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "d1": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    },
                    "d2": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r2": {"body": {"k": 2}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        waves = provider._build_domain_dependency_order()
        assert len(waves) == 1
        assert set(waves[0]) == {"d1", "d2"}

    def test_cross_ref_creates_two_waves(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "category": {
                                "src": {"body": {"key": "Source", "value": "v1"}}
                            }
                        },
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "category": {
                                "ref": {"body": {"val": "{site_a.src.body.value}"}}
                            }
                        },
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        waves = provider._build_domain_dependency_order()
        assert len(waves) == 2
        assert waves[0] == ["site_a"]
        assert waves[1] == ["site_b"]

    def test_circular_cross_domain_raises(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "d1": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "entityA": {"r1": {"body": {"x": "{d2.r2.extId}"}}}
                        },
                    },
                    "d2": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "entityA": {"r2": {"body": {"x": "{d1.r1.extId}"}}}
                        },
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        with pytest.raises(ValueError, match="Circular cross-domain dependency"):
            provider._build_domain_dependency_order()

    def test_cross_ref_in_operations_creates_two_waves(self, minimal_global_config):
        """A cross-domain ref inside an operations block orders the waves."""
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "category": {
                                "src": {"body": {"key": "Source", "value": "v1"}}
                            }
                        },
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "cluster": {
                                "ops": {
                                    "operations": [
                                        {
                                            "type": "associate_categories_to_cluster",
                                            "body": {
                                                "categories": ["{site_a.src.extId}"]
                                            },
                                        }
                                    ]
                                }
                            }
                        },
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        waves = provider._build_domain_dependency_order()
        assert waves == [["site_a"], ["site_b"]]

    def test_data_block_resource_ref_creates_two_waves(self, minimal_global_config):
        """A domain whose only cross-domain dependency lives in its data:
        block (e.g. a filter or passthrough param referencing another
        domain's resource) must still wait for the producer domain."""
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "category": {
                                "src": {"body": {"key": "Source", "value": "v1"}}
                            }
                        },
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "data": {
                            "category": {
                                "lookup": {"filter": "name eq '{site_a.src.extId}'"}
                            }
                        },
                        "resources": {"category": {"ref": {"body": {"val": "x"}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        waves = provider._build_domain_dependency_order()
        assert waves == [["site_a"], ["site_b"]]

    def test_data_block_cross_domain_data_ref_creates_two_waves(
        self, minimal_global_config
    ):
        """A {data.<domain>....} token in a data: block also orders waves."""
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "data": {"category": {"src_lookup": {"filter": "name eq 'x'"}}},
                        "resources": {"category": {"src": {"body": {"key": "Source"}}}},
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "data": {
                            "cluster": {
                                "lookup": {
                                    "hostExtId": (
                                        "{data.site_a.category.src_lookup.data.0.extId}"
                                    )
                                }
                            }
                        },
                        "resources": {"category": {"ref": {"body": {"val": "x"}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        waves = provider._build_domain_dependency_order()
        assert waves == [["site_a"], ["site_b"]]

    def test_empty_resources_domain_without_data_not_in_waves(
        self, minimal_global_config
    ):
        """A resource-less domain (delete-everything) must not occupy an
        apply wave just because domain_data_config stores ``{}`` for it."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    },
                    "lab2": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        waves = provider._build_domain_dependency_order()
        named = {d for wave in waves for d in wave}
        assert "lab1" in named
        assert "lab2" not in named

    def test_data_only_domain_in_waves_and_has_handler(self, minimal_global_config):
        """A domain with data sources but no resources must get a handler
        and occupy a wave so consumers can wait for its cache."""
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "data": {"category": {"src_lookup": {"filter": "name eq 'x'"}}},
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "data": {
                            "cluster": {
                                "lookup": {
                                    "hostExtId": (
                                        "{data.site_a.category.src_lookup.data.0.extId}"
                                    )
                                }
                            }
                        },
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        assert "site_a" in provider.domain_entity_handler_map
        waves = provider._build_domain_dependency_order()
        assert waves == [["site_a"], ["site_b"]]


# ---------------------------------------------------------------------------
# Upsert (create/update)
# ---------------------------------------------------------------------------


ENTITY_A_META = {
    "entityA": {
        "update_supported": True,
    }
}


class TestUpsert:
    def test_create_new_resource(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.create.return_value = "new-ext-id"
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {},
            ctx,
            resource_state,
        )
        assert "res1" in results
        assert results["res1"]["extId"] == "new-ext-id"

    def test_create_stores_full_api_body(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.create.return_value = "new-ext-id"
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {"foo": "api", "extra": "field"}
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {},
            ctx,
            resource_state,
        )
        assert results["res1"]["body"] == {"foo": "api", "extra": "field"}

    def test_create_strips_schema_readonly_fields(
        self, minimal_global_config, new_config
    ):
        """State written after create should route the fetched body
        through the entity handler's schema-driven readOnly stripping, so
        server-managed fields never land in state.yml in the first place."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.create.return_value = "new-ext-id"
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {
            "name": "tiny-linux",
            "createTime": "2026-08-31T15:14:47+00:00",
            "ownerExtId": "ae1c33bd-f0dd-5000-9e36-49247c0d1b67",
        }
        handler.strip_readonly_fields.side_effect = None
        handler.strip_readonly_fields.return_value = {"name": "tiny-linux"}
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {},
            ctx,
            resource_state,
        )

        handler.strip_readonly_fields.assert_called_once_with(
            "entityA",
            {
                "name": "tiny-linux",
                "createTime": "2026-08-31T15:14:47+00:00",
                "ownerExtId": "ae1c33bd-f0dd-5000-9e36-49247c0d1b67",
            },
        )
        assert results["res1"]["body"] == {"name": "tiny-linux"}

    def test_create_fallback_body_on_fetch_error(
        self, minimal_global_config, new_config
    ):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.create.return_value = "new-ext-id"
        handler.get_entity_by_ext_id.side_effect = Exception("fetch failed")
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {},
            ctx,
            resource_state,
        )
        assert results["res1"]["body"] == {"foo": "bar"}

    def test_create_fallback_body_when_get_returns_none(
        self, minimal_global_config, new_config
    ):
        """Action helpers (e.g. fc_create_cluster) return None from GET;
        keep the configured body without treating None as a sanitize error."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.create.return_value = "new-ext-id"
        handler.get_entity_by_ext_id.return_value = None
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {},
            ctx,
            resource_state,
        )
        assert results["res1"]["body"] == {"foo": "bar"}
        handler.sanitize_entity_data.assert_not_called()

    def test_update_changed_resource(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.update.return_value = "abc123"
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
            ctx,
            resource_state,
        )
        assert "res1" in results
        assert results["res1"]["extId"] == "abc123"

    def test_no_change_skips_update(
        self, minimal_global_config, new_config, matching_state
    ):
        provider = _make_provider(minimal_global_config, new_config, matching_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {"res1": {"extId": "abc123", "body": {"foo": "bar"}}},
            ctx,
            resource_state,
        )
        assert "res1" in results
        handler.update.assert_not_called()
        handler.create.assert_not_called()

    def test_no_change_carry_forward_refreshes_params(
        self, minimal_global_config, new_config, matching_state
    ):
        """Regression for 1.8: params/rules must reflect current config.

        When a resource is unchanged (``update_needed=False``) the
        provider carries forward the previous state entry.  Callers that
        interpolate ``{resource.params.*}`` need the current declared
        params, not whatever was persisted on the previous run.
        """
        provider = _make_provider(minimal_global_config, new_config, matching_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        input_resource = {
            "res1": {
                "body": {"foo": "bar"},
                "rules": {"prevent_destroy": True},
                "params": {"env": "prod", "owner": "team-a"},
            }
        }
        prev_resource = {
            "res1": {
                "extId": "abc123",
                "body": {"foo": "bar"},
                "params": {"env": "dev"},
            }
        }
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            input_resource,
            prev_resource,
            ctx,
            resource_state,
        )
        assert "res1" in results
        handler.update.assert_not_called()
        handler.create.assert_not_called()
        assert results["res1"]["params"] == {"env": "prod", "owner": "team-a"}
        assert results["res1"]["rules"] == {"prevent_destroy": True}
        assert results["res1"]["extId"] == "abc123"
        assert resource_state["res1"]["params"] == {"env": "prod", "owner": "team-a"}

    def test_no_change_carry_forward_without_params_keeps_prev(
        self, minimal_global_config, new_config, matching_state
    ):
        """When config declares no params, the previous entry is preserved as-is."""
        provider = _make_provider(minimal_global_config, new_config, matching_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {
                "res1": {
                    "extId": "abc123",
                    "body": {"foo": "bar"},
                    "params": {"env": "dev"},
                }
            },
            ctx,
            resource_state,
        )
        assert results["res1"]["params"] == {"env": "dev"}

    def test_extid_from_input_no_state_skips_create(
        self, minimal_global_config, new_config
    ):
        """Resource with extId in input but no state entry should not create."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {
                "res1": {
                    "extId": "pre-existing-id",
                    "body": {"foo": "bar"},
                    "rules": provider.default_rules,
                }
            },
            {},
            ctx,
            resource_state,
        )
        assert "res1" in results
        assert results["res1"]["extId"] == "pre-existing-id"
        assert results["res1"]["body"] == {"foo": "bar"}
        handler.create.assert_not_called()
        handler.update.assert_not_called()

    def test_operations_run_for_all_resources(
        self, minimal_global_config, new_config, matching_state
    ):
        """Operations run regardless of resource state or extId."""
        provider = _make_provider(minimal_global_config, new_config, matching_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        resource_cfg = {
            "res1": {
                "body": {"foo": "bar"},
                "rules": provider.default_rules,
                "operations": [{"type": "do_something", "body": {"x": 1}}],
            }
        }
        with patch.object(provider, "_run_operation") as run_op:
            provider._prepare_entity_upsert_results(
                "entityA",
                "lab1",
                handler,
                resource_cfg,
                {"res1": {"extId": "abc123", "body": {"foo": "bar"}}},
                ctx,
                resource_state,
            )
        run_op.assert_called_once()

    def test_create_exception_returns_empty(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.create.side_effect = Exception("fail")
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            {},
            ctx,
            resource_state,
        )
        assert "res1" not in results

    def test_update_exception_preserves_prev(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.update.side_effect = Exception("fail")
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables=new_config.get("variables", {}))
        resource_state: dict = {}
        prev = {"res1": {"extId": "abc123", "body": {"foo": "baz"}}}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "bar"}, "rules": provider.default_rules}},
            prev,
            ctx,
            resource_state,
        )
        assert results["res1"]["extId"] == "abc123"
        assert results["res1"]["body"] == {"foo": "baz"}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_success(self, minimal_global_config, new_config, new_state):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.delete.return_value = None

        surviving = provider._prepare_delete_entity_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
        )
        assert surviving == {}

    def test_delete_failure_preserves_resource(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.delete.side_effect = Exception("fail")

        surviving = provider._prepare_delete_entity_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
        )
        assert "res1" in surviving

    def test_prevent_destroy_blocks_delete(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]

        surviving = provider._prepare_delete_entity_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
            rules_map={"res1": {"prevent_destroy": True}},
        )
        assert "res1" in surviving
        handler.delete.assert_not_called()

    def test_delete_skips_missing_ext_id(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.delete = MagicMock()
        surviving = provider._prepare_delete_entity_results(
            "entityA",
            "lab1",
            handler,
            {"res1": {"body": {"foo": "baz"}}},
        )
        assert surviving == {}
        handler.delete.assert_not_called()

    def test_delete_run_results_record_each_future_ext_id(
        self, minimal_global_config, new_config, new_state
    ):
        """Every run_results row must carry its own future's ext_id.

        Regression test for the Phase B fix where the ``as_completed`` loop
        formerly captured the loop variable ``ext_id`` from the submission
        loop and stamped every row with the last-submitted value.
        """
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.delete.return_value = None

        resources = {
            "res-a": {"extId": "ext-A", "body": {"n": 1}},
            "res-b": {"extId": "ext-B", "body": {"n": 2}},
            "res-c": {"extId": "ext-C", "body": {"n": 3}},
        }
        provider._prepare_delete_entity_results("entityA", "lab1", handler, resources)

        run_rows = provider.run_results["lab1"]
        by_name = {row["resource_name"]: row["extId"] for row in run_rows}
        assert by_name == {
            "res-a": "ext-A",
            "res-b": "ext-B",
            "res-c": "ext-C",
        }

    def test_delete_run_results_record_ext_id_on_failure(
        self, minimal_global_config, new_config, new_state
    ):
        """Failed delete futures also record the correct per-future ext_id."""
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]

        def _delete(**kwargs):
            if kwargs["resource_name"] == "res-b":
                raise Exception("boom")

        handler.delete.side_effect = _delete

        resources = {
            "res-a": {"extId": "ext-A", "body": {"n": 1}},
            "res-b": {"extId": "ext-B", "body": {"n": 2}},
            "res-c": {"extId": "ext-C", "body": {"n": 3}},
        }
        surviving = provider._prepare_delete_entity_results(
            "entityA", "lab1", handler, resources
        )
        assert "res-b" in surviving
        assert "res-a" not in surviving
        assert "res-c" not in surviving

        run_rows = provider.run_results["lab1"]
        by_name = {row["resource_name"]: row["extId"] for row in run_rows}
        assert by_name == {
            "res-a": "ext-A",
            "res-b": "ext-B",
            "res-c": "ext-C",
        }
        error_row = next(r for r in run_rows if r["resource_name"] == "res-b")
        assert error_row["extId"] == "ext-B"
        assert "boom" in error_row["error"]


# ---------------------------------------------------------------------------
# ignore_changes
# ---------------------------------------------------------------------------


class TestIgnoreChanges:
    def test_ignored_field_not_compared(self):
        prev = {"config": {"pulseStatus": {"isEnabled": True}, "name": "a"}}
        curr = {"config": {"pulseStatus": {"isEnabled": False}, "name": "a"}}
        stripped_prev, stripped_curr = _apply_ignore_changes(
            prev, curr, ["config.pulseStatus"]
        )
        assert stripped_prev == stripped_curr

    def test_non_ignored_field_still_compared(self):
        prev = {"config": {"name": "a"}}
        curr = {"config": {"name": "b"}}
        stripped_prev, stripped_curr = _apply_ignore_changes(prev, curr, [])
        assert stripped_prev != stripped_curr

    def test_empty_ignore_list(self):
        data = {"a": 1, "b": 2}
        p, c = _apply_ignore_changes(data, data, [])
        assert p == c


class TestMergeIgnoredFields:
    """Tests for _merge_ignored_fields."""

    def test_reverts_ignored_fields_to_prev(self):
        prev = {"key": "old-key", "value": "old-val", "description": "old-desc"}
        curr = {"key": "new-key", "value": "new-val", "description": "new-desc"}
        merged = _merge_ignored_fields(prev, curr, ["key", "value"])
        assert merged["key"] == "old-key"
        assert merged["value"] == "old-val"
        assert merged["description"] == "new-desc"

    def test_empty_ignore_list_returns_curr(self):
        curr = {"a": 1}
        assert _merge_ignored_fields({"a": 2}, curr, []) is curr

    def test_empty_prev_body_returns_curr(self):
        curr = {"a": 1}
        assert _merge_ignored_fields({}, curr, ["a"]) is curr

    def test_ignored_field_not_in_prev_keeps_curr(self):
        prev = {"key": "old"}
        curr = {"key": "new", "extra": "val"}
        merged = _merge_ignored_fields(prev, curr, ["extra"])
        assert merged["extra"] == "val"
        assert merged["key"] == "new"

    def test_does_not_mutate_curr(self):
        prev = {"key": "old"}
        curr = {"key": "new", "desc": "d"}
        _merge_ignored_fields(prev, curr, ["key"])
        assert curr["key"] == "new"


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class TestPlan:
    def test_plan_create(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        plan = provider.plan()
        assert "create" in plan
        assert "update" in plan
        assert "delete" in plan

    def test_plan_no_handler(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        provider.domain_entity_handler_map = {}
        plan = provider.plan()
        assert plan["create"] == {}

    def test_plan_includes_operations(self, minimal_global_config, new_config_with_ops):
        provider = _make_provider(minimal_global_config, new_config_with_ops)
        plan = provider.plan()
        assert "operations" in plan
        if plan["operations"]:
            ops = plan["operations"].get("lab1", {}).get("entityA", [])
            assert any(o["type"] == "do_something" for o in ops)

    def test_plan_fetches_data_sources(self, minimal_global_config, new_config):
        """Plan should call _fetch_data_sources for each domain."""
        provider = _make_provider(minimal_global_config, new_config)
        with patch.object(
            provider, "_fetch_data_sources", return_value=({}, [])
        ) as mock_fetch:
            provider.plan()
            mock_fetch.assert_called_once()
            args, kwargs = mock_fetch.call_args
            assert args == ("lab1", provider.domain_entity_handler_map["lab1"])
            assert isinstance(kwargs.get("ctx"), InterpolationContext)
            assert kwargs.get("strict") is True

    def test_plan_data_source_failure_logs_warning(
        self, minimal_global_config, new_config
    ):
        """Plan should warn and continue if data source fetch fails."""
        provider = _make_provider(minimal_global_config, new_config)
        with patch.object(
            provider,
            "_fetch_data_sources",
            side_effect=RuntimeError("api error"),
        ):
            plan = provider.plan()
            assert "create" in plan

    def test_plan_resolves_cross_domain_resource_ref(self, minimal_global_config):
        """A {domain.resource.field} token in a resource body must resolve
        during plan (against the referenced domain's *previous* state),
        not be left as a literal unresolved token."""
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "category": {
                                "src": {"body": {"value": "v1"}},
                            }
                        },
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {
                            "category": {
                                "ref": {"body": {"val": "{site_a.src.body.value}"}},
                            }
                        },
                    },
                }
            }
        )
        state = {
            "domains": {
                "site_a": {
                    "host": "1.1.1.1",
                    "resources": {
                        "category": {"src": {"extId": "src-1", "body": {"value": "v1"}}}
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        plan = provider.plan()
        creates = plan["create"].get("site_b", {}).get("category", [])
        assert len(creates) == 1
        assert creates[0]["body"]["val"] == "v1"

    def test_plan_resolves_cross_domain_data_ref_in_data_block(
        self, minimal_global_config
    ):
        """A {data.<domain>....} token in a domain's data: block must
        resolve during plan once the producer domain has been visited."""
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "data": {"category": {"lookup": {"filter": "name eq 'x'"}}},
                        "resources": {"category": {"src": {"body": {"value": "v1"}}}},
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "data": {
                            "category": {
                                "lookup2": {
                                    "parentExtId": (
                                        "{data.site_a.category.lookup.data.0.extId}"
                                    )
                                }
                            }
                        },
                        "resources": {"category": {"ref": {"body": {"val": "x"}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        # _make_provider patches DomainEntityHandler with autospec=True, so
        # every DomainEntityHandler(...) call returns the *same* mock
        # instance (mock_class.return_value) regardless of constructor
        # args -- both domains share one handler mock here.
        handler = provider.domain_entity_handler_map["site_a"]
        assert provider.domain_entity_handler_map["site_b"] is handler

        def list_entities_side_effect(entity_type, **kwargs):
            if kwargs.get("_filter") == "name eq 'x'":
                return [MagicMock()]
            return []

        handler.list_entities.side_effect = list_entities_side_effect
        handler.sanitize_entity_data.return_value = {"extId": "cat-1", "name": "x"}

        provider.plan()

        # site_a's lookup result feeds site_b's lookup2 param, proving the
        # data-cache for site_a was persisted and visible to site_b.
        assert (
            provider.domain_data_cache["site_a"]["category"]["lookup"]["data"][0][
                "extId"
            ]
            == "cat-1"
        )
        calls_with_parent = [
            c
            for c in handler.list_entities.call_args_list
            if c.kwargs.get("parentExtId") is not None
        ]
        assert len(calls_with_parent) == 1
        assert calls_with_parent[0].kwargs["parentExtId"] == "cat-1"

    def test_plan_empty_resources_schedules_all_deletes(
        self, minimal_global_config, new_state
    ):
        """Emptying a domain's resources schedules all state resources for deletion."""
        empty_config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, empty_config, new_state)
        plan = provider.plan()
        deleted = plan["delete"].get("lab1", {}).get("entityA", [])
        assert len(deleted) == 1
        assert deleted[0]["resource_name"] == "res1"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_returns_domains(self, minimal_global_config, new_config):
        with patch.object(
            Provider,
            "_run_domain_for_upsert",
            return_value=(
                {"entityA": {"res1": {"extId": "x", "body": {"foo": "bar"}}}},
                "lab1",
            ),
        ):
            provider = _make_provider(minimal_global_config, new_config)
            output = provider.run()
            assert "domains" in output

    def test_run_delete_removed_resources(
        self, minimal_global_config, new_config, new_state
    ):
        # Remove res1 from current config to trigger delete
        config = deepcopy(new_config)
        config["domains"]["lab1"]["resources"]["entityA"] = {
            "res2": {"body": {"x": 1}, "rules": config["defaults"]["rules"]}
        }
        with (
            patch.object(
                Provider,
                "_run_domain_for_upsert",
                return_value=(
                    {"entityA": {"res2": {"extId": "y", "body": {"x": 1}}}},
                    "lab1",
                ),
            ),
            patch.object(
                Provider,
                "_run_domain_for_delete",
                return_value=({}, "lab1"),
            ),
        ):
            provider = _make_provider(minimal_global_config, config, new_state)
            output = provider.run()
            assert "domains" in output

    def test_run_domain_prepopulates_resource_state(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        with (
            patch.object(provider, "_fetch_data_sources", return_value=({}, [])),
            patch.object(provider, "_prepare_entity_upsert_results") as prep,
        ):

            def _spy(*_args, **_kwargs):
                resource_state = _args[6]
                assert "res1" in resource_state
                return {}

            prep.side_effect = _spy
            results, domain_name = provider._run_domain_for_upsert("lab1")
        assert domain_name == "lab1"
        assert results == {}


# ---------------------------------------------------------------------------
# Destroy
# ---------------------------------------------------------------------------


class TestDestroy:
    def test_destroy_deletes_all(self, minimal_global_config, new_config, new_state):
        with patch.object(
            Provider,
            "_run_domain_for_delete",
            return_value=({}, "lab1"),
        ):
            provider = _make_provider(minimal_global_config, new_config, new_state)
            output = provider.destroy()
            assert "domains" in output
            # All resources deleted -> empty domains
            assert output["domains"] == {} or all(
                not d.get("resources") for d in output["domains"].values()
            )

    def test_destroy_forwards_entity_rules(
        self, minimal_global_config, new_config, new_state
    ):
        """Provider.destroy should forward entity_rules_map to _run_domain_for_delete."""
        with patch.object(
            Provider,
            "_run_domain_for_delete",
            return_value=({}, "lab1"),
        ) as mock_del:
            provider = _make_provider(minimal_global_config, new_config, new_state)
            rules = {"lab1": {"entityA": {"res1": {"prevent_destroy": True}}}}
            provider.destroy(entity_rules_map=rules)
            assert mock_del.called
            _, kwargs = mock_del.call_args
            assert kwargs.get("entity_rules_map") == {
                "entityA": {"res1": {"prevent_destroy": True}}
            }


# ---------------------------------------------------------------------------
# Destroy cross-domain ordering (E3)
# ---------------------------------------------------------------------------


def _multi_domain_config(host_a: str = "1.1.1.1", host_b: str = "2.2.2.2") -> dict:
    """Two-domain config where ``lab2`` references ``lab1``."""
    return load_config(
        {
            "domains": {
                "lab1": {
                    "host": host_a,
                    "username": "admin",
                    "password": "pass",
                    "resources": {
                        "entityA": {"a1": {"body": {"name": "producer"}}},
                    },
                },
                "lab2": {
                    "host": host_b,
                    "username": "admin",
                    "password": "pass",
                    "resources": {
                        "entityA": {
                            "b1": {
                                "body": {"link": "{lab1.a1.ext_id}"},
                            }
                        },
                    },
                },
            },
        }
    )


def _multi_domain_state(host_a: str = "1.1.1.1", host_b: str = "2.2.2.2") -> dict:
    """Previous state for the two-domain cross-domain config."""
    return {
        "domains": {
            "lab1": {
                "host": host_a,
                "resources": {
                    "entityA": {
                        "a1": {
                            "extId": "abc-prod",
                            "body": {"name": "producer"},
                        }
                    }
                },
            },
            "lab2": {
                "host": host_b,
                "resources": {
                    "entityA": {
                        "b1": {
                            "extId": "abc-cons",
                            "body": {"link": "abc-prod"},
                        }
                    }
                },
            },
        }
    }


class TestDestroyCrossDomainOrdering:
    """E3 regression suite -- consumers must destroy before producers."""

    def test_destroy_respects_cross_domain_reverse_order(
        self, minimal_global_config
    ) -> None:
        config = _multi_domain_config()
        state = _multi_domain_state()
        call_order: list[str] = []

        def _record(
            self, domain_name, entities_to_delete, entity_rules_map, on_state_change
        ):
            call_order.append(domain_name)
            return ({}, domain_name)

        with patch.object(Provider, "_run_domain_for_delete", new=_record):
            provider = _make_provider(minimal_global_config, config, state)
            provider.destroy()

        assert call_order == ["lab2", "lab1"], (
            "Consumer (lab2) must finish destroying before producer (lab1) "
            "begins; got order: " + repr(call_order)
        )

    def test_destroy_parallelism_preserved_when_no_cross_domain_refs(
        self, minimal_global_config
    ) -> None:
        # Two independent domains -> single wave; both run in parallel.
        config = load_config(
            {
                "domains": {
                    "labA": {
                        "host": "10.0.0.1",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                    },
                    "labB": {
                        "host": "10.0.0.2",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"body": {"y": 2}}}},
                    },
                }
            }
        )
        state = {
            "domains": {
                "labA": {
                    "host": "10.0.0.1",
                    "resources": {"entityA": {"r": {"extId": "a", "body": {"x": 1}}}},
                },
                "labB": {
                    "host": "10.0.0.2",
                    "resources": {"entityA": {"r": {"extId": "b", "body": {"y": 2}}}},
                },
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        waves = provider._build_destroy_domain_waves()
        assert len(waves) == 1
        assert set(waves[0]) == {"labA", "labB"}

    def test_destroy_cross_domain_cycle_raises(self, minimal_global_config) -> None:
        # Cross-domain DAG is built from the current input config (state
        # stores resolved bodies, so tokens only survive there). A cycle
        # in the config is surfaced loudly rather than deadlocking.
        cyclic_config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.1.1.1",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {"a1": {"body": {"x": "{lab2.b1.ext_id}"}}},
                        },
                    },
                    "lab2": {
                        "host": "2.2.2.2",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {"b1": {"body": {"y": "{lab1.a1.ext_id}"}}},
                        },
                    },
                },
            }
        )
        provider = _make_provider(
            minimal_global_config, cyclic_config, _multi_domain_state()
        )
        with pytest.raises(ValueError, match="Circular cross-domain dependency"):
            provider._build_destroy_domain_waves()

    def test_destroy_includes_state_only_domains_as_isolated_nodes(
        self, minimal_global_config
    ) -> None:
        # A domain in previous state but no longer in config (e.g. user
        # removed it from input.yml without first running destroy) must
        # still be destroyed -- it appears as an isolated node and goes
        # in the last wave (no inbound edges -> wave 0 of apply, last
        # wave of destroy).
        config = _multi_domain_config()
        state = _multi_domain_state()
        state["domains"]["labOrphan"] = {
            "host": "3.3.3.3",
            "resources": {"entityA": {"o1": {"extId": "ophan", "body": {"name": "x"}}}},
        }
        provider = _make_provider(minimal_global_config, config, state)
        flat = [d for wave in provider._build_destroy_domain_waves() for d in wave]
        assert set(flat) == {"lab1", "lab2", "labOrphan"}

    def test_destroy_waves_skip_empty_wave_targets(self, minimal_global_config) -> None:
        # When a wave has no resources to delete (e.g. previous state
        # contained the domain but all its resources were removed
        # in-place beforehand), destroy must skip it without raising
        # ``ValueError: max_workers must be greater than 0``.
        config = _multi_domain_config()
        state = _multi_domain_state()
        provider = _make_provider(minimal_global_config, config, state)

        with patch.object(
            Provider,
            "_run_domain_for_delete",
            return_value=({}, "lab1"),
        ) as mock_del:
            provider.destroy()
            # Both domains delivered exactly one delete call -> no empty
            # wave was scheduled.
            assert mock_del.call_count == 2


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_refresh_success(self, minimal_global_config, new_config, new_state):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {"foo": "refreshed"}

        refreshed = provider.refresh_state()
        assert "domains" in refreshed

    def test_refresh_no_handler(self, minimal_global_config, new_config, new_state):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        provider.domain_entity_handler_map = {}
        refreshed = provider.refresh_state()
        assert "domains" in refreshed

    def test_refresh_exception_returns_prev(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.side_effect = Exception("fail")
        refreshed = provider.refresh_state()
        assert "domains" in refreshed

    def test_refresh_single_domain_empty_does_not_raise(
        self, minimal_global_config, new_config
    ):
        """Regression for 1.7: ``ThreadPoolExecutor(max_workers=0)``.

        When a domain's previous state contains no resources, the worker
        count would collapse to ``min(0, ...)`` which raised
        ``ValueError`` from ``ThreadPoolExecutor``.  The clamp to
        ``max(1, ...)`` keeps the executor valid (no futures run).
        """
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        domain, refreshed = provider._refresh_domain("lab1", {})
        assert domain == "lab1"
        assert refreshed["resources"] == {}
        handler.get_entity_by_ext_id.assert_not_called()


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class TestOutputs:
    def test_resolve_outputs(self, minimal_global_config):
        config = load_config(
            {
                "variables": {"env": "prod"},
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {"res1": {"body": {"name": "test"}}},
                        },
                    }
                },
                "outputs": {
                    "my_output": {
                        "value": "{var.env}",
                        "description": "Environment",
                    },
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        outputs = provider.resolve_outputs()
        assert outputs["my_output"]["value"] == "prod"

    def test_resolve_outputs_with_data_cache_single_domain(self, minimal_global_config):
        config = load_config(
            {
                "variables": {},
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"res1": {"body": {"name": "x"}}}},
                    }
                },
                "outputs": {
                    "cluster_id": {
                        "value": "{data.cluster.all.data.0.extId}",
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        provider.domain_data_cache = {
            "lab1": {
                "cluster": {
                    "all": {
                        "data": [{"extId": "c-123"}],
                        "metadata": {"totalAvailableResults": 1},
                    }
                }
            }
        }
        outputs = provider.resolve_outputs()
        assert outputs["cluster_id"]["value"] == "c-123"

    def test_resolve_outputs_with_data_cache_multi_domain(self, minimal_global_config):
        config = load_config(
            {
                "variables": {},
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"res1": {"body": {"name": "x"}}}},
                    }
                },
                "outputs": {
                    "cluster_id": {
                        "value": "{data.lab1.cluster.all.data.0.extId}",
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        provider.domain_data_cache = {
            "lab1": {
                "cluster": {
                    "all": {
                        "data": [{"extId": "c-123"}],
                        "metadata": {"totalAvailableResults": 1},
                    }
                }
            },
            "lab2": {
                "cluster": {
                    "all": {
                        "data": [{"extId": "c-999"}],
                        "metadata": {"totalAvailableResults": 1},
                    }
                }
            },
        }
        outputs = provider.resolve_outputs()
        assert outputs["cluster_id"]["value"] == "c-123"

    def test_resolve_outputs_domain_qualified_works_with_single_domain(
        self, minimal_global_config
    ):
        """Regression: with the namespaced cache, a domain-qualified
        {data.<domain>.*} token now resolves even when there is only one
        domain -- previously the single-domain shape was flat-only, so
        adding a second domain later would have silently broken any
        existing domain-qualified output expression."""
        config = load_config(
            {
                "variables": {},
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"res1": {"body": {"name": "x"}}}},
                    }
                },
                "outputs": {
                    "cluster_id": {
                        "value": "{data.lab1.cluster.all.data.0.extId}",
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        provider.domain_data_cache = {
            "lab1": {
                "cluster": {
                    "all": {
                        "data": [{"extId": "c-123"}],
                        "metadata": {"totalAvailableResults": 1},
                    }
                }
            }
        }
        outputs = provider.resolve_outputs()
        assert outputs["cluster_id"]["value"] == "c-123"

    def test_no_outputs(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        outputs = provider.resolve_outputs()
        assert outputs == {}

    def test_resolve_outputs_merges_resource_state(self, minimal_global_config):
        config = load_config(
            {
                "variables": {},
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"res1": {"body": {"name": "x"}}}},
                    }
                },
                "outputs": {
                    "res_id": {"value": "{res1.ext_id}"},
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        provider.domain_resource_state = {
            "lab1": {"res1": {"extId": "res-123", "body": {"name": "x"}}}
        }
        outputs = provider.resolve_outputs()
        assert outputs["res_id"]["value"] == "res-123"


# ---------------------------------------------------------------------------
# extract_parent_kwargs
# ---------------------------------------------------------------------------


class TestExtractParentKwargs:
    def test_from_params(self, monkeypatch):
        monkeypatch.setattr(
            "ztf.provider.provider.entity_metadata_map",
            {"child": {"parent_id_param": "parentExtId"}},
        )
        resource = {"params": {"parentExtId": "p-123"}, "body": {}}
        result = _extract_parent_kwargs("child", resource)
        assert result == {"parentExtId": "p-123"}

    def test_from_top_level(self, monkeypatch):
        monkeypatch.setattr(
            "ztf.provider.provider.entity_metadata_map",
            {"child": {"parent_id_param": "parentExtId"}},
        )
        resource = {"parentExtId": "p-123", "body": {}}
        result = _extract_parent_kwargs("child", resource)
        assert result == {"parentExtId": "p-123"}

    def test_no_parent(self, monkeypatch):
        monkeypatch.setattr(
            "ztf.provider.provider.entity_metadata_map",
            {"top": {}},
        )
        result = _extract_parent_kwargs("top", {"body": {}})
        assert result == {}

    def test_meta_not_dict(self, monkeypatch):
        monkeypatch.setattr(
            "ztf.provider.provider.entity_metadata_map",
            {"child": "bad-meta"},
        )
        result = _extract_parent_kwargs("child", {"body": {}})
        assert result == {}

    def test_parent_value_missing(self, monkeypatch):
        monkeypatch.setattr(
            "ztf.provider.provider.entity_metadata_map",
            {"child": {"parent_id_param": "parentExtId"}},
        )
        result = _extract_parent_kwargs("child", {"body": {}})
        assert result == {}


# ---------------------------------------------------------------------------
# set_entity_thread_name
# ---------------------------------------------------------------------------


class TestThreadName:
    def test_sets_name(self):
        def dummy():
            return threading.current_thread().name

        wrapped = set_entity_thread_name("test-thread", dummy)
        assert wrapped() == "test-thread"


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


class TestImport:
    def test_import_domain_not_found(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        with pytest.raises(ValueError, match="not found in config"):
            provider.import_resource_data("res1", "nonexistent")

    def test_import_resource_not_found(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        with pytest.raises(ValueError, match="Resource 'nope' not found"):
            provider.import_resource_data("nope", "lab1")


# ---------------------------------------------------------------------------
# Gap 5: Domain failure preserves previous state
# ---------------------------------------------------------------------------


class TestDomainFailurePreservesState:
    def test_upsert_exception_returns_previous_state(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.create.side_effect = Exception("boom")

        with patch.object(
            provider,
            "_fetch_data_sources",
            side_effect=Exception("domain-level failure"),
        ):
            results, domain_name = provider._run_domain_for_upsert("lab1")
            assert domain_name == "lab1"
            assert "entityA" in results
            assert "res1" in results["entityA"]
            assert results["entityA"]["res1"]["extId"] == "abc123"


# ---------------------------------------------------------------------------
# Gap 9: Refresh keeps previous state on error
# ---------------------------------------------------------------------------


class TestRefreshKeepsPreviousOnError:
    def test_refresh_error_keeps_resource(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        error = Exception("API error")
        error.status = 500
        handler.get_entity_by_ext_id.side_effect = error

        refreshed = provider.refresh_state()
        lab1 = refreshed.get("domains", {}).get("lab1", {})
        resources = lab1.get("resources", {}).get("entityA", {})
        assert "res1" in resources
        assert resources["res1"]["extId"] == "abc123"
        assert resources["res1"]["body"] == {"foo": "baz"}

    def test_refresh_none_keeps_previous_without_sanitize(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = None

        refreshed = provider.refresh_state()
        lab1 = refreshed.get("domains", {}).get("lab1", {})
        resources = lab1.get("resources", {}).get("entityA", {})
        assert "res1" in resources
        assert resources["res1"]["extId"] == "abc123"
        assert resources["res1"]["body"] == {"foo": "baz"}
        handler.sanitize_entity_data.assert_not_called()

    def test_refresh_404_removes_resource(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        error = Exception("Not Found")
        error.status = 404
        handler.get_entity_by_ext_id.side_effect = error

        refreshed = provider.refresh_state()
        lab1 = refreshed.get("domains", {}).get("lab1", {})
        resources = lab1.get("resources", {})
        assert "entityA" not in resources


class TestRefreshStripsReadonlyFields:
    def test_refresh_strips_schema_readonly_fields(
        self, minimal_global_config, new_config, new_state
    ):
        """Refresh should route the live body through the entity handler's
        schema-driven readOnly stripping before diffing/storing it, so
        server-managed fields (createTime, ownerExtId, ...) never show up
        as spurious drift."""
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {
            "name": "tiny-linux",
            "createTime": "2026-08-31T15:14:47+00:00",
            "ownerExtId": "ae1c33bd-f0dd-5000-9e36-49247c0d1b67",
        }
        handler.strip_readonly_fields.side_effect = None
        handler.strip_readonly_fields.return_value = {"name": "tiny-linux"}

        refreshed = provider.refresh_state()

        handler.strip_readonly_fields.assert_called_once_with(
            "entityA",
            {
                "name": "tiny-linux",
                "createTime": "2026-08-31T15:14:47+00:00",
                "ownerExtId": "ae1c33bd-f0dd-5000-9e36-49247c0d1b67",
            },
        )
        body = refreshed["domains"]["lab1"]["resources"]["entityA"]["res1"]["body"]
        assert body == {"name": "tiny-linux"}


# ---------------------------------------------------------------------------
# Gap 8: Refresh stores full body
# ---------------------------------------------------------------------------


class TestRefreshFullBody:
    def test_refresh_stores_all_api_fields(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {
            "foo": "refreshed",
            "new_field": "from_api",
        }

        refreshed = provider.refresh_state()
        lab1 = refreshed.get("domains", {}).get("lab1", {})
        body = lab1["resources"]["entityA"]["res1"]["body"]
        assert body["foo"] == "refreshed"
        assert body["new_field"] == "from_api"

    def test_refresh_preserves_rules(self, minimal_global_config):
        """Rules persisted in state must survive a refresh cycle."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "rules": {"prevent_destroy": True},
                                    "body": {"foo": "bar"},
                                },
                            }
                        },
                    }
                },
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "entityA": {
                            "res1": {
                                "extId": "abc-123",
                                "body": {"foo": "bar"},
                                "rules": {"prevent_destroy": True},
                            }
                        }
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {"foo": "refreshed"}

        refreshed = provider.refresh_state()
        entry = refreshed["domains"]["lab1"]["resources"]["entityA"]["res1"]
        assert entry["rules"] == {"prevent_destroy": True}
        assert entry["body"]["foo"] == "refreshed"


# ---------------------------------------------------------------------------
# Gap 6: prevent_destroy enforced during apply
# ---------------------------------------------------------------------------


class TestPreventDestroyInApply:
    def test_run_passes_rules_to_delete(self, minimal_global_config, new_state):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res2": {"body": {"x": 1}},
                            }
                        },
                    }
                },
            }
        )
        with (
            patch.object(
                Provider,
                "_run_domain_for_upsert",
                return_value=(
                    {"entityA": {"res2": {"extId": "y", "body": {"x": 1}}}},
                    "lab1",
                ),
            ),
            patch.object(
                Provider,
                "_run_domain_for_delete",
                return_value=({}, "lab1"),
            ) as mock_delete,
        ):
            provider = _make_provider(minimal_global_config, config, new_state)
            provider.run()
            if mock_delete.called:
                _, kwargs = mock_delete.call_args
                assert "entity_rules_map" in kwargs

    def test_state_fallback_blocks_delete_of_removed_resource(
        self, minimal_global_config
    ):
        """When a resource with prevent_destroy is removed from config,
        the rule persisted in state should still block deletion."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {},
                    }
                },
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "entityA": {
                            "protected_res": {
                                "extId": "prot-123",
                                "body": {"key": "Protected"},
                                "rules": {"prevent_destroy": True},
                            }
                        }
                    },
                }
            }
        }
        with (
            patch.object(Provider, "_run_domain_for_upsert", return_value=({}, "lab1")),
            patch.object(
                Provider,
                "_run_domain_for_delete",
                wraps=None,
                return_value=(
                    {
                        "entityA": {
                            "protected_res": state["domains"]["lab1"]["resources"][
                                "entityA"
                            ]["protected_res"]
                        }
                    },
                    "lab1",
                ),
            ) as mock_delete,
        ):
            provider = _make_provider(minimal_global_config, config, state)
            provider.run()
            if mock_delete.called:
                _, kwargs = mock_delete.call_args
                rules_map = kwargs["entity_rules_map"]
                assert rules_map["entityA"]["protected_res"]["prevent_destroy"] is True

    def test_config_rules_override_state_rules(self, minimal_global_config):
        """When config explicitly sets prevent_destroy: false, it overrides
        the state-persisted rule and deletion proceeds."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "protected_res": {
                                    "rules": {"prevent_destroy": False},
                                    "body": {"key": "Protected"},
                                },
                            }
                        },
                    }
                },
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "entityA": {
                            "protected_res": {
                                "extId": "prot-123",
                                "body": {"key": "Old-Protected"},
                                "rules": {"prevent_destroy": True},
                            }
                        }
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.delete = MagicMock(return_value={"success": True})

        surviving = provider._prepare_delete_entity_results(
            "entityA",
            "lab1",
            handler,
            {"protected_res": {"extId": "prot-123", "body": {"key": "Protected"}}},
            rules_map={"protected_res": {"prevent_destroy": False}},
        )
        assert "protected_res" not in surviving


# ---------------------------------------------------------------------------
# Gap 4: Incremental state writes (on_state_change callback)
# ---------------------------------------------------------------------------


class TestIncrementalStateWrites:
    def test_run_calls_on_state_change(self, minimal_global_config, new_config):
        callback = MagicMock()

        def _fake_upsert(domain_name, on_state_change=None):
            results = {"entityA": {"res1": {"extId": "x", "body": {"foo": "bar"}}}}
            if on_state_change:
                on_state_change({"domains": {}})
            return results, domain_name

        with patch.object(Provider, "_run_domain_for_upsert", side_effect=_fake_upsert):
            provider = _make_provider(minimal_global_config, new_config)
            provider.run(on_state_change=callback)
            assert callback.called

    def test_destroy_calls_on_state_change(
        self, minimal_global_config, new_config, new_state
    ):
        callback = MagicMock()

        def _fake_delete(
            domain_name, entities_to_delete, entity_rules_map=None, on_state_change=None
        ):
            if on_state_change:
                on_state_change({"domains": {}})
            return {}, domain_name

        with patch.object(Provider, "_run_domain_for_delete", side_effect=_fake_delete):
            provider = _make_provider(minimal_global_config, new_config, new_state)
            provider.destroy(on_state_change=callback)
            assert callback.called


# ---------------------------------------------------------------------------
# Graceful shutdown / partial state
# ---------------------------------------------------------------------------


class TestGracefulShutdown:
    def test_request_shutdown_sets_flag(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        assert not provider._shutdown_requested.is_set()
        provider.request_shutdown()
        assert provider._shutdown_requested.is_set()

    def test_get_partial_state_empty(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        state = provider.get_partial_state()
        assert state == {"domains": {}}

    def test_update_partial_results_calls_callback(
        self, minimal_global_config, new_config
    ):
        provider = _make_provider(minimal_global_config, new_config)
        callback = MagicMock()
        domain_results = {"entityA": {"res1": {"extId": "x", "body": {}}}}
        provider._update_partial_results("lab1", domain_results, callback)
        assert callback.called
        assert provider._partial_results["lab1"] == domain_results

    def test_update_partial_results_no_callback(
        self, minimal_global_config, new_config
    ):
        provider = _make_provider(minimal_global_config, new_config)
        domain_results = {"entityA": {"res1": {"extId": "x", "body": {}}}}
        provider._update_partial_results("lab1", domain_results, None)
        assert provider._partial_results["lab1"] == domain_results

    def test_get_partial_state_after_updates(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        domain_results = {"entityA": {"res1": {"extId": "x", "body": {"a": 1}}}}
        provider._update_partial_results("lab1", domain_results, None)
        state = provider.get_partial_state()
        res = state["domains"]["lab1"]["resources"]["entityA"]["res1"]
        assert res["extId"] == "x"

    def test_shutdown_stops_upsert_loop(self, minimal_global_config, entity_map_patch):
        """When shutdown is requested, upsert should stop processing
        remaining resources and return whatever was completed."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "r1": {"body": {"name": "first"}},
                                "r2": {"body": {"name": "second"}},
                            },
                        },
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        call_count = 0

        def _create_side_effect(entity, data, resource_name=None):
            nonlocal call_count
            call_count += 1
            provider.request_shutdown()
            return f"ext-{call_count}"

        handler.create.side_effect = _create_side_effect
        handler.read = MagicMock(return_value=None)

        results, _ = provider._run_domain_for_upsert("lab1")
        assert call_count == 1, "Should stop after first resource on shutdown"

    def test_shutdown_stops_delete_loop(
        self, minimal_global_config, new_config, new_state, entity_map_patch
    ):
        """When shutdown is requested during delete, remaining resources
        should be kept in surviving state."""
        provider = _make_provider(minimal_global_config, new_config, new_state)
        provider.request_shutdown()
        entities = {"entityA": {"res1": {"extId": "e1", "body": {}}}}
        surviving, _ = provider._run_domain_for_delete("lab1", entities)
        assert "entityA" in surviving
        assert "res1" in surviving["entityA"]

    def test_run_skips_delete_phase_on_shutdown(
        self, minimal_global_config, entity_map_patch
    ):
        """If shutdown is requested during upsert, the delete phase
        should be skipped entirely."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r1": {"body": {"x": 1}}}},
                    }
                }
            }
        )
        prev_state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "entityA": {
                            "r1": {"extId": "e1", "body": {"x": 1}},
                            "r_old": {"extId": "e2", "body": {"x": 2}},
                        }
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, prev_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        def _upsert_with_shutdown(domain_name, on_state_change=None):
            provider.request_shutdown()
            return {"entityA": {"r1": {"extId": "e1", "body": {"x": 1}}}}, domain_name

        with patch.object(
            provider, "_run_domain_for_upsert", side_effect=_upsert_with_shutdown
        ):
            provider.run()
        handler.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Gap 7: create_before_destroy
# ---------------------------------------------------------------------------


class TestCreateBeforeDestroy:
    def test_replace_when_update_not_supported(self, minimal_global_config, new_state):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "body": {"foo": "bar"},
                                    "rules": {"create_before_destroy": True},
                                },
                            }
                        },
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = {
            "entityA": {
                "update_supported": False,
            }
        }
        handler.create.return_value = "new-ext-id"
        handler.delete.return_value = None

        ctx = InterpolationContext(variables={})
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {
                "res1": {
                    "body": {"foo": "bar"},
                    "rules": {"create_before_destroy": True},
                }
            },
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
            ctx,
            resource_state,
        )
        assert "res1" in results
        assert results["res1"]["extId"] == "new-ext-id"
        handler.create.assert_called_once()
        handler.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Gap 3: Field-level diff in plan
# ---------------------------------------------------------------------------


class TestFieldLevelDiff:
    def test_compute_field_diff_added(self):
        diff = _compute_field_diff({}, {"name": "new"})
        assert diff["added"] == {"name": "new"}
        assert diff["removed"] == {}
        assert diff["changed"] == {}

    def test_compute_field_diff_removed(self):
        diff = _compute_field_diff({"name": "old"}, {})
        assert diff["removed"] == {"name": "old"}

    def test_compute_field_diff_changed(self):
        diff = _compute_field_diff({"name": "old"}, {"name": "new"})
        assert diff["changed"] == {"name": {"old": "old", "new": "new"}}

    def test_compute_field_diff_no_change(self):
        diff = _compute_field_diff({"name": "same"}, {"name": "same"})
        assert diff["added"] == {}
        assert diff["removed"] == {}
        assert diff["changed"] == {}

    def test_plan_update_includes_diff_fields(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        plan = provider.plan()
        updates = plan.get("update", {}).get("lab1", {}).get("entityA", [])
        assert len(updates) == 1
        assert "diff_fields" in updates[0]
        diff = updates[0]["diff_fields"]
        assert "changed" in diff
        assert "foo" in diff["changed"]

    def test_plan_update_diff_excludes_server_only_fields(self, minimal_global_config):
        """Server-managed fields in state but not in input must not appear as removed."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "body": {
                                        "key": "AppTier",
                                        "value": "SSH",
                                        "description": "NVD1",
                                    }
                                },
                            }
                        },
                    }
                },
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "entityA": {
                            "res1": {
                                "extId": "abc-123",
                                "body": {
                                    "key": "AppTier",
                                    "value": "SSH",
                                    "type": "USER",
                                    "description": "NVD",
                                    "extId": "abc-123",
                                },
                            }
                        }
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        plan = provider.plan()
        updates = plan.get("update", {}).get("lab1", {}).get("entityA", [])
        assert len(updates) == 1
        diff = updates[0]["diff_fields"]
        assert diff["removed"] == {}
        assert diff["added"] == {}
        assert "description" in diff["changed"]
        assert diff["changed"]["description"] == {"old": "NVD", "new": "NVD1"}

    def test_plan_diff_excludes_ignored_fields(self, minimal_global_config):
        """Fields in ignore_changes must not appear in the plan diff."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "rules": {
                                        "ignore_changes": ["key", "value"],
                                    },
                                    "body": {
                                        "key": "CHANGED-Key",
                                        "value": "CHANGED-Value",
                                        "description": "new-desc",
                                    },
                                },
                            }
                        },
                    }
                },
            }
        )
        state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "entityA": {
                            "res1": {
                                "extId": "abc-123",
                                "body": {
                                    "key": "Original-Key",
                                    "value": "Original-Value",
                                    "description": "old-desc",
                                },
                            }
                        }
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        plan = provider.plan()
        updates = plan.get("update", {}).get("lab1", {}).get("entityA", [])
        assert len(updates) == 1
        diff = updates[0]["diff_fields"]
        assert "key" not in diff["changed"]
        assert "value" not in diff["changed"]
        assert "description" in diff["changed"]
        assert diff["changed"]["description"] == {
            "old": "old-desc",
            "new": "new-desc",
        }

    def test_plan_extid_from_input_no_state(self, minimal_global_config):
        """Resource with extId in input but not in state shows no-change, not create."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "extId": "pre-existing-id",
                                    "body": {"name": "existing"},
                                }
                            }
                        },
                    }
                },
            }
        )
        state: dict = {"domains": {}}
        provider = _make_provider(minimal_global_config, config, state)
        plan = provider.plan()
        creates = plan.get("create", {}).get("lab1", {}).get("entityA", [])
        updates = plan.get("update", {}).get("lab1", {}).get("entityA", [])
        assert creates == []
        assert updates == []


# ---------------------------------------------------------------------------
# _fetch_data_sources
# ---------------------------------------------------------------------------


class TestFetchDataSources:
    def test_filter_success(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = [MagicMock(), MagicMock()]
        handler.sanitize_entity_data.side_effect = [
            {"name": "x", "extId": "e1"},
            {"name": "y", "extId": "e2"},
        ]
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"filter": "name eq 'x'"}}
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert cache["entityA"]["src1"]["data"][0]["name"] == "x"
        assert cache["entityA"]["src1"]["metadata"]["totalAvailableResults"] == 2
        assert failures == []

    def test_no_filter_warns(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {"entityA": {"src1": {}}}
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert cache["entityA"]["src1"]["data"] == []
        assert cache["entityA"]["src1"]["metadata"]["totalAvailableResults"] == 0
        assert failures == []

    def test_no_filter_zero_results_logs_warning(
        self, minimal_global_config, new_config, caplog
    ):
        """Passthrough-only sources (no ``filter``) must still surface an
        explicit "no results" signal on zero items, not just silence until a
        downstream resource fails to resolve against the empty cache."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"hardwareProviderExtId": "hw-1"}}
        }
        with caplog.at_level(logging.WARNING):
            cache, failures = provider._fetch_data_sources("lab1", handler)
        assert cache["entityA"]["src1"]["data"] == []
        assert failures == []
        assert any(
            "entityA/src1" in rec.message and "no results for params" in rec.message
            for rec in caplog.records
        )

    def test_success_logs_item_count(self, minimal_global_config, new_config, caplog):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = [MagicMock()]
        handler.sanitize_entity_data.return_value = {"name": "x", "extId": "e1"}
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"filter": "name eq 'x'"}}
        }
        with caplog.at_level(logging.INFO):
            cache, failures = provider._fetch_data_sources("lab1", handler)
        assert cache["entityA"]["src1"]["data"][0]["name"] == "x"
        assert any(
            "entityA/src1" in rec.message and "fetched 1 item(s)" in rec.message
            for rec in caplog.records
        )
        assert not any("list of items" in rec.message for rec in caplog.records)
        assert not any('"extId"' in rec.message for rec in caplog.records)

    def test_no_results(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"filter": "name eq 'missing'"}}
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert cache["entityA"]["src1"]["data"] == []
        assert cache["entityA"]["src1"]["metadata"]["totalAvailableResults"] == 0
        assert failures == []

    def test_exception_returns_empty_and_tracks_failure(
        self, minimal_global_config, new_config
    ):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.side_effect = Exception("api boom")
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"filter": "name eq 'x'"}}
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert cache["entityA"]["src1"] == {}
        assert failures == ["entityA/src1"]

    def test_multiple_failures_tracked(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.side_effect = Exception("timeout")
        provider.domain_data_config["lab1"] = {
            "cluster": {
                "c1": {"filter": "name eq 'a'"},
                "c2": {"filter": "name eq 'b'"},
            },
            "category": {
                "cat1": {"filter": "name eq 'x'"},
            },
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert len(failures) == 3
        assert "cluster/c1" in failures
        assert "cluster/c2" in failures
        assert "category/cat1" in failures

    def test_passthrough_arbitrary_kwargs_forwarded(
        self, minimal_global_config, new_config
    ):
        """Non-alias keys (e.g. parent-id params) must reach list_entities."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {
                "src1": {
                    "hardwareProviderExtId": "hw-1",
                    "connectionExtId": "conn-1",
                    "filter": "name eq 'x'",
                }
            }
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert failures == []
        kwargs = handler.list_entities.call_args.kwargs
        assert kwargs["hardwareProviderExtId"] == "hw-1"
        assert kwargs["connectionExtId"] == "conn-1"
        assert kwargs["_filter"] == "name eq 'x'"

    def test_unknown_data_source_key_is_forwarded(
        self, minimal_global_config, new_config
    ):
        """Keys other than depends_on are passed through, including unknown ones.

        Parent-id params rely on this. A typo is therefore forwarded to the
        SDK (typically a TypeError) rather than stripped.
        """
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {
                "src1": {
                    "filter": "name eq 'x'",
                    "depends_on": ["other_src"],
                    "not_an_sdk_param": "junk",
                },
                "other_src": {"filter": "name eq 'y'"},
            }
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert failures == []
        src1_kwargs = None
        for call in handler.list_entities.call_args_list:
            if call.kwargs.get("not_an_sdk_param"):
                src1_kwargs = call.kwargs
                break
        assert src1_kwargs is not None
        assert src1_kwargs["not_an_sdk_param"] == "junk"
        assert src1_kwargs["_filter"] == "name eq 'x'"
        assert "depends_on" not in src1_kwargs

    def test_no_ctx_leaves_config_unresolved(self, minimal_global_config, new_config):
        """Without a ctx, tokens are forwarded as-is (back-compat)."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"filter": "name eq '{var.unset}'"}}
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert failures == []
        assert handler.list_entities.call_args.kwargs["_filter"] == (
            "name eq '{var.unset}'"
        )

    def test_resolves_cross_domain_resource_ref(
        self, minimal_global_config, new_config
    ):
        """A {domain.resource.field} token in a data source is resolved via ctx."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"filter": "name eq '{other.res.extId}'"}}
        }
        ctx = InterpolationContext(
            domain_states={"other": {"res": {"extId": "abc-123"}}}
        )
        cache, failures = provider._fetch_data_sources(
            "lab1", handler, ctx=ctx, strict=True
        )
        assert failures == []
        assert handler.list_entities.call_args.kwargs["_filter"] == "name eq 'abc-123'"

    def test_resolves_cross_domain_data_ref(self, minimal_global_config, new_config):
        """A {data.domain.entity.source.field} token is resolved via ctx."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {
                "src1": {"parentExtId": "{data.other.entityB.lookup.data.0.extId}"}
            }
        }
        ctx = InterpolationContext(
            data_cache={"other": {"entityB": {"lookup": {"data": [{"extId": "xyz"}]}}}}
        )
        cache, failures = provider._fetch_data_sources(
            "lab1", handler, ctx=ctx, strict=True
        )
        assert failures == []
        assert handler.list_entities.call_args.kwargs["parentExtId"] == "xyz"

    def test_unresolved_token_strict_skips_fetch_and_records_failure(
        self, minimal_global_config, new_config
    ):
        """An unresolvable token must never reach the API as a literal string."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        provider.domain_data_config["lab1"] = {
            "entityA": {"src1": {"filter": "name eq '{var.missing}'"}}
        }
        ctx = InterpolationContext(variables={})
        cache, failures = provider._fetch_data_sources(
            "lab1", handler, ctx=ctx, strict=True
        )
        assert failures == ["entityA/src1"]
        handler.list_entities.assert_not_called()

    def test_unresolved_token_among_multiple_sources_only_skips_that_one(
        self, minimal_global_config, new_config
    ):
        """One unresolvable source shouldn't block sibling sources from fetching."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {
                "bad": {"filter": "name eq '{var.missing}'"},
                "good": {"filter": "name eq 'x'"},
            }
        }
        ctx = InterpolationContext(variables={})
        cache, failures = provider._fetch_data_sources(
            "lab1", handler, ctx=ctx, strict=True
        )
        assert failures == ["entityA/bad"]
        assert "good" in cache["entityA"]
        assert "bad" not in cache["entityA"]

    def test_depends_on_not_forwarded_to_list_entities(
        self, minimal_global_config, new_config
    ):
        """``depends_on`` is an ordering directive, never an API param."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "entityA": {
                "src1": {"filter": "name eq 'x'"},
                "src2": {
                    "filter": "name eq 'y'",
                    "depends_on": ["src1"],
                },
            }
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert failures == []
        for call in handler.list_entities.call_args_list:
            assert "depends_on" not in call.kwargs

    def test_dependent_source_fetched_after_its_dependency(
        self, minimal_global_config, new_config
    ):
        """src2 depends on src1; src2's filter should receive src1's result."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]

        src1_item = MagicMock()
        handler.list_entities.side_effect = lambda et, **kw: (
            [src1_item] if kw.get("_filter") == "name eq 'x'" else []
        )
        handler.sanitize_entity_data.return_value = {"extId": "e-1", "name": "x"}

        provider.domain_data_config["lab1"] = {
            "category": {
                "src1": {"filter": "name eq 'x'"},
                "src2": {
                    "parentExtId": "{data.category.src1.data.0.extId}",
                    "depends_on": ["src1"],
                },
            }
        }
        ds_ctx = provider._build_data_source_context("lab1")
        cache, failures = provider._fetch_data_sources(
            "lab1", handler, ctx=ds_ctx, strict=True
        )
        assert failures == []
        assert cache["category"]["src1"]["data"][0]["extId"] == "e-1"
        # src2's list_entities call must have received the resolved parentExtId
        src2_call = next(
            c
            for c in handler.list_entities.call_args_list
            if c.kwargs.get("parentExtId") is not None
        )
        assert src2_call.kwargs["parentExtId"] == "e-1"

    def test_implicit_token_orders_fetch_without_depends_on(
        self, minimal_global_config, new_config
    ):
        """A ``{data.<entity>.<source>...}`` token alone (no ``depends_on``)
        must still fetch the producer first and resolve the consumer."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]

        src1_item = MagicMock()
        handler.list_entities.side_effect = lambda et, **kw: (
            [src1_item] if kw.get("_filter") == "name eq 'x'" else []
        )
        handler.sanitize_entity_data.return_value = {"extId": "e-1", "name": "x"}

        provider.domain_data_config["lab1"] = {
            "node": {
                "src2": {
                    "parentExtId": "{data.category.src1.data.0.extId}",
                }
            },
            "category": {
                "src1": {"filter": "name eq 'x'"},
            },
        }
        ds_ctx = provider._build_data_source_context("lab1")
        cache, failures = provider._fetch_data_sources(
            "lab1", handler, ctx=ds_ctx, strict=True
        )
        assert failures == []
        src2_call = next(
            c
            for c in handler.list_entities.call_args_list
            if c.kwargs.get("parentExtId") is not None
        )
        assert src2_call.kwargs["parentExtId"] == "e-1"
        assert cache["category"]["src1"]["data"][0]["extId"] == "e-1"

    def test_independent_sources_all_fetched_without_ordering_error(
        self, minimal_global_config, new_config
    ):
        """Sources with no deps between them must all succeed regardless of
        config order (regression guard for the sequential rewrite)."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "category": {
                "a": {"filter": "name eq 'a'"},
                "b": {"filter": "name eq 'b'"},
                "c": {"filter": "name eq 'c'"},
            }
        }
        cache, failures = provider._fetch_data_sources("lab1", handler)
        assert failures == []
        assert set(cache["category"]) == {"a", "b", "c"}

    def test_circular_dependency_raises_instead_of_silent_fallback(
        self, minimal_global_config, new_config
    ):
        """A circular data-source dependency must raise, not silently fall
        back to config order (which previously risked fetching a source
        before the data it references exists)."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        provider.domain_data_config["lab1"] = {
            "category": {
                "src1": {"filter": "x", "depends_on": ["src2"]},
                "src2": {"filter": "y", "depends_on": ["src1"]},
            }
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            provider._fetch_data_sources("lab1", handler)
        handler.list_entities.assert_not_called()

    def test_duplicate_source_name_is_a_hard_error(
        self, minimal_global_config, new_config
    ):
        """A source name reused across entity types must fail loudly before
        anything is fetched.  Source names share one flat namespace, so one
        of the two could never be ordered or referenced -- half-applying the
        domain around it would leave its consumers silently unresolvable."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "category": {"dup": {"filter": "name eq 'first'"}},
            "node": {"dup": {"filter": "name eq 'second'"}},
        }
        with pytest.raises(ValueError, match="Duplicate data source name 'dup'"):
            provider._fetch_data_sources("lab1", handler)
        handler.list_entities.assert_not_called()

    def test_validation_warning_for_unknown_source_ref(
        self, minimal_global_config, new_config, caplog
    ):
        """A token referencing a nonexistent source name should surface an
        early warning via validate_data_tokens, not just a confusing
        unresolved-token failure once the API is called."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "node": {"src1": {"parentExtId": "{data.category.typo_src.data.0.extId}"}}
        }
        with caplog.at_level(logging.WARNING):
            provider._fetch_data_sources("lab1", handler)
        assert any(
            "typo_src" in rec.message and "unknown source" in rec.message
            for rec in caplog.records
        )

    def test_index_access_without_orderby_warns(
        self, minimal_global_config, new_config, caplog
    ):
        """Indexing into a source's results with no orderby configured
        should warn that the result order may be non-deterministic."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "category": {"src1": {"filter": "name eq 'x'"}},
            "node": {
                "src2": {
                    "parentExtId": "{data.category.src1.data.0.extId}",
                    "depends_on": ["src1"],
                }
            },
        }
        with caplog.at_level(logging.WARNING):
            provider._fetch_data_sources("lab1", handler)
        assert any(
            "index-based access" in rec.message and "src1" in rec.message
            for rec in caplog.records
        )

    def test_index_access_with_orderby_no_warning(
        self, minimal_global_config, new_config, caplog
    ):
        """The same index-access pattern must not warn once the referenced
        source has an explicit orderby -- its ordering is deterministic."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "category": {"src1": {"filter": "name eq 'x'", "orderby": "name asc"}},
            "node": {
                "src2": {
                    "parentExtId": "{data.category.src1.data.0.extId}",
                    "depends_on": ["src1"],
                }
            },
        }
        with caplog.at_level(logging.WARNING):
            provider._fetch_data_sources("lab1", handler)
        assert not any("index-based access" in rec.message for rec in caplog.records)

    def test_index_access_with_underscore_orderby_no_warning(
        self, minimal_global_config, new_config, caplog
    ):
        """``_orderby`` is the API alias of ``orderby`` and must also
        suppress the non-determinism warning."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.list_entities.return_value = []
        provider.domain_data_config["lab1"] = {
            "category": {"src1": {"filter": "name eq 'x'", "_orderby": "name asc"}},
            "node": {
                "src2": {
                    "parentExtId": "{data.category.src1.data.0.extId}",
                    "depends_on": ["src1"],
                }
            },
        }
        with caplog.at_level(logging.WARNING):
            provider._fetch_data_sources("lab1", handler)
        assert not any("index-based access" in rec.message for rec in caplog.records)


class TestBuildDataSourceContext:
    """Tests for _build_data_source_context."""

    def test_excludes_current_domain_includes_others(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    },
                    "site_b": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r2": {"body": {"k": 2}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        provider.domain_resource_state["site_a"] = {"r1": {"extId": "a1"}}
        provider.domain_resource_state["site_b"] = {"r2": {"extId": "b1"}}
        provider.domain_data_cache["site_a"] = {
            "entityA": {"src": {"data": [], "metadata": {}}}
        }
        provider.domain_data_cache["site_b"] = {
            "entityA": {"src": {"data": [], "metadata": {}}}
        }

        ctx = provider._build_data_source_context("site_b")

        assert "site_a" in ctx.domain_states
        assert "site_b" not in ctx.domain_states
        # Namespaced shape: cross-domain caches live under "_cross" keyed
        # by domain name; the current domain is excluded from there too.
        assert "site_a" in ctx.data_cache["_cross"]
        assert "site_b" not in ctx.data_cache["_cross"]
        assert ctx.resource_state == {}

    def test_partial_cache_merged_into_flat_layer(self, minimal_global_config):
        """partial_cache entries must appear in ctx.data_cache["_local"] under
        their entity_type key so that within-domain flat {data.e.s.*} tokens
        resolve without any risk of colliding with a domain name."""
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        partial = {"category": {"src1": {"data": [{"extId": "cat-1"}], "metadata": {}}}}
        ctx = provider._build_data_source_context("site_a", partial_cache=partial)
        assert (
            ctx.data_cache["_local"]["category"]["src1"]["data"][0]["extId"] == "cat-1"
        )

    def test_no_partial_cache_omits_flat_layer(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "site_a": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        ctx = provider._build_data_source_context("site_a")
        assert ctx.data_cache["_local"] == {}

    def test_domain_and_entity_name_collision_no_ambiguity(self, minimal_global_config):
        """Regression: an entity type sharing a name with a domain must not
        cause cross-domain data to shadow (or be shadowed by) local data --
        the namespaced cache keeps "_cross" and "_local" fully disjoint."""
        config = load_config(
            {
                "domains": {
                    "cluster": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    },
                    "site_a": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r2": {"body": {"k": 2}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        # Cross-domain cache for a domain literally named "cluster".
        provider.domain_data_cache["cluster"] = {
            "node": {"remote_src": {"data": [{"extId": "remote-1"}]}}
        }
        # Local (within-domain) partial cache for an *entity type* also
        # named "cluster", fetched while building site_a's data sources.
        partial = {"cluster": {"local_src": {"data": [{"extId": "local-1"}]}}}

        ctx = provider._build_data_source_context("site_a", partial_cache=partial)

        # Cross-domain reference resolves against the "cluster" domain.
        assert (
            resolve(
                "{data.cluster.node.remote_src.data.0.extId}",
                ctx,
            )
            == "remote-1"
        )
        # Flat/local reference resolves against the "cluster" entity type,
        # not the "cluster" domain -- no collision despite the shared name.
        assert (
            resolve(
                "{data.cluster.local_src.data.0.extId}",
                ctx,
            )
            == "local-1"
        )


# ---------------------------------------------------------------------------
# _build_data_source_dependency_graph
# ---------------------------------------------------------------------------


class TestBuildDataSourceDependencyGraph:
    """Tests for Provider._build_data_source_dependency_graph."""

    def _make_provider_with_data(self, minimal_global_config, data_block):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "data": data_block,
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    }
                }
            }
        )
        return _make_provider(minimal_global_config, config)

    def test_no_deps_all_zero_in_degree(self, minimal_global_config):
        provider = self._make_provider_with_data(
            minimal_global_config,
            {
                "category": {
                    "src1": {"filter": "name eq 'x'"},
                    "src2": {"filter": "name eq 'y'"},
                }
            },
        )
        graph, in_degree = provider._build_data_source_dependency_graph(
            provider.domain_data_config["lab1"]
        )
        assert in_degree["src1"] == 0
        assert in_degree["src2"] == 0
        assert graph["src1"] == []
        assert graph["src2"] == []

    def test_implicit_token_ref_creates_edge(self, minimal_global_config):
        """src2 (under entity type 'node') references src1's result via a
        flat data token → src1 must come before src2 in the sort."""
        provider = self._make_provider_with_data(
            minimal_global_config,
            {
                "category": {
                    "src1": {"filter": "name eq 'x'"},
                },
                "node": {"src2": {"parentExtId": "{data.category.src1.data.0.extId}"}},
            },
        )
        data_config = provider.domain_data_config["lab1"]
        graph, in_degree = provider._build_data_source_dependency_graph(data_config)
        assert in_degree["src2"] == 1
        assert in_degree["src1"] == 0
        assert "src2" in graph["src1"]
        sorted_names = provider._topological_sort_sources(graph, in_degree)
        assert sorted_names.index("src1") < sorted_names.index("src2")

    def test_local_ref_when_entity_type_matches_domain_name(
        self, minimal_global_config
    ):
        """A domain named ``cluster`` must not hide a local
        ``{data.cluster.src1...}`` dependency edge."""
        config = load_config(
            {
                "domains": {
                    "cluster": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    },
                    "lab1": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "data": {
                            "cluster": {
                                "src1": {"filter": "name eq 'x'"},
                            },
                            "node": {
                                "src2": {
                                    "parentExtId": ("{data.cluster.src1.data.0.extId}")
                                }
                            },
                        },
                        "resources": {"entityA": {"r2": {"body": {"k": 2}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        data_config = provider.domain_data_config["lab1"]
        graph, in_degree = provider._build_data_source_dependency_graph(data_config)
        assert in_degree["src2"] == 1
        assert "src2" in graph["src1"]

    def test_explicit_depends_on_creates_edge(self, minimal_global_config):
        provider = self._make_provider_with_data(
            minimal_global_config,
            {
                "category": {
                    "src1": {"filter": "name eq 'x'"},
                    "src2": {
                        "filter": "name eq 'y'",
                        "depends_on": ["src1"],
                    },
                }
            },
        )
        data_config = provider.domain_data_config["lab1"]
        graph, in_degree = provider._build_data_source_dependency_graph(data_config)
        assert in_degree["src2"] == 1
        assert "src2" in graph["src1"]
        sorted_names = provider._topological_sort_sources(graph, in_degree)
        assert sorted_names.index("src1") < sorted_names.index("src2")

    def test_unknown_depends_on_logs_warning_no_edge(
        self, minimal_global_config, caplog
    ):
        provider = self._make_provider_with_data(
            minimal_global_config,
            {
                "category": {
                    "src1": {
                        "filter": "name eq 'x'",
                        "depends_on": ["nonexistent"],
                    }
                }
            },
        )
        with caplog.at_level(logging.WARNING):
            graph, in_degree = provider._build_data_source_dependency_graph(
                provider.domain_data_config["lab1"]
            )
        assert in_degree["src1"] == 0
        assert any(
            "nonexistent" in rec.message and "does not match" in rec.message
            for rec in caplog.records
        )

    def test_circular_dependency_raises(self, minimal_global_config):
        provider = self._make_provider_with_data(
            minimal_global_config,
            {
                "category": {
                    "src1": {"filter": "x", "depends_on": ["src2"]},
                    "src2": {"filter": "y", "depends_on": ["src1"]},
                }
            },
        )
        data_config = provider.domain_data_config["lab1"]
        graph, in_degree = provider._build_data_source_dependency_graph(data_config)
        with pytest.raises(ValueError, match="Circular dependency"):
            provider._topological_sort_sources(graph, in_degree)

    def test_duplicate_source_name_across_entity_types_rejected(
        self, minimal_global_config
    ):
        """A source name reused across entity types is rejected while the
        graph is built, and the error names both entity types so the user
        knows which two declarations to reconcile."""
        provider = self._make_provider_with_data(
            minimal_global_config,
            {
                "category": {"dup": {"filter": "name eq 'x'"}},
                "node": {"dup": {"filter": "name eq 'y'"}},
                "cluster": {"other": {"filter": "name eq 'z'"}},
            },
        )
        data_config = provider.domain_data_config["lab1"]
        with pytest.raises(ValueError) as excinfo:
            provider._build_data_source_dependency_graph(data_config)
        message = str(excinfo.value)
        assert "Duplicate data source name 'dup'" in message
        assert "'category'" in message
        assert "'node'" in message

    def test_unique_source_names_counted_from_in_degree(self, minimal_global_config):
        """The sort counts nodes from in_degree (one entry per source name)
        rather than re-deriving a count from the raw {entity_type: {source:
        cfg}} config, so a domain spreading sources across entity types
        sorts cleanly instead of raising a false "circular dependency"."""
        provider = self._make_provider_with_data(
            minimal_global_config,
            {
                "category": {"src_a": {"filter": "name eq 'x'"}},
                "node": {"src_b": {"filter": "name eq 'y'"}},
                "cluster": {"src_c": {"filter": "name eq 'z'"}},
            },
        )
        data_config = provider.domain_data_config["lab1"]
        graph, in_degree = provider._build_data_source_dependency_graph(data_config)
        sorted_names = provider._topological_sort_sources(graph, in_degree)
        assert set(sorted_names) == {"src_a", "src_b", "src_c"}

    def test_cross_domain_token_not_treated_as_local_dep(self, minimal_global_config):
        """A {data.other_domain.entity.source.*} token must NOT create an
        edge in the local dependency graph — it is a cross-domain ref."""
        config = load_config(
            {
                "domains": {
                    "other_domain": {
                        "host": "2.2.2.2",
                        "username": "u",
                        "password": "p",
                        "resources": {"entityA": {"r1": {"body": {"k": 1}}}},
                    },
                    "lab1": {
                        "host": "1.1.1.1",
                        "username": "u",
                        "password": "p",
                        "data": {
                            "category": {
                                "src1": {
                                    "parentExtId": (
                                        "{data.other_domain.category.src_x.data.0.extId}"
                                    )
                                }
                            }
                        },
                        "resources": {"entityA": {"r2": {"body": {"k": 2}}}},
                    },
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        data_config = provider.domain_data_config["lab1"]
        graph, in_degree = provider._build_data_source_dependency_graph(data_config)
        assert in_degree["src1"] == 0


# ---------------------------------------------------------------------------
# _resolve_and_compare error paths
# ---------------------------------------------------------------------------


class TestResolveAndCompare:
    def test_interpolation_error(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        ctx = InterpolationContext(variables={})
        resource_cfg = {"body": {"x": "{var.missing}"}}
        result = provider._resolve_and_compare(resource_cfg, None, ctx)
        _, _, _, _, _, exc_msg = result
        assert exc_msg is not None

    def test_compare_ignores_extra_previous_fields(
        self, minimal_global_config, new_config
    ):
        provider = _make_provider(minimal_global_config, new_config)
        ctx = InterpolationContext(variables={})
        prev = {"extId": "e1", "body": {"a": 1, "extra": "x"}}
        resource_cfg = {"body": {"a": 1}}
        _, _, _, _, update_needed, exc_msg = provider._resolve_and_compare(
            resource_cfg, prev, ctx
        )
        assert exc_msg is None
        assert update_needed is False

    def test_compare_prunes_list_items(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        ctx = InterpolationContext(variables={})
        prev = {"extId": "e1", "body": {"items": [{"a": 1, "extra": 2}]}}
        resource_cfg = {"body": {"items": [{"a": 1}]}}
        _, _, _, _, update_needed, exc_msg = provider._resolve_and_compare(
            resource_cfg, prev, ctx
        )
        assert exc_msg is None
        assert update_needed is False

    def test_comparison_exception(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        ctx = InterpolationContext(variables={})
        prev = {"extId": "e1", "body": {"a": 1}}
        resource_cfg = {"body": {"a": 1}}
        with patch(
            "ztf.provider.provider._apply_ignore_changes",
            side_effect=Exception("cmp fail"),
        ):
            result = provider._resolve_and_compare(resource_cfg, prev, ctx)
        _, _, _, _, update_needed, exc_msg = result
        assert exc_msg is not None

    def test_upsert_resolve_error_with_prev_item(
        self, minimal_global_config, new_config
    ):
        """When _resolve_and_compare returns exc_msg and prev_item exists,
        the previous state is preserved and error logged as 'update' (L521-528)."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables={})
        resource_state: dict = {}
        prev = {"res1": {"extId": "abc123", "body": {"name": "old"}}}
        inp = {"res1": {"body": {"name": "{var.missing}"}}}

        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            inp,
            prev,
            ctx,
            resource_state,
        )
        assert results["res1"]["extId"] == "abc123"
        assert results["res1"]["body"] == {"name": "old"}
        handler.create.assert_not_called()
        handler.update.assert_not_called()

    def test_upsert_resolve_error_no_prev_item(self, minimal_global_config, new_config):
        """When _resolve_and_compare returns exc_msg and no prev_item,
        resource is skipped and error logged as 'create' (L529-535)."""
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = ENTITY_A_META

        ctx = InterpolationContext(variables={})
        resource_state: dict = {}
        inp = {"res1": {"body": {"name": "{var.missing}"}}}

        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            inp,
            {},
            ctx,
            resource_state,
        )
        assert "res1" not in results
        handler.create.assert_not_called()


# ---------------------------------------------------------------------------
# _run_operation
# ---------------------------------------------------------------------------


class TestRunOperation:
    def test_success(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.run_operation.return_value = "ok"
        ctx = InterpolationContext(variables={})
        provider._run_operation(
            "entityA", handler, {"type": "do_something"}, "lab1", ctx
        )
        handler.run_operation.assert_called_once()

    def test_exception_logged(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.run_operation.side_effect = Exception("op fail")
        ctx = InterpolationContext(variables={})
        provider._run_operation(
            "entityA", handler, {"type": "do_something"}, "lab1", ctx
        )


# ---------------------------------------------------------------------------
# _build_handler_data & _build_state_entry
# ---------------------------------------------------------------------------


class TestBuildHelpers:
    def test_build_handler_data_with_params(self):
        resource = {"body": {"a": 1}, "params": {"clusterExtId": "c1"}}
        data = Provider._build_handler_data(resource, "res1")
        assert data["body"] == {"a": 1}
        assert data["clusterExtId"] == "c1"
        assert data["resource_name"] == "res1"

    def test_build_handler_data_no_params(self):
        resource = {"body": {"a": 1}}
        data = Provider._build_handler_data(resource, "res1")
        assert data["body"] == {"a": 1}
        assert "clusterExtId" not in data

    def test_build_state_entry_with_params(self):
        resource = {"body": {"a": 1}, "params": {"p": "v"}}
        entry = Provider._build_state_entry(resource, "e1")
        assert entry["extId"] == "e1"
        assert entry["params"] == {"p": "v"}

    def test_build_state_entry_no_params(self):
        resource = {"body": {"a": 1}}
        entry = Provider._build_state_entry(resource, "e1")
        assert entry["extId"] == "e1"
        assert "params" not in entry

    def test_build_state_entry_persists_rules(self):
        resource = {"body": {"a": 1}, "rules": {"prevent_destroy": True}}
        entry = Provider._build_state_entry(resource, "e1")
        assert entry["rules"] == {"prevent_destroy": True}

    def test_build_state_entry_no_rules(self):
        resource = {"body": {"a": 1}}
        entry = Provider._build_state_entry(resource, "e1")
        assert "rules" not in entry


# ---------------------------------------------------------------------------
# _run_domain_for_upsert / _run_domain_for_delete exceptions
# ---------------------------------------------------------------------------


class TestDomainExceptions:
    def test_upsert_domain_exception_preserves_state(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        with patch.object(
            provider, "_fetch_data_sources", side_effect=RuntimeError("boom")
        ):
            results, dn = provider._run_domain_for_upsert("lab1")
        assert dn == "lab1"
        assert "entityA" in results

    def test_delete_domain_exception_preserves_entities(
        self, minimal_global_config, new_config, new_state
    ):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        with patch.object(
            provider,
            "_prepare_delete_entity_results",
            side_effect=RuntimeError("boom"),
        ):
            entities = {"entityA": {"res1": {"extId": "e1", "body": {}}}}
            results, dn = provider._run_domain_for_delete("lab1", entities)
        assert dn == "lab1"
        assert "entityA" in results

    def test_delete_rebuilds_graph_from_input_config(
        self, minimal_global_config, entity_map_patch
    ):
        """When domain_resource_order is empty, delete should rebuild the
        dependency graph from the input config and respect reverse topological
        order (overlay deleted before vpc, vpc before ext_subnet)."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "subnet": {
                                "ext_sub": {"body": {"name": "ext"}},
                                "overlay": {"body": {"vpcRef": "{my_vpc.ext_id}"}},
                            },
                            "vpc": {
                                "my_vpc": {
                                    "body": {"subnetRef": "{ext_sub.ext_id}"},
                                },
                            },
                        },
                    }
                }
            },
        )
        prev_state = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "resources": {
                        "subnet": {
                            "ext_sub": {"extId": "s1", "body": {"name": "ext"}},
                            "overlay": {"extId": "s2", "body": {"vpcRef": "v1"}},
                        },
                        "vpc": {
                            "my_vpc": {"extId": "v1", "body": {"subnetRef": "s1"}},
                        },
                    },
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, prev_state)
        assert not provider.domain_resource_order

        delete_order: list[str] = []

        def _capture_delete(entity, domain_name, handler, resources, rules_map=None):
            delete_order.extend(resources.keys())
            return {}

        with patch.object(
            provider,
            "_prepare_delete_entity_results",
            side_effect=_capture_delete,
        ):
            entities = prev_state["domains"]["lab1"]["resources"]
            provider._run_domain_for_delete("lab1", entities)

        assert delete_order.index("overlay") < delete_order.index("my_vpc")
        assert delete_order.index("my_vpc") < delete_order.index("ext_sub")


# ---------------------------------------------------------------------------
# run() delete phase edge cases
# ---------------------------------------------------------------------------


class TestRunDeletePhase:
    def test_delete_domain_not_in_handler_map(self, minimal_global_config, new_state):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"res2": {"body": {"x": 1}}}},
                    }
                }
            }
        )
        with patch.object(
            Provider,
            "_run_domain_for_upsert",
            return_value=(
                {"entityA": {"res2": {"extId": "y", "body": {"x": 1}}}},
                "lab1",
            ),
        ):
            provider = _make_provider(minimal_global_config, config, new_state)
            provider.domain_entity_handler_map.pop("lab1", None)
            output = provider.run()
            assert "domains" in output


# ---------------------------------------------------------------------------
# destroy no handler warning
# ---------------------------------------------------------------------------


class TestDestroyNoHandler:
    def test_no_handler_for_domain(self, minimal_global_config, new_config, new_state):
        provider = _make_provider(minimal_global_config, new_config, new_state)
        provider.domain_entity_handler_map = {}
        output = provider.destroy()
        assert "domains" in output


# ---------------------------------------------------------------------------
# import_resource_data
# ---------------------------------------------------------------------------


class TestImportSuccess:
    def test_import_happy_path(self, minimal_global_config, new_config):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {"extId": "e1", "body": {}},
                            }
                        },
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {"name": "imported"}
        result = provider.import_resource_data("res1", "lab1")
        assert result["entity_name"] == "entityA"
        assert result["extId"] == "e1"
        assert result["sanitized_data"] is not None

    def test_import_strips_readonly_fields(self, minimal_global_config):
        """Import should route sanitized data through the entity handler's
        schema-driven readOnly stripping before returning it."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {"extId": "e1", "body": {}},
                            }
                        },
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {
            "name": "tiny-linux",
            "createTime": "2026-08-31T15:14:47+00:00",
            "ownerExtId": "ae1c33bd-f0dd-5000-9e36-49247c0d1b67",
        }
        handler.strip_readonly_fields.side_effect = None
        handler.strip_readonly_fields.return_value = {"name": "tiny-linux"}

        result = provider.import_resource_data("res1", "lab1")

        handler.strip_readonly_fields.assert_called_once_with(
            "entityA",
            {
                "name": "tiny-linux",
                "createTime": "2026-08-31T15:14:47+00:00",
                "ownerExtId": "ae1c33bd-f0dd-5000-9e36-49247c0d1b67",
            },
        )
        assert result["sanitized_data"] == {"name": "tiny-linux"}

    def test_import_resolves_data_interpolation(self, minimal_global_config):
        """Import should resolve data-source tokens in extId before
        fetching the resource from the cluster."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "data": {
                            "entityA": {
                                "lookup": {
                                    "filter": "name eq 'foo'",
                                    "select": "extId",
                                }
                            }
                        },
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "extId": "{data.entityA.lookup.data.0.extId}",
                                    "body": {},
                                },
                            }
                        },
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        handler = provider.domain_entity_handler_map["lab1"]

        fake_cache = {
            "entityA": {
                "lookup": {
                    "data": [{"extId": "resolved-ext-id", "name": "foo"}],
                    "metadata": {"totalAvailableResults": 1},
                }
            }
        }
        with patch.object(
            provider, "_fetch_data_sources", return_value=(fake_cache, [])
        ):
            handler.get_entity_by_ext_id.return_value = MagicMock()
            handler.sanitize_entity_data.return_value = {"name": "imported"}
            result = provider.import_resource_data("res1", "lab1")

        assert result["extId"] == "resolved-ext-id"
        handler.get_entity_by_ext_id.assert_called_once_with(
            "entityA", "resolved-ext-id"
        )

    def test_import_resolves_variable_tokens(self, minimal_global_config):
        """Import should resolve variable tokens in extId."""
        config = load_config(
            {
                "variables": {"my_id": "abc-123"},
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "extId": "{var.my_id}",
                                    "body": {},
                                },
                            }
                        },
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {"name": "imported"}

        result = provider.import_resource_data("res1", "lab1")
        assert result["extId"] == "abc-123"

    def test_import_unresolved_tokens(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {"extId": "{var.id}", "body": {}},
                            }
                        },
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        with pytest.raises(ValueError, match="unresolved"):
            provider.import_resource_data("res1", "lab1")

    def test_import_no_ext_id(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {"body": {"name": "x"}},
                            }
                        },
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        with pytest.raises(ValueError, match="No ext_id"):
            provider.import_resource_data("res1", "lab1")

    def test_import_no_handler(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {"extId": "e1", "body": {}},
                            }
                        },
                    }
                }
            }
        )
        provider = _make_provider(minimal_global_config, config)
        provider.domain_entity_handler_map = {}
        with pytest.raises(ValueError, match="No entity handler"):
            provider.import_resource_data("res1", "lab1")


# ---------------------------------------------------------------------------
# resolve_outputs error path
# ---------------------------------------------------------------------------


class TestResolveOutputsError:
    def test_bad_token_non_strict(self, minimal_global_config):
        """Non-strict mode passes through unresolved tokens."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {"res1": {"body": {"name": "test"}}},
                        },
                    }
                },
                "outputs": {
                    "broken": {
                        "value": "{resource.nonexistent.field}",
                        "description": "broken",
                    },
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        outputs = provider.resolve_outputs()
        assert "broken" in outputs

    def test_resolve_raises_value_error(self, minimal_global_config):
        """Force a ValueError in resolve to exercise the error branch."""
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {"res1": {"body": {"name": "test"}}},
                        },
                    }
                },
                "outputs": {
                    "broken": {
                        "value": "{var.missing}",
                        "description": "broken",
                    },
                },
            }
        )
        provider = _make_provider(minimal_global_config, config)
        with patch(
            "ztf.provider.provider.resolve",
            side_effect=ValueError("token error"),
        ):
            outputs = provider.resolve_outputs()
        assert outputs["broken"]["value"] is None
        assert "error" in outputs["broken"]


# ---------------------------------------------------------------------------
# _write_run_results
# ---------------------------------------------------------------------------


class TestWriteRunResults:
    def test_write_creates_file(
        self, tmp_path, monkeypatch, minimal_global_config, new_config
    ):
        monkeypatch.chdir(tmp_path)
        provider = _make_provider(minimal_global_config, new_config)
        provider._write_run_results({"lab1": [{"op": "create"}]})
        import json

        with open(tmp_path / "ztf_run_results.json") as f:
            data = json.load(f)
        assert data["results"]["lab1"] == [{"op": "create"}]
        assert data["metadata"]["interrupted"] is False
        assert "completed_at" in data["metadata"]

    def test_overwrite_replaces_old_data(
        self, tmp_path, monkeypatch, minimal_global_config, new_config
    ):
        import json

        results_file = tmp_path / "ztf_run_results.json"
        results_file.write_text(json.dumps({"lab1": [{"op": "old"}]}))
        monkeypatch.chdir(tmp_path)
        provider = _make_provider(minimal_global_config, new_config)
        provider._write_run_results({"lab1": [{"op": "new"}]})
        with open(results_file) as f:
            data = json.load(f)
        assert data["results"]["lab1"] == [{"op": "new"}]

    def test_empty_no_write(
        self, tmp_path, monkeypatch, minimal_global_config, new_config
    ):
        monkeypatch.chdir(tmp_path)
        provider = _make_provider(minimal_global_config, new_config)
        provider._write_run_results({})
        assert not (tmp_path / "ztf_run_results.json").exists()

    def test_writes_to_configured_path(
        self, tmp_path, minimal_global_config, new_config
    ):
        import json

        provider = _make_provider(minimal_global_config, new_config)
        nested = tmp_path / "sub" / "audit.json"
        provider.run_results_path = nested
        provider._write_run_results({"lab1": [{"op": "create"}]})
        assert nested.is_file()
        data = json.loads(nested.read_text())
        assert data["results"]["lab1"] == [{"op": "create"}]

    def test_records_interrupted_flag_from_shutdown_event(
        self, tmp_path, monkeypatch, minimal_global_config, new_config
    ):
        import json

        monkeypatch.chdir(tmp_path)
        provider = _make_provider(minimal_global_config, new_config)
        provider._shutdown_requested.set()
        provider._write_run_results({"lab1": [{"op": "create"}]})
        data = json.loads((tmp_path / "ztf_run_results.json").read_text())
        assert data["metadata"]["interrupted"] is True

    def test_explicit_interrupted_argument_wins(
        self, tmp_path, monkeypatch, minimal_global_config, new_config
    ):
        import json

        monkeypatch.chdir(tmp_path)
        provider = _make_provider(minimal_global_config, new_config)
        provider._shutdown_requested.set()
        provider._write_run_results({"lab1": [{"op": "create"}]}, interrupted=False)
        data = json.loads((tmp_path / "ztf_run_results.json").read_text())
        assert data["metadata"]["interrupted"] is False


class TestAccumulateRunResults:
    def test_accumulates_across_entities(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        provider._accumulate_run_results({"lab1": [{"op": "create"}]})
        provider._accumulate_run_results({"lab1": [{"op": "update"}]})
        assert len(provider.run_results["lab1"]) == 2

    def test_accumulates_multiple_domains(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        provider._accumulate_run_results({"lab1": [{"op": "create"}]})
        provider._accumulate_run_results({"lab2": [{"op": "delete"}]})
        assert "lab1" in provider.run_results
        assert "lab2" in provider.run_results

    def test_empty_results_noop(self, minimal_global_config, new_config):
        provider = _make_provider(minimal_global_config, new_config)
        provider._accumulate_run_results({})
        assert provider.run_results == {}


# ---------------------------------------------------------------------------
# _initialize_domain_entity_handlers validation
# ---------------------------------------------------------------------------


class TestInitValidation:
    def test_missing_body_and_ext_id(self, minimal_global_config):
        config = {
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "pass",
                    "resources": {"entityA": {"res1": {}}},
                }
            }
        }
        with pytest.raises(ValueError, match="body.*ext_id"):
            _make_provider(minimal_global_config, config)

    def test_state_only_domain_no_creds(self, minimal_global_config):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"res1": {"body": {"a": 1}}}},
                    }
                }
            }
        )
        state = {
            "domains": {
                "orphan": {
                    "host": "9.9.9.9",
                    "resources": {"entityA": {"old_res": {"extId": "e1", "body": {}}}},
                }
            }
        }
        provider = _make_provider(minimal_global_config, config, state)
        assert "orphan" not in provider.domain_entity_handler_map


# ---------------------------------------------------------------------------
# Create-before-destroy edge cases
# ---------------------------------------------------------------------------


class TestCreateBeforeDestroyEdge:
    def test_create_fails(self, minimal_global_config, new_state):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "body": {"foo": "bar"},
                                    "rules": {"create_before_destroy": True},
                                }
                            }
                        },
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = {
            "entityA": {
                "update_supported": False,
            }
        }
        handler.create.side_effect = Exception("create fail")
        ctx = InterpolationContext(variables={})
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {
                "res1": {
                    "body": {"foo": "bar"},
                    "rules": {"create_before_destroy": True},
                }
            },
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
            ctx,
            resource_state,
        )
        assert results["res1"]["extId"] == "abc123"

    def test_delete_old_fails(self, minimal_global_config, new_state):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "body": {"foo": "bar"},
                                    "rules": {"create_before_destroy": True},
                                }
                            }
                        },
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = {
            "entityA": {
                "update_supported": False,
            }
        }
        handler.create.return_value = "new-ext-id"
        handler.delete.side_effect = Exception("delete fail")
        ctx = InterpolationContext(variables={})
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {
                "res1": {
                    "body": {"foo": "bar"},
                    "rules": {"create_before_destroy": True},
                }
            },
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
            ctx,
            resource_state,
        )
        assert results["res1"]["extId"] == "new-ext-id"

    def test_create_before_destroy_no_ext_id(self, minimal_global_config, new_state):
        config = load_config(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {
                                    "body": {"foo": "bar"},
                                    "rules": {"create_before_destroy": True},
                                }
                            }
                        },
                    }
                },
            }
        )
        provider = _make_provider(minimal_global_config, config, new_state)
        handler = provider.domain_entity_handler_map["lab1"]
        handler.entity_metadata_map = {"entityA": {"update_supported": "False"}}
        handler.create.return_value = None
        ctx = InterpolationContext(variables={})
        resource_state: dict = {}
        results = provider._prepare_entity_upsert_results(
            "entityA",
            "lab1",
            handler,
            {
                "res1": {
                    "body": {"foo": "bar"},
                    "rules": {"create_before_destroy": True},
                }
            },
            {"res1": {"extId": "abc123", "body": {"foo": "baz"}}},
            ctx,
            resource_state,
        )
        assert results["res1"]["extId"] == "abc123"
