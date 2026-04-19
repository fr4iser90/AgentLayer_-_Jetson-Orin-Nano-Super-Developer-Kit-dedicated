"""Tests for ported PIDEA workflow helpers (git templates, validation)."""

import pytest

from apps.backend.integrations.pidea.workflow.git_ops import (
    resolve_branch_name_template,
    sanitize_task_title_for_branch,
    validate_branch_name,
)


def test_sanitize_task_title() -> None:
    assert sanitize_task_title_for_branch("Foo Bar!!!") == "foo-bar"


def test_resolve_template() -> None:
    assert resolve_branch_name_template("x-${task.id}-y", task_id="abc-1") == "x-abc-1-y"
    assert "feat-" in resolve_branch_name_template(
        "feat-{{task.title}}",
        task_title="Hello World",
    )


def test_validate_branch_ok() -> None:
    validate_branch_name("feature/foo-bar")


def test_validate_branch_rejects() -> None:
    with pytest.raises(ValueError):
        validate_branch_name("bad;rm")
    with pytest.raises(ValueError):
        validate_branch_name("a..b")
