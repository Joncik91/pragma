"""Typed errors with a stable JSON payload shape for AI-consumable output.

Every CLI command catches PragmaError, prints `err.to_json()` to stdout,
and exits non-zero. The payload shape is part of Pragma's public contract
with Claude Code — see spec §2.3.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(kw_only=True)
class PragmaError(Exception):
    """Base class for all expected Pragma error paths."""

    code: str
    message: str
    remediation: str
    context: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_json(self) -> str:
        payload = {
            "error": self.code,
            "message": self.message,
            "remediation": self.remediation,
            "context": self.context,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(kw_only=True)
class ManifestSyntaxError(PragmaError):
    code: str = "manifest_syntax_error"


@dataclass(kw_only=True)
class ManifestSchemaError(PragmaError):
    code: str = "manifest_schema_error"


@dataclass(kw_only=True)
class ManifestHashMismatch(PragmaError):
    code: str = "manifest_hash_mismatch"


@dataclass(kw_only=True)
class ManifestNotFound(PragmaError):
    code: str = "manifest_not_found"


@dataclass(kw_only=True)
class LockNotFound(PragmaError):
    code: str = "lock_not_found"


@dataclass(kw_only=True)
class AlreadyInitialised(PragmaError):
    code: str = "already_initialised"


@dataclass(kw_only=True)
class DuplicateRequirementId(PragmaError):
    code: str = "duplicate_requirement_id"


@dataclass(kw_only=True)
class StateNotFound(PragmaError):
    code: str = "state_not_found"


@dataclass(kw_only=True)
class StateSchemaError(PragmaError):
    code: str = "state_schema_error"


@dataclass(kw_only=True)
class StateLocked(PragmaError):
    code: str = "state_locked"


@dataclass(kw_only=True)
class SliceNotFound(PragmaError):
    code: str = "slice_not_found"


@dataclass(kw_only=True)
class SliceAlreadyActive(PragmaError):
    code: str = "slice_already_active"


@dataclass(kw_only=True)
class SliceNotActive(PragmaError):
    code: str = "slice_not_active"


@dataclass(kw_only=True)
class GateWrongState(PragmaError):
    code: str = "gate_wrong_state"


@dataclass(kw_only=True)
class MilestoneDepUnshipped(PragmaError):
    code: str = "milestone_dep_unshipped"


@dataclass(kw_only=True)
class UnlockMissingTests(PragmaError):
    code: str = "unlock_missing_tests"


@dataclass(kw_only=True)
class UnlockTestPassing(PragmaError):
    code: str = "unlock_test_passing"


@dataclass(kw_only=True)
class CompleteTestsFailing(PragmaError):
    code: str = "complete_tests_failing"


@dataclass(kw_only=True)
class GateHashDrift(PragmaError):
    code: str = "gate_hash_drift"


@dataclass(kw_only=True)
class DisciplineViolationError(PragmaError):
    code: str = "discipline_violation"


@dataclass(kw_only=True)
class CommitShapeViolationError(PragmaError):
    code: str = "commit_shape_violation"


@dataclass(kw_only=True)
class IntegrityMismatchError(PragmaError):
    code: str = "integrity_mismatch"


@dataclass(kw_only=True)
class SettingsNotFoundError(PragmaError):
    code: str = "settings_not_found"


@dataclass(kw_only=True)
class HashNotFoundError(PragmaError):
    code: str = "hash_not_found"


@dataclass(kw_only=True)
class UnknownHookEventError(PragmaError):
    code: str = "unknown_hook_event"


@dataclass(kw_only=True)
class HookInputMissingError(PragmaError):
    code: str = "hook_input_missing"


@dataclass(kw_only=True)
class ReportNoSpans(PragmaError):
    code: str = "report_no_spans"


@dataclass(kw_only=True)
class ReportManifestDesync(PragmaError):
    code: str = "report_manifest_desync"


@dataclass(kw_only=True)
class NarrativeEmptyStage(PragmaError):
    code: str = "narrative_empty_stage"


@dataclass(kw_only=True)
class NarrativeNoActiveSlice(PragmaError):
    code: str = "narrative_no_active_slice"
