"""Shared SDK invocation helpers for Nutanix API clients.

Provides dict-then-model fallback when calling SDK methods that accept a body,
so that namespaces that require model instances (e.g. Prism) work without
hardcoding per-SDK behavior.
"""

from __future__ import annotations

import importlib
import re
from typing import Any


def _build_model(
    model_class: Any,
    value: dict[str, Any],
    sdk: Any,
    client: Any,
) -> Any:
    """Instantiate model_class, recursively converting each declared attribute."""
    attr_map = getattr(model_class, "attribute_map", {})
    data: dict[str, Any] = {}
    for attr, attr_type in model_class.swagger_types.items():
        camel_key = attr_map.get(attr, attr)
        if attr in value:
            attr_value = value[attr]
        elif camel_key in value:
            attr_value = value[camel_key]
        else:
            continue
        if attr_value is None:
            continue
        data[attr] = _convert_field(attr_value, attr_type, sdk, client)
    return model_class(**data)


def _resolve_model_class(dotted_path: str, sdk: Any) -> Any:
    """Resolve an SDK model class from its fully-qualified dotted type path.

    Generated model classes are re-exported at the package's top level
    under a disambiguated alias whenever their bare class name collides
    across namespaces -- e.g. ``lifecycle.v4.config.BasicAuth`` is
    re-exported as ``sdk.LifecycleConfigBasicAuth`` because the same SDK
    package also defines ``common.v1.config.BasicAuth`` as
    ``sdk.CommonConfigBasicAuth``. Guessing the bare class name
    (``BasicAuth``) and looking it up on the top-level package therefore
    fails whenever a collision exists, silently falling through to the
    SDK's own (lossy) deserializer.

    Every generated model's *submodule* path always matches its dotted
    type path exactly (``<sdk>.models.<dotted_path>``, class name = the
    last segment), regardless of what alias -- if any -- it was given at
    the top level. Importing that submodule directly finds the class
    under its real name and sidesteps the collision entirely.

    Args:
        dotted_path: A dotted type path such as
            ``"lifecycle.v4.config.BasicAuth"`` (from a ``$objectType``
            value or a concrete ``swagger_types`` entry).
        sdk: The imported SDK package module.

    Returns:
        The resolved model class, or ``None`` if it cannot be found either
        via the exact submodule path or the top-level package namespace.
    """
    class_name = dotted_path.rsplit(".", 1)[-1]
    sdk_name = getattr(sdk, "__name__", None)
    submodule = None
    if sdk_name:
        try:
            submodule = importlib.import_module(f"{sdk_name}.models.{dotted_path}")
        except ImportError:
            submodule = None
    model_class = getattr(submodule, class_name, None) if submodule else None
    if model_class is not None:
        return model_class
    return getattr(sdk, class_name, None)


def _convert_field(value: Any, attr_type: Any, sdk: Any, client: Any) -> Any:
    """Recursively convert a raw value into the SDK type expected at this field.

    Every dict is resolved via our own model construction whenever a matching
    SDK class can be found -- either the concrete declared attr_type, or (for
    oneOf/discriminated-union fields) the class named by the dict's own
    $objectType. We never delegate a nested dict to the SDK's generic
    ApiClient.deserialize(), because that native code path mishandles oneOf
    dicts nested below the first level: it pops attributes off the dict in
    place while attempting to resolve them, and silently returns the (now
    partially stripped) dict on failure -- e.g. lifecycle's
    bondSettings.bondConfig losing its 'nics' field.
    """
    if isinstance(value, dict):
        obj_type = value.get("$objectType") or value.get("_object_type")
        if obj_type:
            dotted_path = obj_type
        elif (
            isinstance(attr_type, str)
            and "." in attr_type
            and not attr_type.startswith("OneOf")
        ):
            # Concrete (non-discriminated) declared type, e.g.
            # "lifecycle.v4.config.HciHypervisorDetails".  Generated model
            # types are always dotted; primitives and maps ("bool",
            # "dict(str, str)") never are, so the dot test keeps those on
            # the SDK's own deserializer.
            dotted_path = attr_type
        else:
            dotted_path = None
        model_class = _resolve_model_class(dotted_path, sdk) if dotted_path else None
        if model_class is not None and hasattr(model_class, "swagger_types"):
            return _build_model(model_class, value, sdk, client)
    if isinstance(value, list) and isinstance(attr_type, str):
        match = re.match(r"list\[(.*)\]", attr_type)
        if match:
            elem_type = match.group(1)
            return [_convert_field(item, elem_type, sdk, client) for item in value]
    return client.deserialize(klass=attr_type, data=value)


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
        r":type body:\s*:class:`~(ntnx_[a-z_]+_py_client)\.models\.([a-zA-Z0-9_.]+)`",
        doc,
        re.DOTALL,
    )

    if not match:
        return body_dict

    sdk_package = match.group(1)
    dotted_path = match.group(2)

    try:
        sdk = importlib.import_module(sdk_package)
        model_class = _resolve_model_class(dotted_path, sdk)

        if model_class is None:
            return body_dict

        if hasattr(model_class, "swagger_types") and hasattr(client, "deserialize"):
            return _build_model(model_class, body_dict, sdk, client)
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
