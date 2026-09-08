"""Normalising an enum-typed BAML field to a plain string."""

from __future__ import annotations

from enum import StrEnum

from pipeline.llm_text import enum_value


class _Colour(StrEnum):
    red = "red"


def test_enum_value_unwraps_an_enum():
    assert enum_value(_Colour.red) == "red"


def test_enum_value_passes_a_plain_string_through():
    """BAML returns plain strings for some fields and enum members for others,
    and which one has changed across regenerations."""
    assert enum_value("red") == "red"
