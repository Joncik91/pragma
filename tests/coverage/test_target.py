"""Tests for production_lines_python and production_target_vitest resolvers.

`production_lines_python` resolves the target module's file by statically
walking ``sys.path`` directories and ``ast.parse``-ing the ``.py`` source —
it never imports or executes the module. These tests pin that static
resolution behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pragma.coverage.target import (
    _vitest_symbol_lines,
    production_lines_python,
    production_target_vitest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_to_sys_path(path: Path):
    """Context manager that temporarily adds a dir to sys.path.

    No module import happens, so there are no ``sys.modules`` entries to
    evict — the resolver only reads files off ``sys.path`` directories.
    """
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        sys.path.insert(0, str(path))
        try:
            yield
        finally:
            sys.path.remove(str(path))

    return _ctx()


# ---------------------------------------------------------------------------
# Python target — positive cases
# ---------------------------------------------------------------------------


def test_production_lines_python_function(tmp_path: Path) -> None:
    """A simple function → returns (file, range) covering its lines."""
    module_file = tmp_path / "foo.py"
    module_file.write_text("def reserve(x, y):\n    return x + y\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("foo", "reserve")
    assert result is not None
    file_path, line_range = result
    assert file_path == module_file.resolve()
    # reserve starts at line 1, ends at line 2
    assert 1 in line_range
    assert 2 in line_range


def test_production_lines_python_class(tmp_path: Path) -> None:
    """A class definition → returns (file, range) covering the class."""
    module_file = tmp_path / "mymod.py"
    module_file.write_text(
        "class MyClass:\n"
        "    def __init__(self):\n"
        "        self.x = 1\n"
        "\n"
        "    def method(self):\n"
        "        return self.x\n"
    )
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("mymod", "MyClass")
    assert result is not None
    file_path, line_range = result
    assert file_path == module_file.resolve()
    assert 1 in line_range
    assert 3 in line_range


def test_production_lines_python_multiline_function(tmp_path: Path) -> None:
    """Range covers all lines of the function, not just the def line."""
    module_file = tmp_path / "bar.py"
    module_file.write_text(
        "# preamble\n"  # line 1
        "\n"  # line 2
        "def calc(a, b, c):\n"  # line 3
        "    x = a + b\n"  # line 4
        "    y = x * c\n"  # line 5
        "    return y\n"  # line 6
    )
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("bar", "calc")
    assert result is not None
    _, line_range = result
    assert 3 in line_range
    assert 6 in line_range


# ---------------------------------------------------------------------------
# Python target — negative cases
# ---------------------------------------------------------------------------


def test_production_lines_python_none_module() -> None:
    assert production_lines_python(None, "fn") is None


def test_production_lines_python_none_symbol() -> None:
    assert production_lines_python("os", None) is None


def test_production_lines_python_both_none() -> None:
    assert production_lines_python(None, None) is None


def test_production_lines_python_missing_module() -> None:
    """No `.py` for the module on any sys.path dir → None (no import attempted)."""
    assert production_lines_python("definitely_not_a_module_42", "fn") is None


def test_production_lines_python_missing_symbol(tmp_path: Path) -> None:
    """Module file exists, symbol not defined in its source → None."""
    (tmp_path / "present_mod.py").write_text("x = 1\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("present_mod", "nonexistent_symbol_xyz")
    assert result is None


def test_production_lines_python_builtin_no_source() -> None:
    """builtins is a C module with no `.py` on sys.path → None."""
    result = production_lines_python("builtins", "len")
    assert result is None


def test_production_lines_python_does_not_execute_module(tmp_path: Path) -> None:
    """Module-level code that would raise on import is NEVER executed.

    The resolver statically parses the source, so a module whose top level
    raises still yields the symbol's line range instead of returning None.
    """
    mod = tmp_path / "side_effect_mod.py"
    mod.write_text(
        "raise RuntimeError('this must never run')\n"  # line 1
        "\n"  # line 2
        "def reserve(x):\n"  # line 3
        "    return x\n"  # line 4
    )
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("side_effect_mod", "reserve")
    assert result is not None
    file_path, line_range = result
    assert file_path == mod.resolve()
    assert 3 in line_range
    assert 4 in line_range


def test_production_lines_python_syntax_error_returns_none(tmp_path: Path) -> None:
    """A module file that can't be ast.parsed → None, not a crash."""
    bad = tmp_path / "syntax_err_mod.py"
    bad.write_text("def reserve(:\n    pass\n")  # invalid syntax
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("syntax_err_mod", "reserve")
    assert result is None


def test_production_lines_python_dotted_module(tmp_path: Path) -> None:
    """A dotted module path resolves to pkg/sub/mod.py under a sys.path dir."""
    pkg = tmp_path / "mypkg" / "sub"
    pkg.mkdir(parents=True)
    (tmp_path / "mypkg" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    mod = pkg / "mod.py"
    mod.write_text("def reserve(x):\n    return x\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("mypkg.sub.mod", "reserve")
    assert result is not None
    file_path, line_range = result
    assert file_path == mod.resolve()
    assert 1 in line_range


def test_production_lines_python_package_init(tmp_path: Path) -> None:
    """A package name resolves to its __init__.py and finds symbols there."""
    pkg = tmp_path / "mypkg2"
    pkg.mkdir()
    init = pkg / "__init__.py"
    init.write_text("# header\ndef reserve(x):\n    return x\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("mypkg2", "reserve")
    assert result is not None
    file_path, line_range = result
    assert file_path == init.resolve()
    assert 2 in line_range


def test_production_lines_python_assigned_symbol(tmp_path: Path) -> None:
    """A module-level assignment (not def/class) resolves to its line."""
    mod = tmp_path / "assigned_mod.py"
    mod.write_text("# c\nVERSION = '1.2.3'\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("assigned_mod", "VERSION")
    assert result is not None
    _, line_range = result
    assert 2 in line_range


def test_production_lines_python_reexported_symbol_not_resolved(tmp_path: Path) -> None:
    """A symbol only re-exported via `from x import name` is NOT resolved.

    Static resolution is deliberately scoped to symbols *defined* at the
    module's top level; it does not follow re-export imports (that would
    require executing or transitively parsing other modules). Call sites
    only pass symbols inferred from the test's own import of this module,
    so this narrowing is intentional, not a regression.
    """
    (tmp_path / "impl_mod.py").write_text("def reserve(x):\n    return x\n")
    reexport = tmp_path / "facade_mod.py"
    reexport.write_text("from impl_mod import reserve\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("facade_mod", "reserve")
    assert result is None


# ---------------------------------------------------------------------------
# Vitest target — helpers
# ---------------------------------------------------------------------------


def _write_production(tmp_path: Path, name: str = "foo.ts") -> Path:
    """Write a minimal production .ts file."""
    p = tmp_path / name
    p.write_text("export function reserve(x: number): number { return x; }\n")
    return p


# ---------------------------------------------------------------------------
# Vitest target — positive cases
# ---------------------------------------------------------------------------


def test_production_target_vitest_named_import(tmp_path: Path) -> None:
    """Named import that is called in the test body → resolved."""
    _write_production(tmp_path)
    test_file = tmp_path / "foo.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import { reserve } from "./foo";\n'
        "\n"
        'it("works", () => {\n'
        "  expect(reserve(1)).toBe(1);\n"
        "});\n"
    )
    result = production_target_vitest(test_file)
    assert result is not None
    prod_file, symbol = result
    assert prod_file == (tmp_path / "foo.ts").resolve()
    assert symbol == "reserve"


def test_production_target_vitest_namespace_import(tmp_path: Path) -> None:
    """Namespace import (import * as M) + M.reserve() → resolved."""
    _write_production(tmp_path)
    test_file = tmp_path / "foo.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import * as M from "./foo";\n'
        "\n"
        'it("works", () => {\n'
        "  expect(M.reserve(1)).toBe(1);\n"
        "});\n"
    )
    result = production_target_vitest(test_file)
    assert result is not None
    prod_file, symbol = result
    assert prod_file == (tmp_path / "foo.ts").resolve()
    assert symbol == "reserve"


def test_production_target_vitest_default_import(tmp_path: Path) -> None:
    """Default import + call → resolved."""
    _write_production(tmp_path)
    test_file = tmp_path / "foo.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import reserve from "./foo";\n'
        "\n"
        'it("works", () => {\n'
        "  expect(reserve(1)).toBe(1);\n"
        "});\n"
    )
    result = production_target_vitest(test_file)
    assert result is not None
    prod_file, symbol = result
    assert prod_file == (tmp_path / "foo.ts").resolve()
    assert symbol == "reserve"


def test_production_target_vitest_tsx_extension(tmp_path: Path) -> None:
    """Production file exists as .tsx, import path omits extension → resolves."""
    tsx_file = tmp_path / "Component.tsx"
    tsx_file.write_text("export function render() { return null; }\n")
    test_file = tmp_path / "Component.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import { render } from "./Component";\n'
        "\n"
        'it("works", () => {\n'
        "  expect(render()).toBe(null);\n"
        "});\n"
    )
    result = production_target_vitest(test_file)
    assert result is not None
    prod_file, symbol = result
    assert prod_file == tsx_file.resolve()
    assert symbol == "render"


# ---------------------------------------------------------------------------
# Vitest target — negative cases
# ---------------------------------------------------------------------------


def test_production_target_vitest_nonexistent_file() -> None:
    """File doesn't exist → None."""
    result = production_target_vitest(Path("/nonexistent/path/foo.test.ts"))
    assert result is None


def test_production_target_vitest_vitest_only_imports(tmp_path: Path) -> None:
    """Only vitest imports, no relative imports → None."""
    test_file = tmp_path / "foo.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n\nit("works", () => {\n  expect(1).toBe(1);\n});\n'
    )
    result = production_target_vitest(test_file)
    assert result is None


def test_production_target_vitest_npm_package_import(tmp_path: Path) -> None:
    """Import from an npm package (no dot prefix) → None."""
    test_file = tmp_path / "foo.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import { foo } from "lodash";\n'
        "\n"
        'it("works", () => {\n'
        "  expect(foo(1)).toBe(1);\n"
        "});\n"
    )
    result = production_target_vitest(test_file)
    assert result is None


def test_production_target_vitest_relative_not_on_disk(tmp_path: Path) -> None:
    """Relative import that doesn't exist on disk → None."""
    test_file = tmp_path / "foo.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import { X } from "./missing";\n'
        "\n"
        'it("works", () => {\n'
        "  expect(X(1)).toBe(1);\n"
        "});\n"
    )
    result = production_target_vitest(test_file)
    assert result is None


def test_production_target_vitest_import_never_called(tmp_path: Path) -> None:
    """Relative import present but never called in body → None."""
    _write_production(tmp_path)
    test_file = tmp_path / "foo.test.ts"
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import { reserve } from "./foo";\n'
        "\n"
        'it("works", () => {\n'
        "  expect(1).toBe(1);\n"
        "});\n"
    )
    result = production_target_vitest(test_file)
    assert result is None


# ---------------------------------------------------------------------------
# _vitest_symbol_lines — private helper for resolving symbol line ranges
# ---------------------------------------------------------------------------


def test_vitest_symbol_lines_function_declaration(tmp_path: Path) -> None:
    """function_declaration: returns line range covering the function."""
    target = tmp_path / "charge.ts"
    target.write_text(
        "// header\n"  # line 1
        "function reserve(x: number) {\n"  # line 2
        "  return x;\n"  # line 3
        "}\n"  # line 4
    )
    result = _vitest_symbol_lines(target, "reserve")
    assert result is not None
    assert 2 in result
    assert 4 in result


def test_vitest_symbol_lines_exported_function(tmp_path: Path) -> None:
    """export function ... → still finds the declaration."""
    target = tmp_path / "charge.ts"
    target.write_text(
        "export function chargeCard(token: string, amount: number): boolean {\n"  # line 1
        "  return amount > 0;\n"  # line 2
        "}\n"  # line 3
    )
    result = _vitest_symbol_lines(target, "chargeCard")
    assert result is not None
    assert 1 in result
    assert 3 in result


def test_vitest_symbol_lines_arrow_function_const(tmp_path: Path) -> None:
    """export const reserve = (...) => {} → returns declaration range."""
    target = tmp_path / "charge.ts"
    target.write_text(
        "export const reserve = (x: number): number => {\n"  # line 1
        "  return x + 1;\n"  # line 2
        "};\n"  # line 3
    )
    result = _vitest_symbol_lines(target, "reserve")
    assert result is not None
    assert 1 in result
    assert 3 in result


def test_vitest_symbol_lines_class_declaration(tmp_path: Path) -> None:
    """class Inventory { ... } → returns class range."""
    target = tmp_path / "inventory.ts"
    target.write_text(
        "class Inventory {\n"  # line 1
        "  reserve(x: number) {\n"  # line 2
        "    return x;\n"  # line 3
        "  }\n"  # line 4
        "}\n"  # line 5
    )
    result = _vitest_symbol_lines(target, "Inventory")
    assert result is not None
    assert 1 in result
    assert 5 in result


def test_vitest_symbol_lines_missing_symbol(tmp_path: Path) -> None:
    """Symbol not found in file → None."""
    target = tmp_path / "charge.ts"
    target.write_text("export function foo(): void {}\n")
    result = _vitest_symbol_lines(target, "nonexistent")
    assert result is None


def test_vitest_symbol_lines_invalid_file(tmp_path: Path) -> None:
    """Syntactically broken file → None (not a crash)."""
    result = _vitest_symbol_lines(tmp_path / "does_not_exist.ts", "anything")
    assert result is None
