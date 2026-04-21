from __future__ import annotations

from pragma_sdk import set_permutation  # type: ignore[import-not-found]

from pragma.core.commits import validate_commit_shape


def test_valid_commit_passes() -> None:
    msg = (
        "feat(core): add thing\n"
        "\n"
        "WHY: The widget was broken.\n"
        "\n"
        "WHAT: Fixed it.\n"
        "\n"
        "WHERE: src/x.py.\n"
        "\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
    )
    with set_permutation("sdk_trace_emits_span"):
        assert validate_commit_shape(msg) == []


def test_missing_why_flagged() -> None:
    msg = "feat: x\n\nWHAT: y\nWHERE: z\n\nCo-Authored-By: a\n"
    errors = validate_commit_shape(msg)
    assert any(e.rule == "missing_why" for e in errors)


def test_missing_body_flagged() -> None:
    errors = validate_commit_shape("feat: short\n")
    assert any(e.rule == "missing_body" for e in errors)


def test_missing_co_authored_by_flagged() -> None:
    msg = "feat: x\n\nWHY: a\nWHAT: b\nWHERE: c\n"
    errors = validate_commit_shape(msg)
    assert any(e.rule == "missing_co_authored_by" for e in errors)


def test_subject_too_long_flagged() -> None:
    long_subj = (
        "feat(really-long-scope): "
        + "x" * 80
        + "\n\nWHY: y\nWHAT: z\nWHERE: q\n\nCo-Authored-By: a\n"
    )
    errors = validate_commit_shape(long_subj)
    assert any(e.rule == "subject_too_long" for e in errors)


def test_subject_exactly_72_chars_allowed() -> None:
    subj = "f" * 72
    msg = f"{subj}\n\nWHY: a\nWHAT: b\nWHERE: c\n\nCo-Authored-By: d\n"
    errors = validate_commit_shape(msg)
    assert all(e.rule != "subject_too_long" for e in errors)
