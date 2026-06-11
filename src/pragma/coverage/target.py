"""Resolve `(target_module, target_symbol)` -> `(file_path, line_range)`.

Per-language: Python resolves the module's `.py` file by statically
walking `sys.path` directories, then `ast.parse`-s the source to locate
the symbol's line range — it never imports or executes the target.
Vitest delegates to a tree-sitter parse of the test file's import
statements. Both return None when the production target doesn't exist on
disk (or the symbol can't be found) — tier 2 then skips the test silently.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _resolve_module_file(target_module: str) -> Path | None:
    """Find the `.py` file backing `target_module` by walking sys.path dirs.

    Never imports. Resolves a dotted name (`pkg.sub.mod`) to either
    `<dir>/pkg/sub/mod.py` or the package's `<dir>/pkg/sub/mod/__init__.py`.
    Returns the first existing candidate, or None.
    """
    rel = Path(*target_module.split("."))
    for entry in sys.path:
        # An empty string means "current working directory"; "" / x == x.
        base = Path(entry) if entry else Path()
        module_file = base / rel.with_suffix(".py")
        if module_file.is_file():
            return module_file.resolve()
        package_init = base / rel / "__init__.py"
        if package_init.is_file():
            return package_init.resolve()
    return None


def _symbol_lines_from_source(source: str, target_symbol: str) -> range | None:
    """Return the 1-indexed inclusive line range of `target_symbol` in `source`.

    Matches a top-level function, async function, class, or name binding
    (assignment / annotated assignment). Returns None when the symbol isn't
    defined at module level or the source can't be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == target_symbol
        ):
            return _node_range(node)
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == target_symbol:
                    return _node_range(node)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == target_symbol
        ):
            return _node_range(node)
    return None


def _node_range(node: ast.AST) -> range:
    """1-indexed inclusive line range for an AST node (lineno..end_lineno)."""
    start = node.lineno
    end = getattr(node, "end_lineno", None) or start
    return range(start, end + 1)


def production_lines_python(
    target_module: str | None, target_symbol: str | None
) -> tuple[Path, range] | None:
    """Map a Python (module, symbol) pair to its (file, line range).

    Resolves the module file statically by walking `sys.path` and reading
    the `.py` source — the inferred module name is treated as untrusted and
    is never imported or executed. Returns None when the file can't be
    located, the source can't be parsed, or the symbol isn't defined at
    module level; tier 2 then emits no verdict.
    """
    if target_module is None or target_symbol is None:
        return None

    module_file = _resolve_module_file(target_module)
    if module_file is None:
        return None

    try:
        source = module_file.read_text(encoding="utf-8")
    except OSError:
        return None

    line_range = _symbol_lines_from_source(source, target_symbol)
    if line_range is None:
        return None

    return (module_file, line_range)


# ---------------------------------------------------------------------------
# Vitest helpers
# ---------------------------------------------------------------------------


def _walk_nodes(node):
    """Depth-first walk of all tree-sitter nodes."""
    yield node
    for child in node.children:
        yield from _walk_nodes(child)


def _collect_relative_imports(root) -> list[tuple[str, str, str]]:
    """Return list of (module_path, kind, symbol) for relative imports.

    kind is one of: 'named', 'default', 'namespace'.
    Only relative imports (starting with '.' or '/') are returned.
    Multiple named imports from the same module produce one entry each.
    """
    results: list[tuple[str, str, str]] = []
    for node in _walk_nodes(root):
        if node.type != "import_statement":
            continue

        # Extract the module path from the `from` clause (source field)
        source_node = node.child_by_field_name("source")
        if source_node is None:
            continue

        # Unwrap string node — text includes quotes
        raw = source_node.text.decode("utf-8").strip("'\"`")
        if not raw.startswith(".") and not raw.startswith("/"):
            # Not a relative import — skip npm packages
            continue

        # Walk the import clause
        for child in node.children:
            if child.type == "import_clause":
                _parse_import_clause(raw, child, results)

    return results


def _parse_import_clause(
    module_path: str,
    clause_node,
    results: list[tuple[str, str, str]],
) -> None:
    """Populate results from a single import_clause node."""
    for child in clause_node.children:
        if child.type == "identifier":
            # default import: `import Foo from "..."`
            results.append((module_path, "default", child.text.decode("utf-8")))

        elif child.type == "named_imports":
            # named imports: `import { A, B } from "..."`
            for spec in child.children:
                if spec.type == "import_specifier":
                    # The alias (local name) is the last identifier, or the only one.
                    # For `import { X as Y }`, we want Y (local name).
                    names = [c for c in spec.children if c.type == "identifier"]
                    if names:
                        local_name = names[-1].text.decode("utf-8")
                        results.append((module_path, "named", local_name))

        elif child.type == "namespace_import":
            # namespace import: `import * as M from "..."`
            # The alias is the identifier after `as`.
            idents = [c for c in child.children if c.type == "identifier"]
            if idents:
                alias = idents[-1].text.decode("utf-8")
                results.append((module_path, "namespace", alias))


def _body_calls_named(root, name: str) -> bool:
    """True if any call_expression in the tree calls bare identifier `name`."""
    for node in _walk_nodes(root):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is not None and func.type == "identifier" and func.text.decode("utf-8") == name:
            return True
    return False


def _body_calls_namespace_member(root, alias: str) -> str | None:
    """Return first attribute X from `alias.X(...)` calls, else None."""
    for node in _walk_nodes(root):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        obj = func.child_by_field_name("object")
        prop = func.child_by_field_name("property")
        if obj is None or prop is None:
            continue
        if obj.text.decode("utf-8") == alias:
            return prop.text.decode("utf-8")
    return None


def _resolve_path(base: Path, module_path: str) -> Path | None:
    """Resolve a relative module path to an existing file on disk.

    Tries .ts, .tsx, .js, .jsx extensions.
    """
    raw = (base / module_path).resolve()
    # If the import already has an extension, check it directly first.
    if raw.suffix in {".ts", ".tsx", ".js", ".jsx"} and raw.exists():
        return raw
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        candidate = raw.with_suffix(ext)
        if candidate.exists():
            return candidate
    # Try as-is (no extension, but happens to be a directory with index — skip for now)
    return None


def _vitest_symbol_lines(target_file: Path, symbol: str) -> range | None:
    """Parse `target_file` with tree-sitter and return the line range of `symbol`.

    Handles:
    - ``function_declaration`` with a matching name identifier.
    - ``lexical_declaration`` containing a ``variable_declarator`` whose name
      matches and whose value is an ``arrow_function`` or ``function_expression``.
    - ``export_statement`` wrapping any of the above.
    - ``class_declaration`` with a matching name.

    Lines are 1-indexed (matching the V8 coverage format).
    Returns None when the symbol can't be found or on any parse error.
    """
    if not target_file.exists():
        return None

    try:
        from pragma.languages.vitest.parser import parse_file  # noqa: PLC0415

        tree = parse_file(target_file)
    except Exception:
        return None

    root = tree.root_node

    def _name_of(node) -> str | None:
        """Return the text of a node's 'name' field, if present."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        return name_node.text.decode("utf-8")

    def _node_range(node) -> range:
        """Return 1-indexed inclusive range for a node."""
        # tree-sitter rows are 0-indexed; add 1.
        start = node.start_point[0] + 1
        end = node.end_point[0] + 1
        return range(start, end + 1)

    def _check_lexical_declarator(lex_node) -> range | None:
        """Check a lexical_declaration node for a matching arrow/function binding."""
        for child in lex_node.children:
            if child.type != "variable_declarator":
                continue
            decl_name = _name_of(child)
            if decl_name != symbol:
                continue
            value = child.child_by_field_name("value")
            if value is not None and value.type in {"arrow_function", "function_expression"}:
                return _node_range(lex_node)
        return None

    def _check_node(node) -> range | None:
        """Check a top-level (or export-wrapped) node for symbol match."""
        if node.type == "function_declaration" or node.type == "class_declaration":
            if _name_of(node) == symbol:
                return _node_range(node)
        elif node.type in {"lexical_declaration", "variable_declaration"}:
            return _check_lexical_declarator(node)
        elif node.type == "export_statement":
            # export_statement wraps the actual declaration
            for child in node.children:
                result = _check_node(child)
                if result is not None:
                    return result
        return None

    for stmt in root.children:
        found = _check_node(stmt)
        if found is not None:
            return found

    return None


def production_target_vitest(test_path: Path) -> tuple[Path, str] | None:
    """Map a Vitest test file to its (production_file, symbol) target.

    Parses the test file's `import` statements via tree-sitter, resolves
    the relative path, and returns the first non-vitest import that the
    test body actually calls. Returns None when no production target can
    be inferred.
    """
    if not test_path.exists():
        return None

    try:
        # We need the tree-sitter parser; import here to avoid circular deps
        # and to make import errors visible at call time rather than module load.
        from pragma.languages.vitest.parser import parse_file
    except Exception:
        return None

    try:
        tree = parse_file(test_path)
    except Exception:
        return None

    root = tree.root_node
    try:
        relative_imports = _collect_relative_imports(root)
    except Exception:
        return None

    for module_path, kind, sym in relative_imports:
        try:
            if kind in {"named", "default"}:
                if not _body_calls_named(root, sym):
                    continue
                symbol_name = sym
            elif kind == "namespace":
                inner = _body_calls_namespace_member(root, sym)
                if inner is None:
                    continue
                symbol_name = inner
            else:
                continue

            prod_file = _resolve_path(test_path.parent, module_path)
            if prod_file is None:
                continue

            return (prod_file, symbol_name)
        except Exception:
            continue

    return None
