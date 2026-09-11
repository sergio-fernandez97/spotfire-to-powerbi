"""Spotfire column data types -> TMDL ``dataType`` and Power Query M type."""

from __future__ import annotations

# Spotfire DataType.name -> (TMDL dataType, M type expression)
_TYPES: dict[str, tuple[str, str]] = {
    "String": ("string", "type text"),
    "Integer": ("int64", "Int64.Type"),
    "LongInteger": ("int64", "Int64.Type"),
    "Real": ("double", "type number"),
    "SingleReal": ("double", "type number"),
    "Currency": ("decimal", "Currency.Type"),
    "Date": ("dateTime", "type date"),
    "DateTime": ("dateTime", "type datetime"),
    "Time": ("dateTime", "type time"),
    "TimeSpan": ("double", "type duration"),
    "Boolean": ("boolean", "type logical"),
    "Binary": ("binary", "type binary"),
}

NUMERIC_TMDL_TYPES = {"int64", "double", "decimal"}


def is_known(spotfire_type: str) -> bool:
    return spotfire_type in _TYPES


def tmdl_type(spotfire_type: str) -> str:
    return _TYPES.get(spotfire_type, ("string", "type text"))[0]


def m_type(spotfire_type: str) -> str:
    return _TYPES.get(spotfire_type, ("string", "type text"))[1]


def format_string(spotfire_type: str) -> str | None:
    if spotfire_type == "Date":
        return "Short Date"
    if spotfire_type == "Time":
        return "Long Time"
    return None
