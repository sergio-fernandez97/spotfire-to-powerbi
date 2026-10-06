"""Spotfire column data types -> TMDL ``dataType`` and Power Query M type."""

from __future__ import annotations

import re

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


# Database integers (scale 0) reach Spotfire as Currency/Real; Power BI should see whole numbers.
_WHOLE = re.compile(r"^(?:DECIMAL|NUMERIC|NUMBER)\(\d+,0\)$|^(?:BIGINT|INT|INTEGER|SMALLINT|TINYINT|BYTEINT)$",
                    re.IGNORECASE)


def _pair(spotfire_type: str, external_type: str | None) -> tuple[str, str]:
    if external_type and _WHOLE.match(external_type.replace(" ", "")) and spotfire_type in (
            "Currency", "Real", "Integer", "LongInteger"):
        return _TYPES["LongInteger"]
    return _TYPES.get(spotfire_type, ("string", "type text"))


def tmdl_type(spotfire_type: str, external_type: str | None = None) -> str:
    return _pair(spotfire_type, external_type)[0]


def m_type(spotfire_type: str, external_type: str | None = None) -> str:
    return _pair(spotfire_type, external_type)[1]


def format_string(spotfire_type: str) -> str | None:
    if spotfire_type == "Date":
        return "Short Date"
    if spotfire_type == "Time":
        return "Long Time"
    return None
