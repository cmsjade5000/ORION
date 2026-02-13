import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_validator():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "validate_plan_graph.py"
    spec = importlib.util.spec_from_file_location("validate_plan_graph", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


class TestValidatePlanGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = _load_validator()

    def _write_plan(self, body: str) -> tuple[str, tempfile.TemporaryDirectory]:
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "example-plan.md"
        path.write_text(body, encoding="utf-8")
        return str(path), temp_dir

    def test_valid_linear_graph(self):
        path, temp_dir = self._write_plan(
            """# Example Plan

## T1: Setup
- **depends_on**: []
- description: Start.

## T2: Build
- **depends_on:** [T1]
- description: Continue.

## T3: Verify
- depends_on: [T2]
- description: Finish.
"""
        )
        errors = self.v.validate_plan_file(path)
        temp_dir.cleanup()
        self.assertEqual(errors, [])

    def test_missing_depends_on(self):
        path, temp_dir = self._write_plan(
            """# Missing depends

## T1: Setup
- depends_on: []

## T2: Build
- description: No dependency declaration.
"""
        )
        errors = self.v.validate_plan_file(path)
        temp_dir.cleanup()
        self.assertTrue(any("T2" in error and "missing required 'depends_on'" in error for error in errors), errors)

    def test_unknown_dependency(self):
        path, temp_dir = self._write_plan(
            """# Unknown dependency

## T1: Setup
- depends_on: []

## T2: Build
- depends_on: [T9]
"""
        )
        errors = self.v.validate_plan_file(path)
        temp_dir.cleanup()
        self.assertTrue(any("unknown dependency 'T9'" in error for error in errors), errors)

    def test_self_dependency(self):
        path, temp_dir = self._write_plan(
            """# Self dependency

## T1: Setup
- depends_on: [T1]
"""
        )
        errors = self.v.validate_plan_file(path)
        temp_dir.cleanup()
        self.assertTrue(any("self-dependency" in error for error in errors), errors)

    def test_cycle_across_tasks(self):
        path, temp_dir = self._write_plan(
            """# Cyclic dependency

## T1: Setup
- depends_on: [T3]

## T2: Build
- depends_on: [T1]

## T3: Verify
- depends_on: [T2]
"""
        )
        errors = self.v.validate_plan_file(path)
        temp_dir.cleanup()
        self.assertTrue(any("cycle detected" in error for error in errors), errors)

    def test_no_t_tasks_passes(self):
        path, temp_dir = self._write_plan(
            """# Notes

This file has no task headings.

- depends_on: [T1]
"""
        )
        errors = self.v.validate_plan_file(path)
        temp_dir.cleanup()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
