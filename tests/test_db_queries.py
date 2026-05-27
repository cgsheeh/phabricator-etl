# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Unit tests for the DB-bound query helpers in `phabricator_etl.stats`.

Tests in this module use the `mock_sessions` fixture from `conftest.py`.
ORM-class placeholders are taken from `mock_sessions.db.<key>.<Class>`.
"""

from types import SimpleNamespace

from phabricator_etl.stats import (
    diff_phid_to_id,
    get_bug_id,
    get_diff_id_for_changeset,
    get_revision_projects,
    get_target_repository,
    get_target_repository_uri,
    get_user_email,
    get_user_name,
)


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


# ---------------------------------------------------------------------------
# `get_target_repository` and `get_target_repository_uri`
# ---------------------------------------------------------------------------


def test_get_target_repository_returns_repo_row_when_found(mock_sessions):
    repo_row = SimpleNamespace(
        phid="PHID-REPO-firefox",
        name="firefox",
        details='{"default-branch": "main"}',
    )
    mock_sessions.repo.set_rows(mock_sessions.db.repo.Repository, [repo_row])

    assert get_target_repository("PHID-REPO-firefox", mock_sessions) is repo_row, (
        "`get_target_repository` should return the matching repository "
        "row object so that callers can read `.name`, `.details`, etc."
    )


def test_get_target_repository_returns_none_when_repo_unknown(mock_sessions):
    mock_sessions.repo.set_rows(
        mock_sessions.db.repo.Repository,
        [SimpleNamespace(phid="PHID-REPO-other", name="other", details=None)],
    )

    assert get_target_repository("PHID-REPO-missing", mock_sessions) is None, (
        "Looking up an unknown repository PHID should return `None` (via "
        "`.first()`) rather than raise."
    )


def test_get_target_repository_uri_returns_uri_attribute(mock_sessions):
    uri_row = SimpleNamespace(
        repositoryPHID="PHID-REPO-firefox",
        uri="https://hg.mozilla.org/mozilla-central",
    )
    mock_sessions.repo.set_rows(mock_sessions.db.repo.RepositoryURI, [uri_row])

    assert get_target_repository_uri("PHID-REPO-firefox", mock_sessions) == (
        "https://hg.mozilla.org/mozilla-central"
    ), (
        "`get_target_repository_uri` should return the `.uri` attribute "
        "of the matching `repository_uri` row, not the row itself."
    )


def test_get_target_repository_uri_returns_none_when_no_uri(mock_sessions):
    # No URI rows registered.
    assert get_target_repository_uri("PHID-REPO-firefox", mock_sessions) is None, (
        "When the repository has no `repository_uri` row, "
        "`get_target_repository_uri` should return `None` instead of "
        "dereferencing `.uri` on `None`."
    )


# ---------------------------------------------------------------------------
# `diff_phid_to_id` and `get_diff_id_for_changeset`
# ---------------------------------------------------------------------------


def test_diff_phid_to_id_returns_none_for_none_input(mock_sessions):
    assert diff_phid_to_id(None, mock_sessions) is None, (
        "`diff_phid_to_id(None, ...)` short-circuits to `None` without "
        "touching the database, because review rows often have null "
        "last-action/last-comment diff PHIDs."
    )


def test_diff_phid_to_id_returns_diff_id_for_known_phid(mock_sessions):
    mock_sessions.diff.set_rows(
        mock_sessions.db.diff.Differential,
        [SimpleNamespace(phid="PHID-DIFF-xyz", id=4242)],
    )

    assert diff_phid_to_id("PHID-DIFF-xyz", mock_sessions) == 4242, (
        "Given a known diff PHID, `diff_phid_to_id` should return the "
        "numeric `id` of the matching `differential_diff` row."
    )


def test_get_diff_id_for_changeset_returns_none_for_none_input(mock_sessions):
    assert get_diff_id_for_changeset(None, mock_sessions) is None, (
        "`get_diff_id_for_changeset(None, ...)` short-circuits to `None`. "
        "Revision-level comments have `changesetID is None`, so this "
        "guard is what keeps `get_comments` from looking up a nonexistent "
        "changeset."
    )


def test_get_diff_id_for_changeset_returns_diff_id_for_known_changeset(mock_sessions):
    mock_sessions.diff.set_rows(
        mock_sessions.db.diff.Changeset,
        [SimpleNamespace(id=77, diffID=88)],
    )

    assert get_diff_id_for_changeset(77, mock_sessions) == 88, (
        "Given a known changeset ID, `get_diff_id_for_changeset` should "
        "return the `diffID` column of the matching "
        "`differential_changeset` row."
    )


# ---------------------------------------------------------------------------
# `get_bug_id`
# ---------------------------------------------------------------------------


def build_bug_id_query(mock_sessions, rows):
    """Mirror the production setup for `bug_id_query` (with the filter
    chained on) using the mock session. Tests are responsible for
    populating the row set so it represents the post-filter result.
    """
    custom_field_storage = mock_sessions.db.diff.CustomFieldStorage
    mock_sessions.diff.set_rows(custom_field_storage, rows)
    return mock_sessions.diff.query(custom_field_storage).filter(
        custom_field_storage.fieldIndex == b"zdMFYM6423ua"
    )


def test_get_bug_id_returns_field_value_when_present(mock_sessions):
    revision = SimpleNamespace(phid="PHID-DREV-abc")
    bug_id_query = build_bug_id_query(
        mock_sessions,
        [SimpleNamespace(objectPHID="PHID-DREV-abc", fieldValue="1234567")],
    )

    assert get_bug_id(revision, mock_sessions, bug_id_query) == "1234567", (
        "When a `differential_customfieldstorage` row exists for the "
        "revision PHID, `get_bug_id` should return its `fieldValue`."
    )


def test_get_bug_id_returns_none_when_no_row(mock_sessions):
    revision = SimpleNamespace(phid="PHID-DREV-abc")
    bug_id_query = build_bug_id_query(mock_sessions, [])

    assert get_bug_id(revision, mock_sessions, bug_id_query) is None, (
        "A revision with no bug-id custom-field row should produce "
        "`None` rather than raise (revisions without a Bugzilla bug are "
        "expected)."
    )


def test_get_bug_id_returns_none_for_empty_field_value(mock_sessions):
    revision = SimpleNamespace(phid="PHID-DREV-abc")
    bug_id_query = build_bug_id_query(
        mock_sessions,
        [SimpleNamespace(objectPHID="PHID-DREV-abc", fieldValue="")],
    )

    assert get_bug_id(revision, mock_sessions, bug_id_query) is None, (
        "An empty-string `fieldValue` should normalize to `None` via the "
        "`fieldValue or None` fall-through, so downstream code treats it "
        "the same as a missing bug-id row."
    )


# ---------------------------------------------------------------------------
# `get_revision_projects`
# ---------------------------------------------------------------------------


def test_get_revision_projects_returns_empty_list_when_no_edges(mock_sessions):
    revision = SimpleNamespace(phid="PHID-DREV-abc")
    projects_query = mock_sessions.projects.query(mock_sessions.db.project.Project)

    assert get_revision_projects(revision, mock_sessions, projects_query) == [], (
        "A revision with no `OBJECT_HAS_PROJECT` edges should produce an "
        "empty project-tag list."
    )


def test_get_revision_projects_returns_project_slugs(mock_sessions):
    revision = SimpleNamespace(phid="PHID-DREV-abc")
    # Register only the edges that pass the (src, type) filter.
    mock_sessions.diff.set_rows(
        mock_sessions.db.diff.Edges,
        [
            SimpleNamespace(src="PHID-DREV-abc", dst="PHID-PROJ-fenix"),
            SimpleNamespace(src="PHID-DREV-abc", dst="PHID-PROJ-conduit"),
        ],
    )
    # Register the matching projects in `set` order. The function uses a
    # set of project PHIDs internally so the output order is not
    # guaranteed; sort before comparing.
    mock_sessions.projects.set_rows(
        mock_sessions.db.project.Project,
        [
            SimpleNamespace(phid="PHID-PROJ-fenix", primarySlug="fenix"),
            SimpleNamespace(phid="PHID-PROJ-conduit", primarySlug="conduit"),
        ],
    )
    projects_query = mock_sessions.projects.query(mock_sessions.db.project.Project)

    result = get_revision_projects(revision, mock_sessions, projects_query)

    assert sorted(result) == ["conduit", "fenix"], (
        "Two `OBJECT_HAS_PROJECT` edges should resolve to the two "
        "matching projects' `primarySlug` values."
    )


def test_get_revision_projects_dedups_duplicate_edges(mock_sessions):
    revision = SimpleNamespace(phid="PHID-DREV-abc")
    # Two edges pointing at the same project; the function dedups via
    # `{edge.dst for edge in edges}`.
    mock_sessions.diff.set_rows(
        mock_sessions.db.diff.Edges,
        [
            SimpleNamespace(src="PHID-DREV-abc", dst="PHID-PROJ-fenix"),
            SimpleNamespace(src="PHID-DREV-abc", dst="PHID-PROJ-fenix"),
        ],
    )
    mock_sessions.projects.set_rows(
        mock_sessions.db.project.Project,
        [SimpleNamespace(phid="PHID-PROJ-fenix", primarySlug="fenix")],
    )
    projects_query = mock_sessions.projects.query(mock_sessions.db.project.Project)

    assert get_revision_projects(revision, mock_sessions, projects_query) == [
        "fenix"
    ], (
        "Duplicate edges to the same project should produce the slug "
        "only once, because the function collects edge `dst` values "
        "into a set before looking them up."
    )
