from __future__ import annotations

from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pragma.core.errors import StateNotFound
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.models import Requirement
from pragma.core.state import read_state

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
    top-level directories with counts so the reader sees *shape* not
    *every path*.
    """
    if len(files) <= cap:
        return ", ".join(files)
    by_dir: Counter[str] = Counter()
    for f in files:
        head = f.split("/", 1)[0] if "/" in f else f
        by_dir[head] += 1
    parts = [f"{d}/ ({n})" for d, n in sorted(by_dir.items())]
    return f"{len(files)} files across " + ", ".join(parts)


def _why_from_slice(reqs: list[Requirement], slice_title: str) -> str:
    """Derive a WHY that cites slice + permutation verdict counts."""
    total = sum(len(r.permutations) for r in reqs)
    success = sum(1 for r in reqs for p in r.permutations if p.expected == "success")
    reject = total - success
    perm_phrase = (
        f"{total} permutation"
        + ("s" if total != 1 else "")
        + (f" ({success} success, {reject} reject)" if reject else "")
    )
    return f"{slice_title}: {perm_phrase} declared."


def _resolve_slice_context(cwd: Path):  # type: ignore[no-untyped-def]
    """Return (active_slice_id, reqs, slice_title) for the current state."""
    manifest = load_manifest(cwd / "pragma.yaml")
    try:
        state = read_state(cwd / ".pragma")
    except StateNotFound:
        state = None
    active_slice_id = state.active_slice if state else None
    if not active_slice_id:
        return None, [], ""
    reqs = list(slice_requirements(manifest, active_slice_id))
    slice_title = ""
    for m in manifest.milestones:
        for s in m.slices:
            if s.id == active_slice_id:
                slice_title = s.title
                break
        if slice_title:
            break
    return active_slice_id, reqs, slice_title


def _pick_why(
    *,
    why_hint: str | None,
    active_slice_id: str | None,
    reqs: list[Requirement],
    slice_title: str,
) -> str:
    if why_hint:
        return why_hint
    if active_slice_id and reqs:
        return _why_from_slice(reqs, slice_title or active_slice_id)
    if active_slice_id:
        return f"Work on slice {active_slice_id}."
    # No active slice — honest about the context, not a placeholder.
    return "Maintenance change outside any active slice."


def build_commit_message(
    *,
    cwd: Path,
    staged_files: list[str],
    subject_hint: str,
    why_hint: str | None,
) -> str:
    active_slice_id, reqs, slice_title = _resolve_slice_context(cwd)
    why = _pick_why(
        why_hint=why_hint,
        active_slice_id=active_slice_id,
        reqs=reqs,
        slice_title=slice_title,
    )
    filtered = [f for f in staged_files if not _is_noise(f)]
    where = _summarise_files(filtered) if filtered else "(no non-noise files staged)"

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
    )
