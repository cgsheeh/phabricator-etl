# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Unit tests for the DB-bound query helpers in `phabricator_etl.stats`.

Tests in this module use the `mock_sessions` fixture from `conftest.py`.
ORM-class placeholders are taken from `mock_sessions.db.<key>.<Class>`.
"""

from types import SimpleNamespace

from phabricator_etl.stats import get_user_email, get_user_name


def test_get_user_name_returns_username_when_found(mock_sessions):
    mock_sessions.users.set_rows(
        mock_sessions.db.user.User,
        [SimpleNamespace(phid="PHID-USER-abc", userName="alice")],
    )

    assert get_user_name("PHID-USER-abc", mock_sessions) == "alice", (
        "When a user row matches the PHID, `get_user_name` should return "
        "the `userName` column."
    )


def test_get_user_name_returns_none_when_no_user_matches(mock_sessions):
    mock_sessions.users.set_rows(
        mock_sessions.db.user.User,
        [SimpleNamespace(phid="PHID-USER-other", userName="bob")],
    )

    assert get_user_name("PHID-USER-missing", mock_sessions) is None, (
        "When no user row matches, `sessions.query(...).one()` raises "
        "`NoResultFound` and `get_user_name` swallows it as `None`."
    )


def test_get_user_email_returns_primary_address(mock_sessions):
    mock_sessions.users.set_rows(
        mock_sessions.db.user.UserEmail,
        [
            SimpleNamespace(
                userPHID="PHID-USER-abc",
                isPrimary=1,
                address="alice@example.com",
            ),
        ],
    )

    assert get_user_email("PHID-USER-abc", mock_sessions) == "alice@example.com", (
        "`get_user_email` should return the `address` of the primary email "
        "row for the given user PHID."
    )


def test_get_user_email_ignores_non_primary_addresses(mock_sessions):
    mock_sessions.users.set_rows(
        mock_sessions.db.user.UserEmail,
        [
            SimpleNamespace(
                userPHID="PHID-USER-abc",
                isPrimary=0,
                address="alice-secondary@example.com",
            ),
            SimpleNamespace(
                userPHID="PHID-USER-abc",
                isPrimary=1,
                address="alice-primary@example.com",
            ),
        ],
    )

    assert get_user_email("PHID-USER-abc", mock_sessions) == (
        "alice-primary@example.com"
    ), (
        "When a user has both primary and secondary email rows, "
        "`get_user_email` should select the primary one via the "
        "`isPrimary=1` filter."
    )


def test_get_user_email_returns_none_when_no_primary_email(mock_sessions):
    mock_sessions.users.set_rows(
        mock_sessions.db.user.UserEmail,
        [
            SimpleNamespace(
                userPHID="PHID-USER-abc",
                isPrimary=0,
                address="alice@example.com",
            ),
        ],
    )

    assert get_user_email("PHID-USER-abc", mock_sessions) is None, (
        "A user with no `isPrimary=1` email row should produce `None`, "
        "because `sessions.query(...).one()` raises `NoResultFound` and "
        "`get_user_email` swallows it."
    )


def test_get_user_email_returns_none_when_user_unknown(mock_sessions):
    # No rows registered at all.
    assert get_user_email("PHID-USER-missing", mock_sessions) is None, (
        "When no `user_email` rows exist at all, `get_user_email` should "
        "still return `None` rather than raise."
    )
