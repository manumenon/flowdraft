import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram


class RenderOutputChecksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = render_flowdraft_diagram
        cls.spec = json.loads((ROOT / "assets" / "default-spec.json").read_text(encoding="utf-8"))

    def test_generated_outputs_pass_contract_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(self.spec, Path(tmp), "sample")

            checks = self.renderer.check_outputs(result, self.spec)

        self.assertTrue(checks["ok"], checks)

    def test_contract_checks_report_invalid_excalidraw_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(self.spec, Path(tmp), "sample")
            excalidraw_path = Path(result["excalidraw"])
            excalidraw = json.loads(excalidraw_path.read_text(encoding="utf-8"))
            first_text = next(element for element in excalidraw["elements"] if element["type"] == "text")
            first_text["fontFamily"] = 1
            excalidraw_path.write_text(json.dumps(excalidraw), encoding="utf-8")

            checks = self.renderer.check_outputs(result, self.spec)

        self.assertFalse(checks["ok"])
        font_check = next(check for check in checks["checks"] if check["name"] == "excalidraw_text_font_family")
        self.assertFalse(font_check["ok"])


if __name__ == "__main__":
    unittest.main()
