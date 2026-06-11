"""Shared SDK invocation helpers for Nutanix API clients.

Provides dict-then-model fallback when calling SDK methods that accept a body,
so that namespaces that require model instances (e.g. Prism) work without
hardcoding per-SDK behavior.
"""

from __future__ import annotations

import importlib
import re
from typing import Any


def dict_to_sdk_model(
    api_method: Any,
    body_dict: dict[str, Any],
    client: Any,
) -> Any:
    """Convert a dict to the SDK model expected by an API method.

    Some SDKs require proper model objects instead of raw dicts.
    This function parses the method docstring to discover the expected model
    class and creates a proper SDK model instance.

    Args:
        api_method: The SDK API method (e.g. api.create_category).
        body_dict: The body dict to convert.
        client: The API client (used for deserialize).

    Returns:
        SDK model instance, or original dict if conversion fails.
    """
    doc = api_method.__doc__ or ""

    # Format: :type body: ... :class:`~ntnx_xxx_py_client.models.xxx.ModelName`
    match = re.search(
        r":type body:\s*:class:`~(ntnx_[a-z_]+_py_client)\.models\.[a-zA-Z0-9_.]+\.([A-Za-z]+)`",
        doc,
        re.DOTALL,
    )

    if not match:
        return body_dict

    sdk_package = match.group(1)
    class_name = match.group(2)

    try:
        sdk = importlib.import_module(sdk_package)
        model_class = getattr(sdk, class_name, None)

        if model_class is None:
            return body_dict

        if hasattr(model_class, "swagger_types") and hasattr(client, "deserialize"):
            attr_map = getattr(model_class, "attribute_map", {})

            entity_data: dict[str, Any] = {}
            for attr, attr_type in model_class.swagger_types.items():
                camel_key = attr_map.get(attr, attr)
                # Explicit None check: legitimate falsy values (False, 0,
                # "", [], {}) must not be coalesced into the camelCase
                # fallback or silently dropped.
                if attr in body_dict:
                    value = body_dict[attr]
                elif camel_key in body_dict:
                    value = body_dict[camel_key]
                else:
                    continue

                if value is None:
                    continue

                # Handle nested objects with $objectType discriminator (OneOf types)
                if isinstance(value, dict) and (
                    "$objectType" in value or "_object_type" in value
                ):
                    obj_type = value.get("$objectType") or value.get("_object_type")
                    if obj_type:
                        nested_class_name = obj_type.split(".")[-1]
                        nested_class = getattr(sdk, nested_class_name, None)
                        if nested_class:
                            nested_attr_map = getattr(nested_class, "attribute_map", {})
                            nested_data = {}
                            for n_attr, n_type in getattr(
                                nested_class, "swagger_types", {}
                            ).items():
                                n_camel = nested_attr_map.get(n_attr, n_attr)
                                # Explicit membership check preserves
                                # legitimate falsy values.
                                if n_attr in value:
                                    n_value = value[n_attr]
                                elif n_camel in value:
                                    n_value = value[n_camel]
                                else:
                                    continue
                                if n_value is not None:
                                    nested_data[n_attr] = client.deserialize(
                                        klass=n_type, data=n_value
                                    )
                            entity_data[attr] = nested_class(**nested_data)
                            continue

                entity_data[attr] = client.deserialize(klass=attr_type, data=value)

            return model_class(**entity_data)
        return model_class(**body_dict)
    except Exception:
        return body_dict


def call_api_with_body(
    api_method: Any,
    body_dict: dict[str, Any],
    client: Any,
    **kwargs: Any,
) -> Any:
    """Call an API method with body, converting to SDK model proactively.

    Some SDKs (notably Prism) require proper model objects instead of raw dicts.
    For POST operations, passing a dict causes an immediate "unsupported object
    type" exception. For PUT operations, the dict is silently accepted but the
    server misinterprets the fields, causing incorrect behavior (e.g. the server
    reads the old state instead of the updated values from the dict body).

    To handle both cases reliably, this function proactively converts the dict
    to a proper SDK model using dict_to_sdk_model. The conversion is safe: it
    falls back to the original dict if the model class can't be determined or
    instantiation fails, so SDKs that accept dicts natively are unaffected.

    Args:
        api_method: The SDK API method to call
        body_dict: The body dict to pass
        client: The API client
        **kwargs: Additional keyword arguments for the API call

    Returns:
        API response

    Raises:
        ApiException: If the API call fails
    """
    body = dict_to_sdk_model(api_method, body_dict, client)
    return api_method(body=body, **kwargs)


def deep_merge(
    base: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Deep merge updates into base dict.

    For nested dicts, recursively merges. None values in updates are skipped.

    Args:
        base: Base dict to merge into (modified in place).
        updates: Updates to apply.

    Returns:
        base (after merge).
    """
    for key, value in updates.items():
        if value is None:
            continue
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base
