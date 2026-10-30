"""Tests for ztf.config.config_loader."""

from pathlib import Path

import pytest

from ztf.config.config_loader import (
    DEFAULT_RULES,
    load_config,
    parse_var_string,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_new_config() -> dict:
    """A minimal valid new-format config."""
    return {
        "variables": {"env": "prod"},
        "defaults": {"rules": {"prevent_destroy": True}},
        "domains": {
            "lab1": {
                "host": "10.0.0.1",
                "username": "admin",
                "password": "secret",
                "resources": {
                    "cluster": {
                        "my-cluster": {
                            "body": {"name": "{var.env}-cluster"},
                        }
                    }
                },
            }
        },
        "outputs": {
            "cluster_id": {
                "value": "{lab1.my-cluster.ext_id}",
                "description": "Cluster ID",
            }
        },
    }


@pytest.fixture
def for_each_config() -> dict:
    """Config with for_each."""
    return {
        "variables": {"env": "prod"},
        "domains": {
            "lab1": {
                "host": "10.0.0.1",
                "username": "admin",
                "password": "secret",
                "resources": {
                    "storage_container": {
                        "{each.key}-sc": {
                            "for_each": {
                                "analytics": {
                                    "name": "analytics-container",
                                    "replication": 3,
                                },
                                "backup": {
                                    "name": "backup-container",
                                    "replication": 2,
                                },
                            },
                            "body": {
                                "name": "{each.value.name}",
                                "replicationFactor": "{each.value.replication}",
                            },
                        }
                    }
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_basic_config(self, minimal_new_config: dict) -> None:
        result = load_config(minimal_new_config)
        assert "domains" in result
        assert "variables" in result
        assert result["variables"]["env"] == "prod"

    def test_variable_resolution(self, minimal_new_config: dict) -> None:
        result = load_config(minimal_new_config)
        resource = result["domains"]["lab1"]["resources"]["cluster"]["my-cluster"]
        assert resource["body"]["name"] == "prod-cluster"

    def test_var_overrides(self, minimal_new_config: dict) -> None:
        result = load_config(minimal_new_config, var_overrides={"env": "staging"})
        resource = result["domains"]["lab1"]["resources"]["cluster"]["my-cluster"]
        assert resource["body"]["name"] == "staging-cluster"

    def test_rules_merged_with_defaults(self, minimal_new_config: dict) -> None:
        result = load_config(minimal_new_config)
        resource = result["domains"]["lab1"]["resources"]["cluster"]["my-cluster"]
        rules = resource["rules"]
        # prevent_destroy from defaults section (overrides DEFAULT_RULES)
        assert rules["prevent_destroy"] is True
        # ignore_changes from DEFAULT_RULES
        assert rules["ignore_changes"] == []
        assert rules["create_before_destroy"] is False

    def test_default_rules_ignore_changes_not_aliased(self) -> None:
        """Mutating one resource's ``ignore_changes`` must not leak.

        Historically the merge pattern ``{**DEFAULT_RULES, **overrides}``
        shallow-copied the wrapper dict but kept every resource pointing
        at the same underlying ``ignore_changes`` list.  A caller that
        later appended to it would corrupt sibling resources and even
        the module-level ``DEFAULT_RULES`` constant.
        """
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "cluster": {
                            "a": {"body": {"name": "a"}},
                            "b": {"body": {"name": "b"}},
                        }
                    },
                }
            }
        }
        result = load_config(config)
        clusters = result["domains"]["lab1"]["resources"]["cluster"]
        a_list = clusters["a"]["rules"]["ignore_changes"]
        b_list = clusters["b"]["rules"]["ignore_changes"]
        default_list = result["defaults"]["rules"]["ignore_changes"]

        # Every consumer must own its own list object.
        assert a_list is not b_list
        assert a_list is not default_list
        assert a_list is not DEFAULT_RULES["ignore_changes"]
        assert default_list is not DEFAULT_RULES["ignore_changes"]

        a_list.append("spec/version")
        assert b_list == []
        assert default_list == []
        assert DEFAULT_RULES["ignore_changes"] == []

    def test_default_rules_ignore_changes_not_aliased_with_for_each(self) -> None:
        """Same isolation must hold across for_each-expanded siblings."""
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "cluster": {
                            "{each.key}-c": {
                                "for_each": {"a": 1, "b": 2},
                                "body": {"name": "{each.key}"},
                            }
                        }
                    },
                }
            }
        }
        result = load_config(config)
        clusters = result["domains"]["lab1"]["resources"]["cluster"]
        a_list = clusters["a-c"]["rules"]["ignore_changes"]
        b_list = clusters["b-c"]["rules"]["ignore_changes"]
        assert a_list is not b_list
        a_list.append("status")
        assert b_list == []
        assert DEFAULT_RULES["ignore_changes"] == []

    def test_per_resource_rules_override(self) -> None:
        config = {
            "defaults": {"rules": {"prevent_destroy": True}},
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "cluster": {
                            "my-cluster": {
                                "rules": {"prevent_destroy": False},
                                "body": {"name": "test"},
                            }
                        }
                    },
                }
            },
        }
        result = load_config(config)
        resource = result["domains"]["lab1"]["resources"]["cluster"]["my-cluster"]
        # Per-resource rule overrides the global default
        assert resource["rules"]["prevent_destroy"] is False

    def test_missing_domains_raises(self) -> None:
        with pytest.raises(ValueError, match="domains"):
            load_config({"variables": {}})

    def test_missing_credentials_raises(self) -> None:
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "resources": {"cluster": {"c": {"body": {"name": "x"}}}},
                }
            }
        }
        with pytest.raises(ValueError, match="username"):
            load_config(config)

    def test_outputs_preserved(self, minimal_new_config: dict) -> None:
        result = load_config(minimal_new_config)
        assert "cluster_id" in result["outputs"]
        # Outputs are NOT resolved at load time
        assert result["outputs"]["cluster_id"]["value"] == "{lab1.my-cluster.ext_id}"

    def test_var_file_non_dict_raises(
        self, minimal_new_config: dict, tmp_path: Path
    ) -> None:
        var_file = tmp_path / "vars.yml"
        var_file.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="YAML mapping"):
            load_config(minimal_new_config, var_files=[str(var_file)])


# ---------------------------------------------------------------------------
# for_each expansion
# ---------------------------------------------------------------------------


class TestForEachExpansion:
    def test_expansion(self, for_each_config: dict) -> None:
        result = load_config(for_each_config)
        sc_resources = result["domains"]["lab1"]["resources"]["storage_container"]
        assert "analytics-sc" in sc_resources
        assert "backup-sc" in sc_resources
        # Template key should not be present
        assert "{each.key}-sc" not in sc_resources

    def test_expanded_body(self, for_each_config: dict) -> None:
        result = load_config(for_each_config)
        sc = result["domains"]["lab1"]["resources"]["storage_container"]
        assert sc["analytics-sc"]["body"]["name"] == "analytics-container"
        assert sc["analytics-sc"]["body"]["replicationFactor"] == 3
        assert sc["backup-sc"]["body"]["name"] == "backup-container"
        assert sc["backup-sc"]["body"]["replicationFactor"] == 2

    def test_expanded_resources_have_rules(self, for_each_config: dict) -> None:
        result = load_config(for_each_config)
        sc = result["domains"]["lab1"]["resources"]["storage_container"]
        assert "rules" in sc["analytics-sc"]
        assert sc["analytics-sc"]["rules"]["prevent_destroy"] is False  # DEFAULT

    def test_duplicate_expansion_names_raise(self) -> None:
        """Phase A regression: a ``for_each`` template that produces the
        same resource name for multiple iterations used to silently
        overwrite earlier iterations, losing resources without warning.
        """
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "subnet": {
                            # Constant name (no {each.key}) -> every
                            # iteration collapses into one.
                            "shared-subnet": {
                                "for_each": {
                                    "a": {"cidr": "10.0.0.0/24"},
                                    "b": {"cidr": "10.0.1.0/24"},
                                },
                                "body": {"cidr": "{each.value.cidr}"},
                            }
                        }
                    },
                }
            }
        }
        with pytest.raises(ValueError, match="duplicate resource name 'shared-subnet'"):
            load_config(config)

    def test_duplicate_names_across_iterations_from_collision_in_template(
        self,
    ) -> None:
        """Two iterations whose key template resolves to the same value are
        also detected (e.g. both map to the same ``{each.value.env}``)."""
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "subnet": {
                            "sub-{each.value.env}": {
                                "for_each": {
                                    "net1": {"env": "dev"},
                                    "net2": {"env": "dev"},
                                },
                                "body": {"name": "{each.key}"},
                            }
                        }
                    },
                }
            }
        }
        with pytest.raises(ValueError, match="duplicate resource name 'sub-dev'"):
            load_config(config)

    @pytest.mark.parametrize(
        "bad_for_each,type_name",
        [
            ("not-a-dict", "str"),
            (["a", "b"], "list"),
            (5, "int"),
            (None, "NoneType"),
        ],
        ids=["string", "list", "int", "none"],
    )
    def test_for_each_non_mapping_raises_clear_error(
        self, bad_for_each: object, type_name: str
    ) -> None:
        """A non-mapping ``for_each`` must produce a user-facing ValueError.

        Previously this surfaced as an ``AttributeError: '<type>' object
        has no attribute 'items'`` from inside the expansion loop, which
        exposed implementation detail and made the config error hard to
        locate.
        """
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "vm": {
                            "vm-{each.key}": {
                                "for_each": bad_for_each,
                                "body": {"name": "x"},
                            }
                        }
                    },
                }
            }
        }
        with pytest.raises(
            ValueError,
            match=rf"has 'for_each' of type {type_name}; expected a mapping",
        ):
            load_config(config)


# ---------------------------------------------------------------------------
# count expansion (E1: Terraform parity sugar over for_each)
# ---------------------------------------------------------------------------


class TestCountExpansion:
    """``count: N`` desugars to ``for_each: {"0": 0, ..., str(N-1): N-1}``.

    Acceptance criteria from the Phase E tracking spec:
    - ``count: 3`` produces three resources using ``{each.index}``/
      ``{each.key}``.
    - ``count: 0`` is a valid no-op.
    - Negative ``count`` raises ``ValueError``.
    - ``count`` and ``for_each`` together raise ``ValueError``.
    """

    @staticmethod
    def _config(count_value: object, name_template: str = "vm-{each.index}"):
        return {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "vm": {
                            name_template: {
                                "count": count_value,
                                "body": {"name": "{each.key}"},
                            }
                        }
                    },
                }
            }
        }

    def test_count_expands_to_indexed_resources(self) -> None:
        result = load_config(self._config(3))
        vms = result["domains"]["lab1"]["resources"]["vm"]
        assert sorted(vms) == ["vm-0", "vm-1", "vm-2"]
        assert vms["vm-0"]["body"]["name"] == "0"
        assert vms["vm-2"]["body"]["name"] == "2"

    def test_count_zero_is_no_op(self) -> None:
        result = load_config(self._config(0))
        assert result["domains"]["lab1"]["resources"]["vm"] == {}

    def test_count_one_produces_single_resource(self) -> None:
        result = load_config(self._config(1))
        vms = result["domains"]["lab1"]["resources"]["vm"]
        assert list(vms) == ["vm-0"]

    def test_count_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative integer"):
            load_config(self._config(-1))

    def test_count_non_integer_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative integer"):
            load_config(self._config("3"))

    def test_count_boolean_raises(self) -> None:
        # ``True``/``False`` are ``int`` in Python; reject them as a
        # likely config mistake (would otherwise expand to 1 / 0).
        with pytest.raises(ValueError, match="non-negative integer"):
            load_config(self._config(True))

    def test_count_and_for_each_mutually_exclusive(self) -> None:
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "vm": {
                            "vm-{each.key}": {
                                "count": 2,
                                "for_each": {"a": 1, "b": 2},
                                "body": {"name": "x"},
                            }
                        }
                    },
                }
            }
        }
        with pytest.raises(ValueError, match="mutually exclusive"):
            load_config(config)

    def test_each_index_token_in_count_resolves_to_int(self) -> None:
        result = load_config(self._config(2, name_template="vm-{each.index}"))
        vms = result["domains"]["lab1"]["resources"]["vm"]
        assert sorted(vms) == ["vm-0", "vm-1"]

    def test_each_index_available_in_for_each_too(self) -> None:
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "vm": {
                            "host-{each.index}-{each.key}": {
                                "for_each": {"alpha": 10, "beta": 20},
                                "body": {"port": "{each.value}"},
                            }
                        }
                    },
                }
            }
        }
        result = load_config(config)
        vms = result["domains"]["lab1"]["resources"]["vm"]
        assert sorted(vms) == ["host-0-alpha", "host-1-beta"]

    def test_count_duplicate_name_error_mentions_each_index(self) -> None:
        # Constant template -> all iterations collapse to one name; the
        # error message should suggest ``{each.index}`` (count idiom)
        # rather than ``{each.key}`` (for_each idiom).
        bad = self._config(2, name_template="constant-name")
        with pytest.raises(ValueError, match=r"\{each\.index\}"):
            load_config(bad)


# ---------------------------------------------------------------------------
# Resource name uniqueness
# ---------------------------------------------------------------------------


class TestResourceNameUniqueness:
    def test_duplicate_name_raises(self) -> None:
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "cluster": {
                            "dupe": {"body": {"name": "a"}},
                        },
                        "subnet": {
                            "dupe": {"body": {"name": "b"}},
                        },
                    },
                }
            }
        }
        with pytest.raises(ValueError, match="Duplicate resource name 'dupe'"):
            load_config(config)

    def test_same_name_different_domains_ok(self) -> None:
        config = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "cluster": {"prod": {"body": {"name": "a"}}},
                    },
                },
                "lab2": {
                    "host": "10.0.0.2",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "cluster": {"prod": {"body": {"name": "b"}}},
                    },
                },
            }
        }
        result = load_config(config)
        assert "prod" in result["domains"]["lab1"]["resources"]["cluster"]
        assert "prod" in result["domains"]["lab2"]["resources"]["cluster"]


# ---------------------------------------------------------------------------
# parse_var_string
# ---------------------------------------------------------------------------


class TestParseVarString:
    def test_basic(self) -> None:
        assert parse_var_string("env=prod") == ("env", "prod")

    def test_value_with_equals(self) -> None:
        assert parse_var_string("url=http://host?a=b") == ("url", "http://host?a=b")

    def test_spaces_stripped(self) -> None:
        assert parse_var_string(" key = value ") == ("key", "value")

    def test_no_equals_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid --var format"):
            parse_var_string("noequals")


# ---------------------------------------------------------------------------
# Custom functions in load_config
# ---------------------------------------------------------------------------


class TestLoadConfigWithFunctions:
    def test_for_each_with_fn_tokens(self) -> None:
        def pad(value: object, width: int = 4) -> str:
            return str(int(value)).zfill(int(width))

        raw = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "category": {
                            "cat_{fn.pad(each.value, 4)}": {
                                "for_each": {"c1": 1, "c2": 2},
                                "body": {
                                    "key": "AppType",
                                    "value": "App{fn.pad(each.value, 4)}",
                                },
                            }
                        }
                    },
                }
            }
        }
        result = load_config(raw, functions={"pad": pad})
        resources = result["domains"]["lab1"]["resources"]["category"]
        assert "cat_0001" in resources
        assert "cat_0002" in resources
        assert resources["cat_0001"]["body"]["value"] == "App0001"
        assert resources["cat_0002"]["body"]["value"] == "App0002"

    def test_for_each_nested_token_in_ext_id(self) -> None:
        """for_each expansion resolves inner {fn.*} tokens within
        {data.*} references, producing clean data-source paths."""

        def pad(value: object, width: object) -> str:
            return str(value).zfill(int(str(width)))

        raw: dict = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "data": {
                        "category": {
                            "item_g1": {"filter": "key eq 'Gold-01'", "select": "extId"}
                        }
                    },
                    "resources": {
                        "category": {
                            "item_{fn.pad(each.value, 2)}": {
                                "extId": "{data.category.item_{fn.pad(each.value, 2)}.data.0.extId}",
                                "for_each": {"g1": 1, "g2": 2},
                                "body": {"key": "Item-{fn.pad(each.value, 2)}"},
                            }
                        }
                    },
                }
            }
        }
        result = load_config(raw, functions={"pad": pad})
        resources = result["domains"]["lab1"]["resources"]["category"]
        assert "item_01" in resources
        assert "item_02" in resources
        assert resources["item_01"]["extId"] == "{data.category.item_01.data.0.extId}"
        assert resources["item_02"]["extId"] == "{data.category.item_02.data.0.extId}"
        assert resources["item_01"]["body"]["key"] == "Item-01"

    def test_functions_passed_through_in_config(self) -> None:
        def noop() -> str:
            return ""

        raw = {
            "domains": {
                "lab1": {
                    "host": "10.0.0.1",
                    "username": "admin",
                    "password": "secret",
                    "resources": {
                        "category": {"test": {"body": {"key": "k", "value": "v"}}}
                    },
                }
            }
        }
        result = load_config(raw, functions={"noop": noop})
        assert result["functions"]["noop"] is noop
