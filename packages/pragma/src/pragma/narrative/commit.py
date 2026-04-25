from __future__ import annotations

from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pragma.core.errors import StateNotFound
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.models import Manifest, Requirement
from pragma.core.state import State, read_state

_TPL_DIR = Path(__file__).parent.parent / "templates"

# Files whose presence in a staged list is noise, not signal: compiled
# bytecode, cache dirs, machine-local gate/audit artifacts, etc. The
# goal is a commit message that describes *the change*, not *every
# byte that moved on disk*.
_NOISE_SUFFIXES = (".pyc", ".pyo")
_NOISE_DIR_PREFIXES = (
    "__pycache__/",
    ".pragma/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
)
_NOISE_EXACT = frozenset(
    {
        ".pragma/audit.jsonl",
        ".pragma/state.json",
        ".pragma/state.json.lock",
        ".pragma/claude-settings.hash",
        ".pragma/pytest-junit.xml",
    }
)


def _is_noise(path: str) -> bool:
    if path in _NOISE_EXACT:
        return True
    if path.endswith(_NOISE_SUFFIXES):
        return True
    return any(seg in path for seg in _NOISE_DIR_PREFIXES)


def _summarise_files(files: list[str], *, cap: int = 8) -> str:
    """Render the file list for the WHERE section.

    Short lists (≤ cap) go verbatim. Longer lists collapse to
    distinct top-level buckets with counts so the reader sees *shape*
    not *every path*. BUG-027 / REQ-025: top-level files (paths with
    no '/') are rendered without a trailing slash; only real
    directory prefixes get the "dir/" form.
    """
    if len(files) <= cap:
        return ", ".join(files)
    by_bucket: Counter[str] = Counter()
    for f in files:
        head = f.split("/", 1)[0] + "/" if "/" in f else f
        by_bucket[head] += 1
    parts = [f"{bucket} ({n})" for bucket, n in sorted(by_bucket.items())]
    return f"{len(files)} files across " + ", ".join(parts)


def _why_from_slice(reqs: list[Requirement], slice_title: str) -> str:
    """Derive a WHY that cites the slice and the REQs it ships.

    BUG-026 / REQ-037. Earlier output was "<slice>: N permutations
    declared" — mechanical, not motivating. New shape names the REQs
    by title so the reader sees what the slice is *about*, not just
    how many things it counts.
    """
    if not reqs:
        return f"{slice_title}." if slice_title else "Slice work."
    titles = [str(r.title).strip() for r in reqs if str(r.title).strip()]
    if len(titles) == 1:
        body = titles[0]
    elif len(titles) == 2:
        body = f"{titles[0]} and {titles[1]}"
    else:
        body = ", ".join(titles[:-1]) + f", and {titles[-1]}"
    head = f"{slice_title} — " if slice_title else ""
    return f"{head}{body}."


def _what_from_reqs(reqs: list[Requirement]) -> str:
    """Render a per-REQ WHAT summary instead of a bare file count.

    BUG-026 / REQ-037. The reader of a commit message wants the
    behaviour that landed, not "Touched N file(s)". Each REQ gets a
    line; permutations show their `expected` verdict so success vs
    reject is visible without opening the manifest.
    """
    if not reqs:
        return ""
    lines: list[str] = []
    for r in reqs:
        perms = [f"{p.id}={p.expected}" for p in r.permutations]
        perms_str = f" — perms: {', '.join(perms)}" if perms else ""
        lines.append(f"  - {r.id}: {r.title}{perms_str}")
    return "\n".join(lines)


def _slice_title(manifest: Manifest, slice_id: str) -> str:
    for m in manifest.milestones:
        for s in m.slices:
            if s.id == slice_id:
                return str(s.title)
    return ""


def _most_recent_shipped_slice(state: State | None) -> str | None:
    """Pick the slice with the latest completed_at among status=shipped.

    BUG-027 / REQ-025: `narrative commit` run right after
    `slice complete` would otherwise fall back to the "outside any
    active slice" copy, ignoring the shipped record that *just*
    landed in state.slices.
    """
    if state is None:
        return None
    best_id: str | None = None
    best_at = ""
    for sid, rec in state.slices.items():
        if rec.status != "shipped":
            continue
        at = rec.completed_at or ""
        if at >= best_at:
            best_at = at
            best_id = sid
    return best_id


def _resolve_slice_context(
    cwd: Path,
) -> tuple[str | None, list[Requirement], str, bool]:
    """Return (slice_id_for_narrative, reqs, slice_title, is_just_shipped)."""
    manifest = load_manifest(cwd / "pragma.yaml")
    try:
        state = read_state(cwd / ".pragma")
    except StateNotFound:
        state = None
    active_slice_id = state.active_slice if state else None
    if active_slice_id:
        reqs = list(slice_requirements(manifest, active_slice_id))
        return active_slice_id, reqs, _slice_title(manifest, active_slice_id), False
    recent = _most_recent_shipped_slice(state)
    if recent is not None:
        reqs = list(slice_requirements(manifest, recent))
        return recent, reqs, _slice_title(manifest, recent), True
    return None, [], "", False


def _pick_why(
    *,
    why_hint: str | None,
    active_slice_id: str | None,
    reqs: list[Requirement],
    slice_title: str,
    is_just_shipped: bool,
) -> str:
    if why_hint:
        return why_hint
    if active_slice_id and reqs:
        base = _why_from_slice(reqs, slice_title or active_slice_id)
        return f"Just shipped — {base}" if is_just_shipped else base
    if active_slice_id:
        verb = "Just shipped slice" if is_just_shipped else "Work on slice"
        return f"{verb} {active_slice_id}."
    # No active slice and no shipped history — honest fallback.
    return "Maintenance change outside any active slice."


def build_commit_message(
    *,
    cwd: Path,
    staged_files: list[str],
    subject_hint: str,
    why_hint: str | None,
) -> str:
    active_slice_id, reqs, slice_title, is_just_shipped = _resolve_slice_context(cwd)
    why = _pick_why(
        why_hint=why_hint,
        active_slice_id=active_slice_id,
        reqs=reqs,
        slice_title=slice_title,
        is_just_shipped=is_just_shipped,
    )
    filtered = [f for f in staged_files if not _is_noise(f)]
    where = _summarise_files(filtered) if filtered else "(no non-noise files staged)"
    what_body = _what_from_reqs(reqs)

    env = Environment(
        loader=FileSystemLoader(_TPL_DIR),
        autoescape=select_autoescape([]),
    )
    tpl = env.get_template("commit-message.tpl")
    return tpl.render(
        subject=subject_hint,
        why=why,
        files=filtered,
        where=where,
        file_count=len(filtered),
        what_body=what_body,
    )
