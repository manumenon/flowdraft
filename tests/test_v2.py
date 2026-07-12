import unittest
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.flowdraft.schema import validate_spec, SpecError
from scripts.flowdraft.compiler import compile_spec
from scripts.flowdraft.layout_engine import layout
from scripts.render_v2 import run_pipeline

SPEC_PATH = ROOT / "assets" / "default-spec-v2.json"

class TestFlowDraftV2(unittest.TestCase):
    def test_schema_validation_valid(self):
        """Test that a valid v2 spec passes schema validation."""
        spec_data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        validated = validate_spec(spec_data)
        self.assertIn("elements", validated)
        self.assertIn("connections", validated)

    def test_schema_validation_invalid(self):
        """Test that invalid spec structures raise SpecError."""
        invalid_spec = {
            "canvas": {"width": 800},
            "elements": [
                {"id": "node_1"}  # Missing "type"
            ]
        }
        with self.assertRaises(SpecError):
            validate_spec(invalid_spec)

    def test_compiler_flat_elements(self):
        """Test that compiler successfully parses and flattens elements."""
        spec_data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        validated = validate_spec(spec_data)
        ir = compile_spec(validated)
        self.assertIn("nodes", ir)
        self.assertIn("connections", ir)
        
        # Check that parent/child relations are preserved
        nodes_map = {n["id"]: n for n in ir["nodes"]}
        self.assertIn("input_panel", nodes_map)
        self.assertIn("input_0", nodes_map)
        self.assertEqual(nodes_map["input_0"]["parent"], "input_panel")

    def test_layout_engine_coordinates(self):
        """Test that layout engine respects explicit overrides and sizes panels."""
        spec_data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        validated = validate_spec(spec_data)
        ir = compile_spec(validated)
        
        # Run layout
        laid_out_ir = layout(ir, canvas_w=1920, canvas_h=1440)
        nodes_map = {n["id"]: n for n in laid_out_ir["nodes"]}
        
        # Check that manual panel coordinate was preserved
        self.assertIsNotNone(nodes_map["center_panel"]["x"])
        self.assertIsNotNone(nodes_map["center_panel"]["y"])

    def test_cli_execution(self):
        """Test the end-to-end v2 rendering pipeline on the default spec."""
        out_dir = ROOT / "outputs" / "test_run"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        results = run_pipeline(
            spec_path=str(SPEC_PATH),
            outdir=str(out_dir),
            basename="test_v2_spec",
            run_checks=True,
            rebrand_name="FlowDraft"
        )
        
        self.assertTrue(results["checks"]["ok"])
        self.assertTrue((out_dir / "test_v2_spec.png").exists())
        self.assertTrue((out_dir / "test_v2_spec.gif").exists())
        self.assertTrue((out_dir / "test_v2_spec.svg").exists())
        self.assertTrue((out_dir / "test_v2_spec.excalidraw").exists())

if __name__ == "__main__":
    unittest.main()
