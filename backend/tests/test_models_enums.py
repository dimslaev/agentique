"""Guards the Python enums against the DB enums the migrations declare.

A label added to a Postgres enum by a migration but not to its StrEnum here
loads fine into the DB and then blows up on read: SQLAlchemy raises
``LookupError: '<label>' is not among the defined enum values`` for every row
carrying it — and ``_active_publisher_links`` selects *all* active publishers,
so one such row takes the whole pipeline run down.
"""
from __future__ import annotations

import inspect
import re
from enum import StrEnum
from pathlib import Path

from app import models

VERSIONS = Path(__file__).parent.parent / "app" / "alembic" / "versions"

# SQLModel names a Postgres enum type after the lowercased class name.
ENUM_MODELS = {
    name.lower(): cls
    for name, cls in inspect.getmembers(models, inspect.isclass)
    if issubclass(cls, StrEnum) and cls is not StrEnum
}

ADD_VALUE = re.compile(
    r"ALTER TYPE (\w+) ADD VALUE (?:IF NOT EXISTS )?'([^']+)'", re.IGNORECASE
)


def test_migration_enum_labels_exist_in_python():
    added = [
        (m.group(1).lower(), m.group(2))
        for path in VERSIONS.glob("*.py")
        for m in ADD_VALUE.finditer(path.read_text())
    ]
    assert added, "expected at least one ADD VALUE migration to guard"

    for type_name, label in added:
        model = ENUM_MODELS.get(type_name)
        assert model is not None, f"no Python enum mapped for {type_name!r}"
        assert label in {e.value for e in model}, (
            f"migration adds {label!r} to {type_name} but {model.__name__} "
            f"has no such member — rows using it will fail to load"
        )
