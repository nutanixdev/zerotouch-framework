"""Tests for ``ztf.generate_examples``."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

import ztf.generate_examples as mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ENTITY_MAP_SRC = textwrap.dedent("""\
    entity_map = {
        "widget": {
            "parent_entity": "cluster",
            "sdk_name": "ntnx_widget_py_client",
            "namespace": "widgetmgmt",
            "create_method_name": "create_widget",
            "get_method_name": "get_widget_by_id",
            "update_method_name": "update_widget_by_id",
            "delete_method_name": "delete_widget_by_id",
            "list_method_name": "list_widgets",
            "operations": ["do_thing", "do_other", "do_more", "do_extra"],
            "method_params": {
                "create": ["body", "clusterExtId"],
            },
        },
        "gadget": {
            "sdk_name": "ntnx_gadget_py_client",
            "namespace": "gadgetmgmt",
            "create_method_name": "create_gadget",
            "get_method_name": "get_gadget_by_id",
            "update_method_name": "update_gadget_by_id",
            "delete_method_name": "delete_gadget_by_id",
            "list_method_name": "list_gadgets",
            "operations": [],
            "method_params": {"create": ["body"]},
        },
        "custom_helper": {
            "sdk_name": "ztf.helpers.custom_helper",
            "namespace": "custom_ns",
            "use_ztf_helper": True,
            "dependent_entities": [],
            "create_supported": True,
            "update_supported": False,
            "delete_supported": False,
            "create_method_name": "create_thing",
            "list_method_name": "",
            "get_method_name": "",
            "update_method_name": "",
            "delete_method_name": "",
            "method_params": {"create": ["body"]},
            "helper_schema": {
                "name": {"type": "string", "required": True, "description": "Name", "example": "test"},
                "count": {"type": "integer", "required": False, "description": "Count", "example": 5},
            },
        },
    }
""")

_COMPAT_MAP: dict[str, Any] = {
    "widgetmgmt": {
        "createWidget": {
            "versions": [4.0, 4.1],
            "http_method": "post",
            "summary": "Create a Widget",
            "schema": {
                "request": {
                    "name": {
                        "type": "string",
                        "required_in": [4.0, 4.1],
                        "readOnly": False,
                        "versions": [4.0, 4.1],
                    },
                    "status": {
                        "type": "enum",
                        "required_in": [],
                        "enum": {"ACTIVE": {}, "INACTIVE": {}, "$UNKNOWN": {}},
                    },
                    "config": {
                        "type": "object",
                        "required_in": [],
                        "children": {
                            "port": {"type": "integer", "required_in": [4.0]},
                        },
                    },
                    "tags": {
                        "type": "array",
                        "required_in": [],
                        "items": {
                            "properties": {
                                "key": {"type": "string", "required_in": [4.0]},
                            }
                        },
                    },
                    "emptyArr": {
                        "type": "array",
                        "required_in": [],
                        "items": {},
                    },
                    "target": {
                        "type": "oneOf",
                        "required_in": [4.0, 4.1],
                        "variants": {
                            "IpTarget": {
                                "object_type": "widgetmgmt.v4.IpTarget",
                                "properties": {
                                    "ip": {"type": "string", "required_in": [4.0]},
                                },
                            },
                            "DnsTarget": {
                                "object_type": "widgetmgmt.v4.DnsTarget",
                                "properties": {
                                    "hostname": {
                                        "type": "string",
                                        "required_in": [4.0],
                                    },
                                },
                            },
                        },
                    },
                    "isEnabled": {"type": "boolean", "required_in": []},
                    "readOnlyField": {"type": "string", "readOnly": True},
                    "tenantId": {"type": "string"},
                },
            },
            "parameters": {
                "clusterExtId": {
                    "type": "string",
                    "required": True,
                    "in": "path",
                    "description": "Cluster ID",
                },
                "X-Request-Id": {
                    "type": "string",
                    "in": "header",
                },
            },
        },
        "listWidgets": {
            "versions": [4.0],
            "http_method": "get",
            "summary": "List widgets",
            "filter_examples": [
                {"field": "name", "example": "https://pc/?$filter=name eq 'x'"},
            ],
            "orderby_examples": [
                {"field": "name", "example": "https://pc/?$orderby=name asc"},
            ],
            "select_fields": [f"field{i}" for i in range(12)],
        },
        "doThing": {
            "versions": [4.0],
            "http_method": "post",
            "summary": "Do a thing",
            "parameters": {
                "extId": {"type": "string", "in": "path"},
                "mode": {
                    "type": "string",
                    "in": "query",
                    "enum": ["FAST", "SLOW", "$UNKNOWN"],
                },
            },
            "schema": {
                "request": {
                    "username": {
                        "type": "string",
                        "required_in": [4.0],
                        "readOnly": False,
                        "versions": [4.0],
                        "example": "john_doe",
                    },
                    "password": {
                        "type": "string",
                        "required_in": [4.0],
                        "readOnly": False,
                        "versions": [4.0],
                    },
                }
            },
        },
    },
    "gadgetmgmt": {
        "createGadget": {
            "versions": [4.0],
            "http_method": "post",
            "summary": "Create a Gadget",
            "schema": {"request": {}},
        },
        "listGadgets": {
            "versions": [4.0],
            "http_method": "get",
            "summary": "List gadgets",
        },
    },
    "bannermgmt": {
        "updateBanner": {
            "versions": [4.1],
            "http_method": "put",
            "summary": "Update banner",
            "schema": {
                "request": {
                    "content": {
                        "type": "string",
                        "description": "Banner text.",
                        "required_in": [],
                        "readOnly": False,
                        "versions": [4.1],
                        "maxLength": 10000,
                    },
                    "isEnabled": {
                        "type": "boolean",
                        "description": "Whether banner is enabled.",
                        "required_in": [],
                        "readOnly": False,
                        "versions": [4.1],
                    },
                },
            },
        },
    },
    "certmgmt": {
        "createCertProvider": {
            "versions": [4.0],
            "http_method": "post",
            "summary": "Create cert provider",
            "schema": {
                "request": {
                    "name": {
                        "type": "string",
                        "required_in": [4.0],
                        "readOnly": False,
                        "versions": [4.0],
                        "example": "CAC",
                    },
                    "clientCaChain": {
                        "type": "string",
                        "required_in": [4.0],
                        "readOnly": False,
                        "versions": [4.0],
                    },
                    "isCertAuthEnabled": {
                        "type": "boolean",
                        "required_in": [4.0],
                        "readOnly": False,
                        "versions": [4.0],
                    },
                    "dirSvcExtID": {
                        "type": "string",
                        "required_in": [4.0],
                        "readOnly": False,
                        "versions": [4.0],
                        "example": "e7742aa2-5139-45f3-bce7-ff51370d9a0f",
                    },
                    "tenantId": {
                        "type": "string",
                        "readOnly": True,
                        "versions": [4.0],
                    },
                    "createdBy": {
                        "type": "string",
                        "readOnly": True,
                        "versions": [4.0],
                        "example": "390b7801-...",
                    },
                },
            },
        },
    },
}


@pytest.fixture()
def mock_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write fake entity_map source and compat JSON, patch module paths."""
    entity_map_file = tmp_path / "entity_map.py"
    entity_map_file.write_text(_ENTITY_MAP_SRC, encoding="utf-8")

    compat_file = tmp_path / "compat.json"
    with open(compat_file, "w", encoding="utf-8") as fh:
        json.dump(_COMPAT_MAP, fh)

    out_dir = tmp_path / "examples"

    monkeypatch.setattr(mod, "_ENTITY_MAP_PATH", entity_map_file)
    monkeypatch.setattr(mod, "_COMPAT_MAP_PATH", compat_file)
    monkeypatch.setattr(mod, "_OUTPUT_DIR", out_dir)
    return out_dir


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestCamelToSnake:
    def test_pascal(self) -> None:
        assert mod._camel_to_snake("StorageContainer") == "storage_container"

    def test_camel(self) -> None:
        assert mod._camel_to_snake("clusterExtId") == "cluster_ext_id"

    def test_single(self) -> None:
        assert mod._camel_to_snake("name") == "name"

    def test_acronym(self) -> None:
        assert mod._camel_to_snake("HTMLParser") == "html_parser"


class TestSnakeToCamel:
    def test_multi(self) -> None:
        assert mod._snake_to_camel("create_widget") == "createWidget"

    def test_single(self) -> None:
        assert mod._snake_to_camel("list") == "list"


class TestFilterEnum:
    def test_removes_special(self) -> None:
        assert mod._filter_enum(["A", "$UNKNOWN", "B", "$REDACTED"]) == ["A", "B"]

    def test_keeps_normal(self) -> None:
        assert mod._filter_enum(["ON", "OFF"]) == ["ON", "OFF"]

    def test_empty(self) -> None:
        assert mod._filter_enum([]) == []


class TestExtractOdataExpr:
    def test_filter(self) -> None:
        url = "https://pc/?$filter=name eq 'x'"
        assert mod._extract_odata_expr(url) == "name eq 'x'"

    def test_orderby(self) -> None:
        url = "https://pc/?$orderby=name asc"
        assert mod._extract_odata_expr(url) == "name asc"

    def test_select(self) -> None:
        url = "https://pc/?$select=name,id"
        assert mod._extract_odata_expr(url) == "name,id"

    def test_no_match(self) -> None:
        plain = "no-odata-here"
        assert mod._extract_odata_expr(plain) == plain


class TestExampleValue:
    def test_boolean_enabled(self) -> None:
        assert mod._example_value("boolean", "isEnabled") is True

    def test_boolean_disabled(self) -> None:
        assert mod._example_value("boolean", "isDisabled") is False

    def test_boolean_generic(self) -> None:
        assert mod._example_value("boolean", "flag") is True

    def test_integer_port(self) -> None:
        assert mod._example_value("integer", "port") == 443

    def test_integer_memory(self) -> None:
        assert mod._example_value("integer", "memoryBytes") == 4294967296

    def test_integer_count(self) -> None:
        assert mod._example_value("integer", "nodeCount") == 2

    def test_integer_generic(self) -> None:
        assert mod._example_value("integer", "retries") == 1

    def test_number(self) -> None:
        assert mod._example_value("number", "ratio") == 1.0

    def test_string_name(self) -> None:
        assert mod._example_value("string", "clusterName") == "example-clusterName"

    def test_string_description(self) -> None:
        assert mod._example_value("string", "description") == "Example description"

    def test_string_email(self) -> None:
        assert mod._example_value("string", "userEmail") == "user@example.com"

    def test_string_ip(self) -> None:
        assert mod._example_value("string", "ipAddress") == "192.168.1.1"

    def test_string_uuid(self) -> None:
        val = mod._example_value("string", "entityUuid")
        assert val == "00000000-0000-0000-0000-000000000000"

    def test_string_url(self) -> None:
        assert mod._example_value("string", "callbackUrl") == "https://example.com"

    def test_string_password(self) -> None:
        assert mod._example_value("string", "password") == "<secret>"

    def test_string_generic(self) -> None:
        assert mod._example_value("string", "foobar") == "example-value"

    def test_empty_type(self) -> None:
        assert mod._example_value("", "foo") == "example-value"

    def test_unknown_type(self) -> None:
        assert mod._example_value("binary", "data") == "example-value"

    def test_schema_example_overrides(self) -> None:
        assert mod._example_value("string", "name", "my-example") == "my-example"

    def test_schema_example_int(self) -> None:
        assert mod._example_value("integer", "port", 8080) == 8080

    def test_schema_example_none_falls_through(self) -> None:
        assert mod._example_value("string", "foobar", None) == "example-value"


class TestFormatConstraints:
    def test_empty(self) -> None:
        assert mod._format_constraints({}) == "-"

    def test_pattern_only(self) -> None:
        result = mod._format_constraints({"pattern": "^[a-z]+$"})
        assert "pattern: `^[a-z]+$`" in result

    def test_min_max_length(self) -> None:
        result = mod._format_constraints({"minLength": 1, "maxLength": 64})
        assert "len: 1..64" in result

    def test_min_length_only(self) -> None:
        result = mod._format_constraints({"minLength": 1})
        assert "minLen: 1" in result

    def test_max_length_only(self) -> None:
        result = mod._format_constraints({"maxLength": 128})
        assert "maxLen: 128" in result

    def test_min_max_items(self) -> None:
        result = mod._format_constraints({"minItems": 1, "maxItems": 10})
        assert "items: 1..10" in result

    def test_combined(self) -> None:
        result = mod._format_constraints(
            {
                "pattern": "^[A-Z]$",
                "minLength": 1,
                "maxLength": 1,
            }
        )
        assert "pattern:" in result
        assert "len: 1..1" in result


class TestMdEscape:
    def test_pipe(self) -> None:
        assert mod._md_escape("a|b") == "a\\|b"

    def test_newline(self) -> None:
        assert mod._md_escape("line1\nline2") == "line1 line2"

    def test_strip(self) -> None:
        assert mod._md_escape("  text  ") == "text"


class TestGetOpData:
    def test_found(self) -> None:
        result = mod._get_op_data(_COMPAT_MAP, "widgetmgmt", "create_widget")
        assert result is not None
        assert result["summary"] == "Create a Widget"

    def test_empty_method(self) -> None:
        assert mod._get_op_data(_COMPAT_MAP, "widgetmgmt", "") is None

    def test_unknown(self) -> None:
        assert mod._get_op_data(_COMPAT_MAP, "widgetmgmt", "unknown_op") is None


class TestIsParentIdParam:
    def test_parent_id_param_match(self) -> None:
        entry = {"parent_id_param": "clusterExtId"}
        assert mod._is_parent_id_param("clusterExtId", entry) is True

    def test_extid_suffix(self) -> None:
        assert mod._is_parent_id_param("dirSvcExtId", {}) is True

    def test_ext_id_literal(self) -> None:
        assert mod._is_parent_id_param("ext_id", {}) is False

    def test_schema_field(self) -> None:
        assert mod._is_parent_id_param("name", {}) is False

    def test_extid_exact(self) -> None:
        assert mod._is_parent_id_param("extId", {}) is False

    def test_non_id_field(self) -> None:
        entry = {"parent_id_param": "clusterExtId"}
        assert mod._is_parent_id_param("isCertAuthEnabled", entry) is False


class TestFormatParentParams:
    def test_with_dep(self) -> None:
        entry = {"parent_entity": "cluster"}
        lines = mod._format_parent_params(["body", "clusterExtId"], entry)
        assert lines[0] == "          params:"
        assert len(lines) == 2
        assert "clusterExtId" in lines[1]
        assert "REQUIRED parent param" in lines[1]
        assert lines[1].startswith("            ")

    def test_without_dep(self) -> None:
        entry = {}
        lines = mod._format_parent_params(["parentId"], entry)
        assert lines[0] == "          params:"
        assert len(lines) == 2
        assert "REQUIRED param" in lines[1]

    def test_skip_body_and_extid(self) -> None:
        entry = {"parent_entity": "cluster"}
        lines = mod._format_parent_params(["body", "extId", "_hidden"], entry)
        assert lines == []

    def test_no_body_schema_params(self) -> None:
        """No-body entity: schema fields rendered with example values."""
        entry = {
            "parent_entity": "directory_service",
            "parent_id_param": "dirSvcExtID",
        }
        schema = {
            "name": {
                "type": "string",
                "required_in": [4.0],
                "versions": [4.0],
                "example": "CAC",
            },
            "isCertAuthEnabled": {
                "type": "boolean",
                "required_in": [4.0],
                "versions": [4.0],
            },
            "dirSvcExtID": {
                "type": "string",
                "required_in": [4.0],
                "versions": [4.0],
                "example": "e7742aa2-5139-45f3-bce7-ff51370d9a0f",
            },
        }
        params = [
            "name",
            "isCertAuthEnabled",
            "dirSvcExtID",
            "extId",
        ]
        lines = mod._format_parent_params(
            params,
            entry,
            schema_request=schema,
        )
        joined = "\n".join(lines)
        assert lines[0] == "          params:"
        assert "CAC" in joined
        assert "true" in joined.lower()
        assert "REQUIRED parent param" in joined
        assert "dirSvcExtID" in joined
        assert joined.count("REQUIRED parent param") == 1

    def test_no_body_readonly_skipped(self) -> None:
        """ReadOnly schema fields are excluded from no-body entity output."""
        entry = {}
        schema = {
            "name": {
                "type": "string",
                "required_in": [4.0],
                "versions": [4.0],
                "readOnly": False,
            },
            "createdBy": {"type": "string", "readOnly": True},
            "tenantId": {"type": "string", "readOnly": True},
        }
        lines = mod._format_parent_params(
            ["name", "createdBy", "tenantId"],
            entry,
            schema_request=schema,
        )
        joined = "\n".join(lines)
        assert "name" in joined
        assert "createdBy" not in joined
        assert "tenantId" not in joined

    def test_no_body_without_schema(self) -> None:
        """No-body with no schema falls back to <value>."""
        entry = {}
        lines = mod._format_parent_params(
            ["somefield"],
            entry,
            schema_request={},
        )
        assert lines[0] == "          params:"
        assert len(lines) == 2
        assert "<value>" in lines[1]

    def test_no_body_nested_object_expanded(self) -> None:
        """Object params in no-body entities expand nested properties."""
        entry = {}
        schema = {
            "revInfo": {
                "type": "object",
                "required_in": [],
                "versions": [4.0],
                "properties": {
                    "isEnabled": {
                        "type": "boolean",
                        "required_in": [],
                        "versions": [4.0],
                        "example": False,
                    },
                },
            },
        }
        lines = mod._format_parent_params(
            ["revInfo"],
            entry,
            schema_request=schema,
        )
        joined = "\n".join(lines)
        assert lines[0] == "          params:"
        assert "revInfo:" in joined
        assert "isEnabled:" in joined
        assert "false" in joined


# ---------------------------------------------------------------------------
# Schema -> YAML tests
# ---------------------------------------------------------------------------


class TestSchemaToYamlLines:
    def test_required_string(self) -> None:
        fields = {"name": {"type": "string", "required_in": [4.0], "versions": [4.0]}}
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "name:" in joined
        assert "REQUIRED" in joined
        assert not joined.startswith("# ")

    def test_optional_commented(self) -> None:
        fields = {"desc": {"type": "string", "required_in": []}}
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        assert any(line.startswith("# ") for line in lines)

    def test_enum_field(self) -> None:
        fields = {
            "status": {
                "type": "enum",
                "required_in": [],
                "enum": {"ON": {}, "OFF": {}, "$UNKNOWN": {}},
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "ON" in joined
        assert "enum:" in joined

    def test_object_with_children(self) -> None:
        fields = {
            "config": {
                "type": "object",
                "required_in": [4.0],
                "versions": [4.0],
                "children": {
                    "port": {
                        "type": "integer",
                        "required_in": [4.0],
                        "versions": [4.0],
                    },
                },
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        assert any("config:" in line for line in lines)
        assert any("port:" in line for line in lines)

    def test_array_with_items(self) -> None:
        fields = {
            "tags": {
                "type": "array",
                "required_in": [4.0],
                "versions": [4.0],
                "items": {
                    "properties": {
                        "key": {
                            "type": "string",
                            "required_in": [4.0],
                            "versions": [4.0],
                        },
                    },
                },
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        assert any("tags:" in line for line in lines)
        assert any("key:" in line for line in lines)

    def test_array_empty_items(self) -> None:
        fields = {"ids": {"type": "array", "required_in": [], "items": {}}}
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        assert any("[]" in line for line in lines)

    def test_array_simple_typed_items(self) -> None:
        """Array with simple-typed items should show example value."""
        fields = {
            "urls": {
                "type": "array",
                "required_in": [],
                "versions": [4.0],
                "items": {
                    "type": "string",
                    "example": "http://example.com/crl",
                    "pattern": "^https?://",
                },
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "urls:" in joined
        assert "http://example.com/crl" in joined

    def test_oneof_variants(self) -> None:
        fields = {
            "target": {
                "type": "oneOf",
                "required_in": [4.0],
                "versions": [4.0],
                "variants": {
                    "IpTarget": {
                        "object_type": "v4.IpTarget",
                        "properties": {
                            "ip": {
                                "type": "string",
                                "required_in": [4.0],
                                "versions": [4.0],
                            },
                        },
                    },
                    "DnsTarget": {
                        "object_type": "v4.DnsTarget",
                        "properties": {
                            "host": {
                                "type": "string",
                                "required_in": [4.0],
                                "versions": [4.0],
                            },
                        },
                    },
                },
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "oneOf:" in joined
        assert "$objectType" in joined
        assert "OR" in joined

    def test_depth_limit(self) -> None:
        fields = {"deep": {"type": "string", "required_in": [4.0], "versions": [4.0]}}
        lines = mod._schema_to_yaml_lines(fields, indent=0, depth=10)
        assert lines == []

    def test_skip_readonly(self) -> None:
        fields = {"secret": {"type": "string", "readOnly": True}}
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        assert lines == []

    def test_skip_internal_field(self) -> None:
        fields = {"tenantId": {"type": "string"}}
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        assert lines == []

    def test_schema_example_used(self) -> None:
        fields = {
            "endpoint": {
                "type": "string",
                "required_in": [4.0],
                "versions": [4.0],
                "example": "https://api.example.com/v1",
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "https://api.example.com/v1" in joined

    def test_version_gating(self) -> None:
        fields = {"new_field": {"type": "string", "required_in": [], "versions": [4.1]}}
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "v4.1" in joined

    def test_boolean_value(self) -> None:
        fields = {
            "isActive": {"type": "boolean", "required_in": [4.0], "versions": [4.0]}
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "true" in joined

    def test_commented_mode(self) -> None:
        fields = {"name": {"type": "string", "required_in": [4.0], "versions": [4.0]}}
        lines = mod._schema_to_yaml_lines(fields, indent=0, commented=True)
        assert all(line.startswith("# ") for line in lines if line.strip())

    def test_required_in_subset(self) -> None:
        """REQUIRED in 4.0 only should show 'REQUIRED in 4.0'."""
        fields = {
            "name": {
                "type": "string",
                "required_in": [4.0],
                "versions": [4.0, 4.1],
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "REQUIRED in 4.0" in joined

    def test_object_with_properties_key(self) -> None:
        """Metadata map stores nested fields under 'properties', not 'children'."""
        fields = {
            "revInfo": {
                "type": "object",
                "required_in": [],
                "versions": [4.0],
                "properties": {
                    "isEnabled": {
                        "type": "boolean",
                        "required_in": [],
                        "versions": [4.0],
                        "example": False,
                    },
                },
            }
        }
        lines = mod._schema_to_yaml_lines(fields, indent=0)
        joined = "\n".join(lines)
        assert "revInfo:" in joined
        assert "isEnabled:" in joined
        assert "false" in joined


# ---------------------------------------------------------------------------
# Generate YAML / Markdown
# ---------------------------------------------------------------------------


class TestGenerateYaml:
    def test_basic_entity(self) -> None:
        entity = {
            "namespace": "widgetmgmt",
            "sdk_name": "ntnx_widget_py_client",
            "create_method_name": "create_widget",
            "list_method_name": "list_widgets",
            "update_method_name": "update_widget_by_id",
            "operations": ["do_thing", "do_other", "do_more", "do_extra"],
            "method_params": {"create": ["body", "clusterExtId"]},
            "parent_entity": "cluster",
        }
        entity_map = {"widget": entity, "cluster": {"namespace": "clustermgmt"}}
        yaml_str = mod._generate_yaml("widget", entity, _COMPAT_MAP, entity_map)
        assert "widget Example Configuration" in yaml_str
        assert "domains:" in yaml_str
        assert "data:" in yaml_str
        assert "# === CREATE ===" in yaml_str
        assert "# === UPDATE ===" in yaml_str
        assert "# === DELETE ===" in yaml_str
        assert "# === OPERATIONS ===" in yaml_str
        assert "do_thing" in yaml_str
        assert "Other operations:" in yaml_str
        assert "filter:" in yaml_str
        assert "Filterable fields:" in yaml_str
        assert "Orderable fields:" in yaml_str
        assert "Selectable fields:" in yaml_str
        assert "... and" in yaml_str
        # Operation body should be rendered
        assert "#       body:" in yaml_str
        assert "john_doe" in yaml_str
        assert "          params:" in yaml_str
        assert "            clusterExtId:" in yaml_str

    def test_no_compat_schema(self) -> None:
        entity = {
            "namespace": "unknown",
            "sdk_name": "ntnx_unknown",
            "create_method_name": "create_thing",
            "list_method_name": "",
            "update_method_name": "",
            "operations": [],
            "method_params": {"create": ["body"]},
        }
        yaml_str = mod._generate_yaml("thing", entity, {}, {})
        assert "Schema not available" in yaml_str

    def test_empty_schema_request(self) -> None:
        entity = {
            "namespace": "gadgetmgmt",
            "sdk_name": "ntnx_gadget",
            "create_method_name": "create_gadget",
            "list_method_name": "list_gadgets",
            "update_method_name": "",
            "operations": [],
            "method_params": {"create": ["body"]},
        }
        yaml_str = mod._generate_yaml("gadget", entity, _COMPAT_MAP, {})
        assert "body: {}" in yaml_str

    def test_list_no_filter_examples(self) -> None:
        compat = {
            "ns": {
                "listThings": {"versions": [4.0], "http_method": "get"},
            }
        }
        entity = {
            "namespace": "ns",
            "sdk_name": "sdk",
            "create_method_name": "",
            "list_method_name": "list_things",
            "update_method_name": "",
            "operations": [],
            "method_params": {},
        }
        yaml_str = mod._generate_yaml("thing", entity, compat, {})
        assert "<filter-expression>" in yaml_str

    def test_no_list_method(self) -> None:
        entity = {
            "namespace": "ns",
            "sdk_name": "sdk",
            "create_method_name": "",
            "list_method_name": "",
            "update_method_name": "",
            "operations": [],
            "method_params": {},
        }
        yaml_str = mod._generate_yaml("thing", entity, {}, {})
        assert "List with filter" not in yaml_str

    def test_no_body_entity(self) -> None:
        entity = {
            "namespace": "certmgmt",
            "sdk_name": "ntnx_cert_py_client",
            "create_method_name": "create_cert_provider",
            "get_method_name": "get_cert_provider_by_id",
            "update_method_name": "",
            "list_method_name": "",
            "operations": [],
            "method_params": {
                "create": [
                    "name",
                    "clientCaChain",
                    "isCertAuthEnabled",
                    "dirSvcExtID",
                    "tenantId",
                    "createdBy",
                    "extId",
                ],
            },
            "parent_entity": "directory_service",
            "parent_id_param": "dirSvcExtID",
        }
        entity_map = {
            "cert_provider": entity,
            "directory_service": {"namespace": "iam"},
        }
        yaml_str = mod._generate_yaml(
            "cert_provider",
            entity,
            _COMPAT_MAP,
            entity_map,
        )
        assert "# === CREATE ===" in yaml_str
        assert "body:" not in yaml_str
        assert "          params:" in yaml_str
        assert 'name: "CAC"' in yaml_str
        assert "isCertAuthEnabled:" in yaml_str
        assert "REQUIRED parent param" in yaml_str
        assert "dirSvcExtID" in yaml_str
        assert "tenantId" not in yaml_str
        assert "createdBy" not in yaml_str

    def test_readonly_entity_no_resources(self) -> None:
        """Data-only entities should not emit a resources: block."""
        entity = {
            "namespace": "ns",
            "sdk_name": "sdk",
            "create_supported": False,
            "create_method_name": "",
            "get_method_name": "get_thing_by_id",
            "update_supported": False,
            "update_method_name": "",
            "delete_supported": False,
            "list_method_name": "list_things",
            "operations": [],
            "method_params": {},
        }
        yaml_str = mod._generate_yaml("thing", entity, {}, {})
        assert "resources:" not in yaml_str
        assert "# === CREATE ===" not in yaml_str
        assert "# === UPDATE ===" not in yaml_str
        assert "# === DELETE ===" not in yaml_str
        assert "data:" in yaml_str

    def test_update_only_entity(self) -> None:
        entity = {
            "namespace": "bannermgmt",
            "sdk_name": "ntnx_banner_py_client",
            "create_supported": False,
            "create_method_name": "",
            "get_method_name": "get_banner",
            "update_method_name": "update_banner",
            "list_method_name": "",
            "operations": [],
            "method_params": {"update": ["body"]},
        }
        yaml_str = mod._generate_yaml("banner", entity, _COMPAT_MAP, {})
        assert "# === CREATE ===" not in yaml_str
        assert "import-then-update" in yaml_str
        assert "cannot be created" in yaml_str
        assert "my_banner:" in yaml_str
        assert "body:" in yaml_str
        assert "content:" in yaml_str
        assert "isEnabled:" in yaml_str


class TestGenerateMarkdown:
    def test_full_entity(self) -> None:
        entity = {
            "namespace": "widgetmgmt",
            "sdk_name": "ntnx_widget_py_client",
            "create_method_name": "create_widget",
            "get_method_name": "get_widget_by_id",
            "update_method_name": "update_widget_by_id",
            "delete_method_name": "delete_widget_by_id",
            "list_method_name": "list_widgets",
            "operations": ["do_thing"],
            "parent_entity": "cluster",
            "method_params": {"create": ["body", "clusterExtId"]},
        }
        md = mod._generate_markdown("widget", entity, _COMPAT_MAP)
        assert "# widget" in md
        assert "## Parent Entity" in md
        assert "## Operations" in md
        assert "Create" in md
        assert "## Create Schema" in md
        assert "## Operation Parameters" in md
        assert "## Filter / Sort / Select" in md
        assert "### Filters" in md
        assert "### Orderby" in md
        assert "### Select Fields" in md
        assert "Do a thing" in md
        assert "`do_thing` Schema" in md
        assert "username" in md

    def test_no_deps(self) -> None:
        entity = {
            "namespace": "gadgetmgmt",
            "sdk_name": "ntnx_gadget",
            "create_method_name": "create_gadget",
            "get_method_name": "get_gadget_by_id",
            "update_method_name": "",
            "delete_method_name": "delete_gadget_by_id",
            "list_method_name": "",
            "operations": [],
            "method_params": {},
        }
        md = mod._generate_markdown("gadget", entity, _COMPAT_MAP)
        assert "## Dependencies" not in md

    def test_unsupported_op(self) -> None:
        entity = {
            "namespace": "ns",
            "sdk_name": "sdk",
            "create_method_name": "",
            "get_method_name": "",
            "update_method_name": "",
            "delete_method_name": "",
            "list_method_name": "",
            "operations": ["unknown_op"],
            "method_params": {},
            "create_supported": False,
            "update_supported": False,
            "delete_supported": False,
        }
        md = mod._generate_markdown("thing", entity, {})
        assert "No" in md
        assert "`unknown_op`" in md

    def test_update_only_entity(self) -> None:
        entity = {
            "namespace": "bannermgmt",
            "sdk_name": "ntnx_banner_py_client",
            "create_supported": False,
            "create_method_name": "",
            "get_method_name": "get_banner",
            "update_method_name": "update_banner",
            "delete_method_name": "",
            "delete_supported": False,
            "list_method_name": "",
            "operations": [],
            "method_params": {"update": ["body"]},
        }
        md = mod._generate_markdown("banner", entity, _COMPAT_MAP)
        assert "## Create Schema" not in md
        assert "## Update Schema" in md
        assert "content" in md
        assert "isEnabled" in md
        assert "maxLen: 10000" in md


class TestMdSchemaRows:
    def test_nested_children(self) -> None:
        fields = {
            "config": {
                "type": "object",
                "required_in": [4.0],
                "versions": [4.0],
                "children": {
                    "port": {
                        "type": "integer",
                        "required_in": [4.0],
                        "versions": [4.0],
                    },
                },
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "config" in joined
        assert "port" in joined

    def test_array_items(self) -> None:
        fields = {
            "list_field": {
                "type": "array",
                "items": {
                    "properties": {
                        "val": {
                            "type": "string",
                            "required_in": [4.0],
                            "versions": [4.0],
                        },
                    },
                },
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "[].val" in joined

    def test_array_simple_typed_items(self) -> None:
        """Simple-typed items show type and constraints in sub-row."""
        fields = {
            "urls": {
                "type": "array",
                "required_in": [],
                "versions": [4.0],
                "items": {
                    "type": "string",
                    "pattern": "^https?://",
                },
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "[].item" in joined
        assert "string" in joined
        assert "pattern:" in joined

    def test_oneof(self) -> None:
        fields = {
            "target": {
                "type": "oneOf",
                "required_in": [4.0],
                "versions": [4.0],
                "variants": {
                    "IpTarget": {
                        "object_type": "v4.IpTarget",
                        "properties": {
                            "ip": {
                                "type": "string",
                                "required_in": [4.0],
                                "versions": [4.0],
                            },
                        },
                    },
                },
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "oneOf" in joined
        assert "$objectType" in joined
        assert "IpTarget" in joined

    def test_skip_readonly(self) -> None:
        fields = {"secret": {"type": "string", "readOnly": True}}
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        assert sections == []

    def test_enum_display(self) -> None:
        fields = {
            "mode": {"type": "enum", "enum": {"A": {}, "B": {}}, "required_in": []}
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "A, B" in joined

    def test_constraints_column(self) -> None:
        fields = {
            "code": {
                "type": "string",
                "required_in": [4.0],
                "versions": [4.0],
                "pattern": r"^[A-Z]{3}$",
                "minLength": 3,
                "maxLength": 3,
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "pattern:" in joined
        assert "len: 3..3" in joined

    def test_required_yes_all_versions(self) -> None:
        fields = {
            "name": {
                "type": "string",
                "required_in": [4.0, 4.1],
                "versions": [4.0, 4.1],
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "| Yes |" in joined

    def test_required_partial_versions(self) -> None:
        fields = {
            "name": {
                "type": "string",
                "required_in": [4.0],
                "versions": [4.0, 4.1],
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "Yes (4.0 only)" in joined

    def test_required_no(self) -> None:
        fields = {
            "name": {
                "type": "string",
                "required_in": [],
                "versions": [4.0],
            }
        }
        sections: list[str] = []
        mod._md_schema_rows(fields, sections, depth=0)
        joined = "\n".join(sections)
        assert "| No |" in joined


# ---------------------------------------------------------------------------
# Load functions
# ---------------------------------------------------------------------------


class TestLoadEntityMap:
    def test_load(self, mock_paths: Path) -> None:
        entity_map = mod._load_entity_map()
        assert "widget" in entity_map
        assert "gadget" in entity_map

    def test_missing_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        src = tmp_path / "empty.py"
        src.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(mod, "_ENTITY_MAP_PATH", src)
        with pytest.raises(RuntimeError, match="entity_map not found"):
            mod._load_entity_map()


class TestLoadCompatMap:
    def test_load(self, mock_paths: Path) -> None:
        compat = mod._load_compat_map()
        assert "widgetmgmt" in compat


# ---------------------------------------------------------------------------
# generate_all
# ---------------------------------------------------------------------------


class TestHelperSchemaToYamlLines:
    """Tests for _helper_schema_to_yaml_lines."""

    def test_required_field(self) -> None:
        schema = {
            "cvm_ip": {
                "type": "string",
                "required": True,
                "description": "CVM IP address",
                "example": "10.0.0.1",
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=0)
        joined = "\n".join(lines)
        assert 'cvm_ip: "10.0.0.1"' in joined
        assert "REQUIRED" in joined
        assert "CVM IP address" in joined

    def test_optional_field_commented(self) -> None:
        schema = {
            "nameserver": {
                "type": "string",
                "required": False,
                "description": "DNS nameserver",
                "example": "8.8.8.8",
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=0)
        joined = "\n".join(lines)
        assert joined.startswith("# ")
        assert "nameserver" in joined

    def test_boolean_example(self) -> None:
        schema = {
            "downgrade": {
                "type": "boolean",
                "required": False,
                "description": "Downgrade mode",
                "example": False,
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=0)
        joined = "\n".join(lines)
        assert "false" in joined

    def test_dict_example(self) -> None:
        schema = {
            "network_settings": {
                "type": "object",
                "required": False,
                "description": "Network config",
                "example": {"dns": "10.0.0.53", "ntp": "pool.ntp.org"},
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=0)
        joined = "\n".join(lines)
        assert "network_settings:" in joined
        assert "dns" in joined
        assert "ntp" in joined

    def test_list_example_with_dicts(self) -> None:
        schema = {
            "nodes_list": {
                "type": "array",
                "required": True,
                "description": "Node list",
                "example": [{"node_serial": "ABC123", "hostname": "host-1"}],
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=0)
        joined = "\n".join(lines)
        assert "nodes_list:" in joined
        assert "node_serial" in joined
        assert "ABC123" in joined

    def test_list_example_with_strings(self) -> None:
        schema = {
            "tags": {
                "type": "array",
                "required": False,
                "description": "Tags",
                "example": ["tag1", "tag2"],
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=0)
        joined = "\n".join(lines)
        assert "tags:" in joined
        assert "tag1" in joined

    def test_none_example_uses_fallback(self) -> None:
        schema = {
            "vlan_id": {
                "type": "integer",
                "required": False,
                "description": "VLAN ID",
                "example": None,
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=0)
        joined = "\n".join(lines)
        assert "vlan_id:" in joined

    def test_indent(self) -> None:
        schema = {
            "name": {
                "type": "string",
                "required": True,
                "description": "Name",
                "example": "test",
            }
        }
        lines = mod._helper_schema_to_yaml_lines(schema, indent=8)
        assert lines[0].startswith("        ")


class TestGenerateCustomHelperYaml:
    """Tests for _generate_custom_helper_yaml."""

    def test_basic_output(self) -> None:
        entry = {
            "namespace": "foundation_central",
            "sdk_name": "ztf.helpers.update_cvm_foundation",
            "dependent_entities": [],
            "use_ztf_helper": True,
            "create_supported": True,
            "update_supported": True,
            "delete_supported": False,
            "helper_schema": {
                "cvm_ip": {
                    "type": "string",
                    "required": True,
                    "description": "CVM IP",
                    "example": "10.0.0.1",
                },
            },
        }
        yaml_str = mod._generate_custom_helper_yaml("update_cvm_foundation", entry)
        assert "update_cvm_foundation Example Configuration" in yaml_str
        assert "use_ztf_helper: true" in yaml_str
        assert "domains:" in yaml_str
        assert "resources:" in yaml_str
        assert "# === CREATE ===" in yaml_str
        assert "body:" in yaml_str
        assert "cvm_ip" in yaml_str
        assert "# === UPDATE ===" in yaml_str
        assert "# === DELETE ===" not in yaml_str
        assert "Credentials" in yaml_str

    def test_with_dependencies(self) -> None:
        entry = {
            "namespace": "foundation_central",
            "sdk_name": "ztf.helpers.fc_imaging",
            "dependent_entities": ["generate_fc_api_key"],
            "use_ztf_helper": True,
            "create_supported": True,
            "update_supported": False,
            "delete_supported": False,
            "helper_schema": {},
        }
        yaml_str = mod._generate_custom_helper_yaml("fc_imaging", entry)
        assert "Dependencies: generate_fc_api_key" in yaml_str

    def test_no_schema(self) -> None:
        entry = {
            "namespace": "ns",
            "sdk_name": "ztf.helpers.foo",
            "dependent_entities": [],
            "use_ztf_helper": True,
            "create_supported": True,
            "update_supported": False,
            "delete_supported": False,
            "helper_schema": {},
        }
        yaml_str = mod._generate_custom_helper_yaml("foo", entry)
        assert "No schema defined" in yaml_str

    def test_delete_supported(self) -> None:
        entry = {
            "namespace": "ns",
            "sdk_name": "ztf.helpers.bar",
            "dependent_entities": [],
            "use_ztf_helper": True,
            "create_supported": True,
            "update_supported": False,
            "delete_supported": True,
            "helper_schema": {},
        }
        yaml_str = mod._generate_custom_helper_yaml("bar", entry)
        assert "# === DELETE ===" in yaml_str


class TestGenerateCustomHelperMarkdown:
    """Tests for _generate_custom_helper_markdown."""

    def test_basic_output(self) -> None:
        entry = {
            "namespace": "foundation_central",
            "sdk_name": "ztf.helpers.fc_cluster",
            "dependent_entities": ["fc_imaging"],
            "use_ztf_helper": True,
            "create_supported": True,
            "update_supported": False,
            "delete_supported": False,
            "helper_schema": {
                "cluster_name": {
                    "type": "string",
                    "required": True,
                    "description": "Cluster name",
                    "example": "my-cluster",
                },
                "redundancy_factor": {
                    "type": "integer",
                    "required": False,
                    "description": "RF",
                    "example": 2,
                },
            },
        }
        md = mod._generate_custom_helper_markdown("fc_cluster", entry)
        assert "# fc_cluster" in md
        assert "Custom ZTF Helper" in md
        assert "## Dependencies" in md
        assert "`fc_imaging`" in md
        assert "## Supported Operations" in md
        assert "| Create    | Yes |" in md
        assert "| Update    | No |" in md
        assert "## Body Fields" in md
        assert "| `cluster_name` | string | Yes | Cluster name |" in md
        assert "| `redundancy_factor` | integer | No | RF |" in md
        assert "## Example Body" in md
        assert "```yaml" in md
        assert 'cluster_name: "my-cluster"' in md
        assert "redundancy_factor: 2" in md

    def test_no_dependencies(self) -> None:
        entry = {
            "namespace": "ns",
            "sdk_name": "ztf.helpers.foo",
            "dependent_entities": [],
            "use_ztf_helper": True,
            "create_supported": True,
            "update_supported": False,
            "delete_supported": False,
            "helper_schema": {},
        }
        md = mod._generate_custom_helper_markdown("foo", entry)
        assert "## Dependencies" not in md

    def test_no_schema(self) -> None:
        entry = {
            "namespace": "ns",
            "sdk_name": "ztf.helpers.bar",
            "dependent_entities": [],
            "use_ztf_helper": True,
            "create_supported": False,
            "update_supported": True,
            "delete_supported": True,
            "helper_schema": {},
        }
        md = mod._generate_custom_helper_markdown("bar", entry)
        assert "## Body Fields" not in md
        assert "| Create    | No |" in md
        assert "| Update    | Yes |" in md
        assert "| Delete    | Yes |" in md

    def test_dict_and_list_examples_in_body(self) -> None:
        entry = {
            "namespace": "ns",
            "sdk_name": "ztf.helpers.baz",
            "dependent_entities": [],
            "use_ztf_helper": True,
            "create_supported": True,
            "update_supported": False,
            "delete_supported": False,
            "helper_schema": {
                "config": {
                    "type": "object",
                    "required": False,
                    "description": "Config",
                    "example": {"key": "value"},
                },
                "items": {
                    "type": "array",
                    "required": False,
                    "description": "Items",
                    "example": [{"id": "1"}],
                },
                "flag": {
                    "type": "boolean",
                    "required": False,
                    "description": "Flag",
                    "example": True,
                },
            },
        }
        md = mod._generate_custom_helper_markdown("baz", entry)
        assert "config:" in md
        assert "key: value" in md
        assert "items:" in md
        assert "id: 1" in md
        assert "flag: true" in md


class TestGenerateAll:
    def test_all_namespaces(
        self, mock_paths: Path, capsys: pytest.CaptureFixture
    ) -> None:
        mod.generate_all()
        out = capsys.readouterr().out
        assert "Generated 3/3" in out
        assert "INDEX.md" in out
        assert (mock_paths / "widgetmgmt" / "widget.yml").exists()
        assert (mock_paths / "widgetmgmt" / "widget.md").exists()
        assert (mock_paths / "gadgetmgmt" / "gadget.yml").exists()
        assert (mock_paths / "custom_ns" / "custom_helper.yml").exists()
        assert (mock_paths / "custom_ns" / "custom_helper.md").exists()
        assert (mock_paths / "INDEX.md").exists()

    def test_custom_helper_routing(
        self, mock_paths: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """use_ztf_helper entities are routed to custom helper generators."""
        mod.generate_all(namespace_filter="custom_ns")
        capsys.readouterr()
        yml_path = mock_paths / "custom_ns" / "custom_helper.yml"
        md_path = mock_paths / "custom_ns" / "custom_helper.md"
        assert yml_path.exists()
        assert md_path.exists()
        yml_content = yml_path.read_text()
        assert "use_ztf_helper: true" in yml_content
        assert "Custom ZTF Helper" in yml_content
        assert 'name: "test"' in yml_content
        md_content = md_path.read_text()
        assert "Custom ZTF Helper" in md_content
        assert "| `name` | string | Yes | Name |" in md_content

    def test_filter_namespace(
        self, mock_paths: Path, capsys: pytest.CaptureFixture
    ) -> None:
        mod.generate_all(namespace_filter="widgetmgmt")
        out = capsys.readouterr().out
        assert "Generated 1/1" in out
        assert (mock_paths / "widgetmgmt" / "widget.yml").exists()
        assert not (mock_paths / "gadgetmgmt").exists()

    def test_nonexistent_namespace(
        self, mock_paths: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("ERROR"):
            mod.generate_all(namespace_filter="nonexistent")
        assert "not found" in caplog.text

    def test_functions_file_generated(
        self, mock_paths: Path, capsys: pytest.CaptureFixture
    ) -> None:
        mod.generate_all()
        out = capsys.readouterr().out
        fn_path = mock_paths / "functions.py"
        assert fn_path.exists()
        content = fn_path.read_text()
        assert "def pad(" in content
        assert "def b64encode(" in content
        assert "def b64decode(" in content
        assert "def template(" in content
        assert "def read_file(" in content
        assert "def read_lines(" in content
        assert "def upper(" in content
        assert "def lower(" in content
        assert "def join(" in content
        assert "starter functions file" in out

    def test_functions_file_skipped_with_namespace_filter(
        self, mock_paths: Path, capsys: pytest.CaptureFixture
    ) -> None:
        mod.generate_all(namespace_filter="widgetmgmt")
        fn_path = mock_paths / "functions.py"
        assert not fn_path.exists()

    def test_index_includes_functions_section(
        self, mock_paths: Path, capsys: pytest.CaptureFixture
    ) -> None:
        mod.generate_all()
        capsys.readouterr()
        index = (mock_paths / "INDEX.md").read_text()
        assert "Custom Functions" in index
        assert "functions.py" in index
