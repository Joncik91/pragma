"""Tests for production_lines_python and production_target_vitest resolvers."""

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
    """Context manager that temporarily adds a dir to sys.path."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        sys.path.insert(0, str(path))
        try:
            yield
        finally:
            sys.path.remove(str(path))
            # Evict any modules loaded from this path so tests are isolated.
            to_remove = [
                k
                for k, v in sys.modules.items()
                if hasattr(v, "__file__") and v.__file__ and str(path) in v.__file__
            ]
            for k in to_remove:
                del sys.modules[k]

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
    assert production_lines_python("definitely_not_a_module_42", "fn") is None


def test_production_lines_python_missing_symbol(tmp_path: Path) -> None:
    """Module exists, symbol does not → None."""
    (tmp_path / "present_mod.py").write_text("x = 1\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("present_mod", "nonexistent_symbol_xyz")
    assert result is None


def test_production_lines_python_builtin_no_source() -> None:
    """builtins.len has no Python source → None."""
    result = production_lines_python("builtins", "len")
    assert result is None


def test_production_lines_python_import_error_handled(tmp_path: Path) -> None:
    """Module with a syntax/import error at import time → None, not crash."""
    bad = tmp_path / "bad_import_mod.py"
    bad.write_text("raise RuntimeError('intentional import failure')\n")
    with _add_to_sys_path(tmp_path):
        result = production_lines_python("bad_import_mod", "anything")
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
