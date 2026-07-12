import json
import tempfile
import unittest
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram

class ChallengerAdversarialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = render_flowdraft_diagram
        cls.default_spec = {
            "canvas": {
                "width": 1210,
                "height": 1138,
                "fps": 20,
                "frames": 2
            },
            "signature": "@FlowDraft",
            "title": {
                "prefix": "Adversarial",
                "highlight": "Verification",
                "subtitle": "Stress testing"
            },
            "inputs": [
                {"label": "In 1", "icon": "file"}
            ],
            "core": {
                "cards": [
                    {"title": "Step 1", "body": "Do 1"}
                ]
            }
        }

    def test_rebrand_case_variants_fail(self):
        """Case-sensitivity check: Verify that LANSHU or LanShu in title/signature are NOT replaced."""
        spec = self.default_spec.copy()
        spec["rebrand"] = True
        spec["title"] = {
            "prefix": "Developed by LANSHU",
            "highlight": "LanShu Engine",
            "subtitle": "lanshu helper"
        }
        
        # Test apply_rebranding directly
        rebranded_spec = self.renderer.apply_rebranding(spec)
        
        # 'lanshu' is lowercase, should be replaced with 'flowdraft'
        self.assertEqual(rebranded_spec["title"]["subtitle"], "flowdraft helper")
        
        # 'LANSHU' and 'LanShu' are NOT matched by apply_rebranding!
        # They will remain in the spec. Let's assert this failure/limitation.
        self.assertEqual(rebranded_spec["title"]["prefix"], "Developed by LANSHU")
        self.assertEqual(rebranded_spec["title"]["highlight"], "LanShu Engine")

    def test_single_frame_gif_motion_check_fails(self):
        """Verify that a valid 1-frame spec fails check_outputs due to the gif_has_motion rule."""
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 1210, "height": 1138, "frames": 1, "fps": 1}
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "one_frame")
            
            # Run output checks which should fail on gif_has_motion because there's only 1 frame
            checks_result = self.renderer.check_outputs(result, spec)
            
            self.assertFalse(checks_result["ok"], "Verification should fail for 1 frame since no motion is detected")
            motion_check = next(c for c in checks_result["checks"] if c["name"] == "gif_has_motion")
            self.assertFalse(motion_check["ok"], "gif_has_motion check should be False")

    def test_null_values_in_nested_dicts_render_as_none_string(self):
        """Verify that setting nested fields to None renders the word 'None' in the output instead of blank."""
        spec = self.default_spec.copy()
        spec["decision"] = {
            "title": None,
            "body": None
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "null_fields")
            
            # Check the svg file contents
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            
            # It converts None to 'None'!
            self.assertIn("None", svg_content, "None is converted to string 'None'")

if __name__ == "__main__":
    unittest.main()
