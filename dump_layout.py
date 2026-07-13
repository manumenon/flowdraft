"""Dump the fully laid-out IR for debugging structural issues."""
import json
from scripts.flowdraft.schema import validate_spec
from scripts.flowdraft.compiler import compile_spec
from scripts.flowdraft.layout_engine import layout

spec = json.load(open("assets/default-spec-v2.json", "r", encoding="utf-8"))
validated = validate_spec(spec)
ir = compile_spec(validated)
laid_out = layout(ir, canvas_w=1920, canvas_h=1440)

# Print all nodes
for n in laid_out["nodes"]:
    nid = n["id"]
    ntype = n["type"]
    title = (n.get("title") or "")[:60]
    x, y = n.get("x"), n.get("y")
    w, h = n.get("width"), n.get("height")
    print(f"=== {nid} (type={ntype}) ===")
    print(f"  pos=({x}, {y}), size=({w}, {h})")
    print(f"  title={title}")
    offsets = n.get("layout_offsets", {})
    for k, v in offsets.items():
        print(f"  offset.{k} = {v}")
    print()

# Print all edges
print("\n--- EDGES ---")
for e in laid_out.get("edges", []):
    src = e.get("source") or e.get("from")
    tgt = e.get("target") or e.get("to")
    label = (e.get("label") or "")[:40]
    pts = e.get("points", [])
    print(f"  {src} -> {tgt}  label={label!r}  points={len(pts)}")

# Print panels
print("\n--- PANELS ---")
for p in laid_out.get("panels", []):
    pid = p["id"]
    title = (p.get("title") or "")[:60]
    x, y = p.get("x"), p.get("y")
    w, h = p.get("width"), p.get("height")
    print(f"  panel {pid}: pos=({x},{y}) size=({w},{h}) title={title}")
    offsets = p.get("layout_offsets", {})
    for k, v in offsets.items():
        print(f"    offset.{k} = {v}")
