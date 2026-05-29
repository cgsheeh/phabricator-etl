# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Shared pytest fixtures for the phabricator-etl test suite.

Test conventions
----------------
- Build fake DB rows with `SimpleNamespace(...)`; any keyword argument
  becomes an attribute on the row.
- Register rows on a session with `mock_sessions.<users|projects|repo|diff>
  .set_rows(cls, rows)`. The `cls` argument is the ORM-class placeholder
  the code under test will pass to `Session.query()`, taken from
  `mock_sessions.db.<key>.<Class>`.
- `MockQuery.filter` is a deliberate no-op: tests must pre-arrange the
  row set so that the query produces the expected result. `filter_by`
  is implemented for real, since it operates on plain attribute names.
- `mock_sessions.db` is a stub `Db` whose ORM-class attributes are
  stable `MagicMock` placeholders. The placeholders are hashable and
  comparable, which is enough for `MockQuery` to key its row store on
  them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Iterable, Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import MultipleResultsFound, NoResultFound

_MISSING = object()


class MockQuery:
    """Mock of a sqlalchemy `Query`.

    Only the subset of methods exercised by the ETL is implemented. `filter`
    is a no-op so that tests can ignore the precise comparator expressions
    used by the code under test; arrange the rows to be the post-filter set
    you expect.
    """

    def __init__(self, rows: Iterable[Any]):
        self._rows = list(rows)

    def filter_by(self, **kwargs) -> "MockQuery":
        def matches(candidate: Any) -> bool:
            for attr_name, expected in kwargs.items():
                if getattr(candidate, attr_name, _MISSING) != expected:
                    return False
            return True

        return MockQuery([row for row in self._rows if matches(row)])

    def filter(self, *args) -> "MockQuery":
        # See module docstring: tests pre-arrange rows, the filter expression itself is ignored.
        return self

    def order_by(self, *args) -> "MockQuery":
        return self

    def with_entities(self, *cols) -> "MockQuery":
        raise NotImplementedError(
            "MockQuery.with_entities is not implemented; "
            "add support when a test requires it."
        )

    def first(self) -> Optional[Any]:
        return self._rows[0] if self._rows else None

    def one(self) -> Any:
        if not self._rows:
            raise NoResultFound("No row was found for `one()`.")
        if len(self._rows) > 1:
            raise MultipleResultsFound("Multiple rows were found for `one()`.")
        return self._rows[0]

    def one_or_none(self) -> Optional[Any]:
        if not self._rows:
            return None
        if len(self._rows) > 1:
            raise MultipleResultsFound("Multiple rows were found for `one_or_none()`.")
        return self._rows[0]

    def all(self) -> list:
        return list(self._rows)

    def count(self) -> int:
        return len(self._rows)

    def __iter__(self):
        return iter(self._rows)


class MockSession:
    """Mock of a sqlalchemy `Session`.

    Use `set_rows(cls, rows)` to register the rows that should be returned
    when the code under test calls `Session.query(cls)`.
    """

    def __init__(self):
        self._rows_by_class: dict = {}

    def set_rows(self, cls: Any, rows: Iterable[Any]) -> None:
        self._rows_by_class[cls] = list(rows)

    def query(self, cls: Any) -> MockQuery:
        return MockQuery(self._rows_by_class.get(cls, []))


def stub_db() -> SimpleNamespace:
    """Build a stub `Db` whose ORM-class attributes are `MagicMock` placeholders.

    Each call returns a fresh stub so tests are independent.
    """
    return SimpleNamespace(
        user=SimpleNamespace(
            User=MagicMock(name="user.User"),
            UserEmail=MagicMock(name="user.UserEmail"),
        ),
        project=SimpleNamespace(
            Project=MagicMock(name="project.Project"),
            Edges=MagicMock(name="project.Edges"),
        ),
        repo=SimpleNamespace(
            Repository=MagicMock(name="repo.Repository"),
            RepositoryURI=MagicMock(name="repo.RepositoryURI"),
        ),
        diff=SimpleNamespace(
            Revision=MagicMock(name="diff.Revision"),
            Differential=MagicMock(name="diff.Differential"),
            Changeset=MagicMock(name="diff.Changeset"),
            Transaction=MagicMock(name="diff.Transaction"),
            TransactionComment=MagicMock(name="diff.TransactionComment"),
            Reviewer=MagicMock(name="diff.Reviewer"),
            Edges=MagicMock(name="diff.Edges"),
            CustomFieldStorage=MagicMock(name="diff.CustomFieldStorage"),
        ),
    )


@dataclass
class MockSessions:
    """Duck-types as `phabricator_etl.stats.Sessions` without touching MySQL."""

    users: MockSession = field(default_factory=MockSession)
    projects: MockSession = field(default_factory=MockSession)
    repo: MockSession = field(default_factory=MockSession)
    diff: MockSession = field(default_factory=MockSession)
    db: SimpleNamespace = field(default_factory=stub_db)


@pytest.fixture
def mock_sessions() -> MockSessions:
    """Return a fresh `MockSessions` with empty per-session row stores."""
    return MockSessions()
