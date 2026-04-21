from __future__ import annotations

import re
from dataclasses import dataclass

from pragma_sdk import trace

_SUBJECT_MAX = 72


@dataclass(frozen=True)
class CommitShapeError:
    rule: str
    remediation: str


@trace("REQ-005")
def validate_commit_shape(message: str) -> list[CommitShapeError]:
    errors: list[CommitShapeError] = []
    if not message.strip():
        errors.append(
            CommitShapeError(
                rule="empty_message",
                remediation="Commit message must not be empty.",
            )
        )
        return errors
    subject = message.split("\n", 1)[0]
    if len(subject) > _SUBJECT_MAX:
        errors.append(
            CommitShapeError(
                rule="subject_too_long",
                remediation=f"Shorten the subject line to at most {_SUBJECT_MAX} characters.",
            )
        )
    if "\n\n" not in message:
        errors.append(
            CommitShapeError(
                rule="missing_body",
                remediation="Add a body separated from the subject by a blank line.",
            )
        )
    else:
        body = message.split("\n\n", 1)[1]
        if not re.search(r"^WHY:", body, re.MULTILINE):
            errors.append(
                CommitShapeError(
                    rule="missing_why",
                    remediation="Add a WHY: line to the body explaining the motivation.",
                )
            )
    if not re.search(r"^Co-Authored-By:", message, re.MULTILINE | re.IGNORECASE):
        errors.append(
            CommitShapeError(
                rule="missing_co_authored_by",
                remediation="Add a Co-Authored-By: trailer for AI-assisted commits.",
            )
        )
    return errors
