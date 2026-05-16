from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load_evaluation_gate_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "evaluation_gate.py"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("evaluation_gate", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load evaluation_gate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


evaluation_gate = _load_evaluation_gate_module()


class EvaluationGateTests(unittest.TestCase):
    def test_score_report_static_gate_passes_current_workspace(self) -> None:
        self.assertEqual(evaluation_gate.collect_failures(), [])


if __name__ == "__main__":
    unittest.main()
