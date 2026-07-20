#!/usr/bin/env python3
"""
render_flowdraft_diagram.py — Compatibility wrapper for FlowDraft Diagram Rendering CLI.
"""

import argparse
import sys
import json
from pathlib import Path

# Add project root to sys.path
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.render_v2 import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="FlowDraft Diagram Rendering CLI Wrapper.")
    parser.add_argument("--spec", required=True, help="Spec JSON path.")
    parser.add_argument("--outdir", required=True, help="Output directory.")
    parser.add_argument("--basename", default="sample_v2", help="Output basename.")
    parser.add_argument("--check", action="store_true", help="Validate output contracts.")
    parser.add_argument("--verify", action="store_true", help="Legacy verify flag.")
    parser.add_argument("--theme", default=None, help="Color theme (dark|light|white).")
    parser.add_argument("--rebrand", action="store_true", help="Rebrand strings.")
    args = parser.parse_args()

    # Rebrand defaults to True for legacy flowdraft
    rebrand_name = "FlowDraft"

    # In render_v2, the verification of frame movement is run inside check_outputs, 
    # which is triggered by run_checks=True (args.check).
    # If the user specifies --verify, we also trigger run_checks.
    run_checks = args.check or args.verify

    try:
        result = run_pipeline(
            spec_path=args.spec,
            outdir=args.outdir,
            basename=args.basename,
            run_checks=run_checks,
            theme_name=args.theme,
            rebrand_name=rebrand_name
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if run_checks and not result.get("checks", {}).get("ok", True):
            sys.exit(1)
            
    except Exception as e:
        sys.stderr.write(f"Pipeline Execution Error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
