def intersection(first_obj: dict | list, second_obj: dict) -> bool:
    """Check if all key-value pairs in *second_obj* exist somewhere in *first_obj*.

    Used by ``Entity._filter_entities`` to match custom filters against entity
    payloads returned by the API.

    Args:
        first_obj: The entity payload (dict or list) to search within.
        second_obj: The filter dict whose keys/values must all be found.

    Returns:
        ``True`` when every entry in *second_obj* was matched and removed,
        ``False`` otherwise.
    """
    if isinstance(first_obj, dict):
        for key, value in first_obj.items():
            if key in second_obj and second_obj[key] == value:
                second_obj.pop(key)
            if isinstance(value, (dict, list)):
                intersection(value, second_obj)
        if not second_obj:
            return True
    elif isinstance(first_obj, list):
        for item in first_obj:
            intersection(item, second_obj)
    return False
