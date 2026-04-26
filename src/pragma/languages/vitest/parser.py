"""tree-sitter-typescript wrapper for Vitest test files."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser, Tree

# One Language instance per process. The TS parser handles .ts/.tsx/.mts/.cts.
# For .js/.jsx/.mjs/.cjs we use the same TS parser (TypeScript is a superset
# of JS for our detection purposes — we only walk syntax shapes, not types).
_LANG_TS = Language(tsts.language_typescript())
_LANG_TSX = Language(tsts.language_tsx())


def _pick_language(path: Path) -> Language:
    if path.suffix in {".tsx", ".jsx"}:
        return _LANG_TSX
    return _LANG_TS


def parse_file(path: Path) -> Tree:
    """Parse a Vitest test file into a tree-sitter Tree."""
    parser = Parser(_pick_language(path))
    return parser.parse(path.read_bytes())
