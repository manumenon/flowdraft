"""
flowdraft.layout_engine
-----------------------
FlowDraft v2 layout engine.  Takes the compiler IR (nodes with measured
sizes, connections, annotations) and assigns **absolute (x, y) positions**
to every node.

This module is self-contained — it depends only on the Python standard
library and the IR dict format produced by ``flowdraft.compiler.compile_spec``.

Public API
~~~~~~~~~~
- ``layout(ir, canvas_w, canvas_h)``         — main entry point
- ``layout_panel_children(panel, nodes_map)`` — position children within a panel

Design principles
~~~~~~~~~~~~~~~~~
1. **No hard-coded element names** — only type-based dispatch and graph
   analysis.  Zero ``if node["id"] == "specific_name"`` checks.
2. **Connection-driven auto-layout** — topological sort of the connection
   graph determines left-to-right order; vertical tiering groups panels
   by role (input → core → side → output).
3. **Content-driven sizing** — panel dimensions are computed from children's
   bounding boxes + padding, never guessed.
4. **Canvas fitting** — after layout, all coordinates are scaled/translated
   to fit the target canvas with margins.
"""

from __future__ import annotations

import math
import heapq
from collections import defaultdict, deque
from typing import Any, Optional

from .constants import THEME, SCALE
from .geometry import point_at_fraction, path_len
from .fonts import load_font, text_size
from .compiler import _scratch_draw
from . import constants as fc



# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

_CANVAS_MARGIN: float = 50.0          # px margin on all sides
_PANEL_GAP_H: float = 40.0           # horizontal gap between top-level elements
_PANEL_GAP_V: float = 100.0          # vertical gap between tiers
_FREE_ELEMENT_GAP: float = 30.0      # gap when placing free elements next to peers

# Default panel inner-layout values (used when panel has no layout dict)
_DEFAULT_DIRECTION: str = "row"
_DEFAULT_GAP: float = 24.0
_DEFAULT_FLOW_MAX_COLS: int = 3       # flow layout wraps after this many columns
_DEFAULT_GRID_COLS: int = 2

# Footer placement
_FOOTER_GAP: float = 16.0            # extra gap above footer inside panel


# ═══════════════════════════════════════════════════════════════════════════
# Helpers — graph building
# ═══════════════════════════════════════════════════════════════════════════

def _build_adjacency(
    connections: list[dict],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build forward and reverse adjacency lists from connections.

    Each connection has a ``path`` list of node IDs.  A path ``[A, B, C]``
    produces edges ``A→B`` and ``B→C``.

    Args:
        connections: The ``ir["connections"]`` list.

    Returns:
        ``(forward, reverse)`` — dicts mapping node_id → [successors]
        and node_id → [predecessors].
    """
    forward: dict[str, list[str]] = defaultdict(list)
    reverse: dict[str, list[str]] = defaultdict(list)

    for conn in connections:
        path = conn.get("path", [])
        if not path and "from" in conn and "to" in conn:
            path = [conn["from"], conn["to"]]
        if isinstance(path, str):
            path = [path]
        for a, b in zip(path, path[1:]):
            if b not in forward[a]:
                forward[a].append(b)
            if a not in reverse[b]:
                reverse[b].append(a)

    return dict(forward), dict(reverse)


def _resolve_to_toplevel(
    node_id: str,
    nodes_map: dict[str, dict],
) -> str:
    """Walk the parent chain to find the top-level ancestor.

    Args:
        node_id:   The starting node ID.
        nodes_map: id → node dict lookup.

    Returns:
        The ID of the top-level element (``parent is None``), or
        *node_id* itself if it is already top-level or unknown.
    """
    visited: set[str] = set()
    current = node_id
    while current in nodes_map:
        node = nodes_map[current]
        parent = node.get("parent")
        if parent is None or parent not in nodes_map:
            return current
        if current in visited:
            return current  # cycle guard
        visited.add(current)
        current = parent
    return node_id


def _build_toplevel_graph(
    connections: list[dict],
    nodes_map: dict[str, dict],
    toplevel_ids: set[str],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build an edge graph among **top-level** elements.

    Child-level connection endpoints are resolved to their top-level
    ancestor so we get a panel-to-panel dependency graph.

    Args:
        connections:  The IR connections list.
        nodes_map:    id → node dict.
        toplevel_ids: Set of IDs that are top-level nodes.

    Returns:
        ``(forward, reverse)`` — sets of successors / predecessors per
        top-level ID.
    """
    forward: dict[str, set[str]] = {tid: set() for tid in toplevel_ids}
    reverse: dict[str, set[str]] = {tid: set() for tid in toplevel_ids}

    for conn in connections:
        path = conn.get("path", [])
        if not path and "from" in conn and "to" in conn:
            path = [conn["from"], conn["to"]]
        if isinstance(path, str):
            path = [path]
        for a, b in zip(path, path[1:]):
            ta = _resolve_to_toplevel(a, nodes_map)
            tb = _resolve_to_toplevel(b, nodes_map)
            if ta != tb and ta in toplevel_ids and tb in toplevel_ids:
                forward.setdefault(ta, set()).add(tb)
                reverse.setdefault(tb, set()).add(ta)

    return forward, reverse


# ═══════════════════════════════════════════════════════════════════════════
# Helpers — topological sort (Kahn's algorithm)
# ═══════════════════════════════════════════════════════════════════════════

def _topological_sort(
    ids: set[str],
    forward: dict[str, set[str]],
    reverse: dict[str, set[str]],
) -> list[str]:
    """Kahn's topological sort of *ids* using the given dependency edges.

    Nodes with no predecessors come first (sources).  Ties are broken
    alphabetically for determinism.

    Args:
        ids:     All node IDs to sort.
        forward: id → set of successors.
        reverse: id → set of predecessors.

    Returns:
        A topologically ordered list.  If cycles exist they are appended
        at the end in alphabetical order.
    """
    in_degree: dict[str, int] = {nid: 0 for nid in ids}
    for nid in ids:
        for succ in forward.get(nid, set()):
            if succ in in_degree:
                in_degree[succ] = in_degree.get(succ, 0) + 1

    queue: list[str] = sorted(
        [nid for nid, deg in in_degree.items() if deg == 0]
    )
    result: list[str] = []

    while queue:
        nid = queue.pop(0)  # FIFO for BFS-like ordering
        result.append(nid)
        for succ in sorted(forward.get(nid, set())):
            if succ in in_degree:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)
                    queue.sort()  # keep deterministic

    # Append any remaining nodes (cycles)
    remaining = sorted(ids - set(result))
    result.extend(remaining)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Helpers — element classification (type-based, never name-based)
# ═══════════════════════════════════════════════════════════════════════════

def _classify_element(
    node: dict,
    nodes_map: dict[str, dict],
    fwd: dict[str, set[str]],
    rev: dict[str, set[str]],
) -> int:
    """Assign a vertical tier to a top-level element.

    Tier assignment (lower = higher on canvas):
        0 — "input tier": panels whose children are all type ``input``, or source panels.
        1 — "core tier": panels containing ``card`` children with many
            children, OR panels that have both incoming and outgoing
            top-level connections.
        2 — "side tier": supporting panels (few connections, no input
            children, not terminal).
        3 — "terminal tier": elements with no outgoing top-level edges
            (sinks), OR free elements like ``diamond`` / single ``card``.

    The classification is purely structural — no ID string matching.

    Args:
        node:      The top-level node dict.
        nodes_map: Full id → node lookup.
        fwd:       Top-level forward adjacency.
        rev:       Top-level reverse adjacency.

    Returns:
        An integer tier (0–3).
    """
    nid = node["id"]
    ntype = node.get("type", "card")
    children_ids = node.get("children", [])

    # Gather children types
    child_types = set()
    for cid in children_ids:
        child = nodes_map.get(cid)
        if child:
            child_types.add(child.get("type", "card"))

    has_outgoing = bool(fwd.get(nid))
    has_incoming = bool(rev.get(nid))

    # Tier 0: input panels (children are all inputs) OR source panels
    if ntype == "panel" and ((child_types and child_types <= {"input"}) or (has_outgoing and not has_incoming)):
        return 0

    # Tier 1: core processing — panels with card children that connect both
    # inward and outward, OR panels with many card children
    if ntype == "panel" and "card" in child_types:
        num_cards = sum(
            1 for cid in children_ids
            if nodes_map.get(cid, {}).get("type") == "card"
        )
        if num_cards >= 4 or (has_incoming and has_outgoing):
            return 1

    # Tier 3: terminal / free elements — no children and no outgoing edges
    if ntype != "panel":
        return 3

    # Tier 2: everything else (side panels)
    return 2


# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Layout panel children
# ═══════════════════════════════════════════════════════════════════════════

def _get_panel_padding(panel: dict) -> dict[str, float]:
    """Extract padding from a panel's resolved style or layout config.

    Falls back to sensible defaults if nothing is specified.

    Args:
        panel: The panel node dict.

    Returns:
        ``{"left": ..., "right": ..., "top": ..., "bottom": ...}``
    """
    # 1. Try explicit layout.padding first (v2 spec format)
    layout_cfg = panel.get("layout", {})
    if isinstance(layout_cfg, dict) and "padding" in layout_cfg:
        pad = layout_cfg["padding"]
        if isinstance(pad, dict):
            return {
                "left":   pad.get("left", 12),
                "right":  pad.get("right", 12),
                "top":    pad.get("top", 36),
                "bottom": pad.get("bottom", 12),
            }

    # 2. Try _resolved_style (set by compiler)
    style = panel.get("_resolved_style", {})
    pad = style.get("padding")
    if isinstance(pad, dict):
        return {
            "left":   pad.get("left", 12),
            "right":  pad.get("right", 12),
            "top":    pad.get("top", 36),
            "bottom": pad.get("bottom", 12),
        }

    # 3. Try explicit style.padding
    explicit_style = panel.get("style", {})
    pad = explicit_style.get("padding")
    if isinstance(pad, dict):
        return {
            "left":   pad.get("left", 12),
            "right":  pad.get("right", 12),
            "top":    pad.get("top", 36),
            "bottom": pad.get("bottom", 12),
        }

    return {"left": 12, "right": 12, "top": 36, "bottom": 12}


def _get_layout_config(panel: dict) -> dict[str, Any]:
    """Extract layout configuration from a panel.

    Looks for ``panel["layout"]`` (explicit v2 spec) and falls back to
    heuristics based on children types.

    Args:
        panel: The panel node dict.

    Returns:
        ``{"direction": ..., "gap": ..., "max_cols": ..., "grid_cols": ...}``
    """
    layout = panel.get("layout", {})
    if isinstance(layout, str):
        layout = {"direction": layout}

    return {
        "direction": layout.get("direction", _DEFAULT_DIRECTION),
        "gap":       layout.get("gap", _DEFAULT_GAP),
        "max_cols":  layout.get("max_cols", _DEFAULT_FLOW_MAX_COLS),
        "grid_cols": layout.get("grid_cols", _DEFAULT_GRID_COLS),
    }


def _separate_footer(
    children_ids: list[str],
    nodes_map: dict[str, dict],
) -> tuple[list[str], Optional[str]]:
    """Split children into main children and an optional footer.

    A footer is identified by ``_role == "footer"`` or an ID ending
    with ``"_footer"``.

    Args:
        children_ids: List of child node IDs.
        nodes_map:    id → node dict.

    Returns:
        ``(main_ids, footer_id_or_None)``
    """
    main: list[str] = []
    footer_id: Optional[str] = None

    for cid in children_ids:
        child = nodes_map.get(cid, {})
        if child.get("_role") == "footer" or cid.endswith("_footer"):
            footer_id = cid
        else:
            main.append(cid)

    return main, footer_id


def resolve_collision_row(node_x: float, node_y: float, node_w: float, node_h: float, fixed_nodes: list[dict], gap: float) -> float:
    changed = True
    while changed:
        changed = False
        for fn in fixed_nodes:
            fx, fy, fw, fh = fn["x"], fn["y"], fn["width"], fn["height"]
            # Check overlap
            if (node_x < fx + fw and node_x + node_w > fx and
                node_y < fy + fh and node_y + node_h > fy):
                node_x = fx + fw + gap
                changed = True
                break
    return node_x


def resolve_collision_col(node_x: float, node_y: float, node_w: float, node_h: float, fixed_nodes: list[dict], gap: float) -> float:
    changed = True
    while changed:
        changed = False
        for fn in fixed_nodes:
            fx, fy, fw, fh = fn["x"], fn["y"], fn["width"], fn["height"]
            # Check overlap
            if (node_x < fx + fw and node_x + node_w > fx and
                node_y < fy + fh and node_y + node_h > fy):
                node_y = fy + fh + gap
                changed = True
                break
    return node_y


def _layout_row(
    child_ids: list[str],
    nodes_map: dict[str, dict],
    gap: float,
    origin_x: float,
    origin_y: float,
    fixed_nodes: list[dict] = [],
) -> tuple[float, float]:
    """Lay children out left-to-right in a single row, avoiding fixed nodes.

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Horizontal gap between children.
        origin_x:  X start for first child.
        origin_y:  Y start for first child.
        fixed_nodes: List of fixed anchor nodes.

    Returns:
        ``(total_width, max_height)`` of the row.
    """
    cursor_x = origin_x
    max_h: float = 0.0

    for i, cid in enumerate(child_ids):
        child = nodes_map.get(cid)
        if child is None:
            continue
        
        # Resolve collision against fixed nodes
        cursor_x = resolve_collision_row(cursor_x, origin_y, child["width"], child["height"], fixed_nodes, gap)
        
        child["x"] = cursor_x
        child["y"] = origin_y
        cursor_x += child["width"] + gap
        max_h = max(max_h, child["height"])

    total_w = cursor_x - gap - origin_x if child_ids else 0.0
    return total_w, max_h


def _layout_column(
    child_ids: list[str],
    nodes_map: dict[str, dict],
    gap: float,
    origin_x: float,
    origin_y: float,
    fixed_nodes: list[dict] = [],
) -> tuple[float, float]:
    """Lay children out top-to-bottom in a single column, avoiding fixed nodes.

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Vertical gap between children.
        origin_x:  X start for all children.
        origin_y:  Y start for first child.
        fixed_nodes: List of fixed anchor nodes.

    Returns:
        ``(max_width, total_height)`` of the column.
    """
    cursor_y = origin_y
    max_w: float = 0.0

    for cid in child_ids:
        child = nodes_map.get(cid)
        if child is None:
            continue
        
        # Resolve collision against fixed nodes
        cursor_y = resolve_collision_col(origin_x, cursor_y, child["width"], child["height"], fixed_nodes, gap)
        
        child["x"] = origin_x
        child["y"] = cursor_y
        cursor_y += child["height"] + gap
        max_w = max(max_w, child["width"])

    total_h = cursor_y - gap - origin_y if child_ids else 0.0
    return max_w, total_h


def _layout_flow(
    child_ids: list[str],
    nodes_map: dict[str, dict],
    gap: float,
    max_cols: int,
    origin_x: float,
    origin_y: float,
    fixed_nodes: list[dict] = [],
) -> tuple[float, float]:
    """Lay children in rows, wrapping after *max_cols* per row, avoiding fixed nodes.

    Within each row children are left-to-right with *gap* spacing.
    Rows are stacked top-to-bottom with *gap* vertical spacing.

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Spacing in both axes.
        max_cols:  Maximum children per row before wrapping.
        origin_x:  X start.
        origin_y:  Y start.
        fixed_nodes: List of fixed anchor nodes.

    Returns:
        ``(total_width, total_height)`` bounding box of all rows.
    """
    rows: list[list[str]] = []
    for i in range(0, len(child_ids), max_cols):
        rows.append(child_ids[i : i + max_cols])

    cursor_y = origin_y
    overall_w: float = 0.0

    for row_ids in rows:
        row_max_h = max((nodes_map[cid]["height"] for cid in row_ids if cid in nodes_map), default=0.0)
        cursor_y = resolve_collision_col(origin_x, cursor_y, overall_w or 1.0, row_max_h, fixed_nodes, gap)
        
        row_w, row_h = _layout_row(row_ids, nodes_map, gap, origin_x, cursor_y, fixed_nodes)
        overall_w = max(overall_w, row_w)
        cursor_y += row_h + gap

    total_h = cursor_y - gap - origin_y if rows else 0.0
    return overall_w, total_h


def _layout_grid(
    child_ids: list[str],
    nodes_map: dict[str, dict],
    gap: float,
    grid_cols: int,
    origin_x: float,
    origin_y: float,
    fixed_nodes: list[dict] = [],
) -> tuple[float, float]:
    """Lay children in a fixed-column grid, avoiding fixed nodes.

    Column widths and row heights are uniform (max of each row / column).

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Spacing in both axes.
        grid_cols: Number of columns.
        origin_x:  X start.
        origin_y:  Y start.
        fixed_nodes: List of fixed anchor nodes.

    Returns:
        ``(total_width, total_height)`` bounding box of the grid.
    """
    if not child_ids:
        return 0.0, 0.0

    # Compute uniform cell size
    col_w: float = 0.0
    row_h: float = 0.0
    for cid in child_ids:
        child = nodes_map.get(cid)
        if child:
            col_w = max(col_w, child["width"])
            row_h = max(row_h, child["height"])

    num_rows = math.ceil(len(child_ids) / grid_cols)

    for idx, cid in enumerate(child_ids):
        child = nodes_map.get(cid)
        if child is None:
            continue
        c_col = idx % grid_cols
        c_row = idx // grid_cols
        cx = origin_x + c_col * (col_w + gap)
        cy = origin_y + c_row * (row_h + gap)
        
        # Check collision and shift right in grid column steps or row steps if needed
        cx = resolve_collision_row(cx, cy, col_w, row_h, fixed_nodes, gap)
        
        child["x"] = cx
        child["y"] = cy

    # Compute final bounds based on actual placed children
    placed_nodes = [nodes_map[cid] for cid in child_ids if cid in nodes_map]
    if placed_nodes:
        max_x = max(n["x"] + n["width"] for n in placed_nodes)
        max_y = max(n["y"] + n["height"] for n in placed_nodes)
        total_w = max_x - origin_x
        total_h = max_y - origin_y
    else:
        total_w = grid_cols * col_w + (grid_cols - 1) * gap
        total_h = num_rows * row_h + (num_rows - 1) * gap
        
    return total_w, total_h


def layout_panel_children(
    panel: dict,
    nodes_map: dict[str, dict],
) -> None:
    """Position a panel's children and compute the panel's final size.

    Children with explicit coordinates in the spec are kept as absolute
    positions (converted to relative offsets).  Remaining children are
    arranged according to ``panel["layout"]["direction"]``: ``row``,
    ``column``, ``flow``, or ``grid``.

    The panel's ``width`` and ``height`` are updated in-place to enclose
    all children plus padding.

    Args:
        panel:     The panel node dict (mutated in-place).
        nodes_map: Full id → node lookup.
    """
    children_ids = panel.get("children", [])
    if not children_ids:
        return

    pad = _get_panel_padding(panel)
    cfg = _get_layout_config(panel)
    direction = cfg["direction"]
    gap = cfg["gap"]

    main_ids, footer_id = _separate_footer(children_ids, nodes_map)

    # ── Separate manually positioned from auto-laid out children ─────
    manual_ids = []
    auto_ids = []
    parent_x = panel.get("x", 0.0) or 0.0
    parent_y = panel.get("y", 0.0) or 0.0

    for cid in main_ids:
        node = nodes_map.get(cid)
        if node is None:
            continue
        if node.get("x") is not None or node.get("y") is not None:
            manual_ids.append(cid)
            # Coordinates inside panel are panel-relative
            node["x"] = node.get("x") or 0.0
            node["y"] = node.get("y") or 0.0
        else:
            auto_ids.append(cid)

    footer_is_manual = False
    if footer_id and footer_id in nodes_map:
        f_node = nodes_map[footer_id]
        if f_node.get("x") is not None or f_node.get("y") is not None:
            footer_is_manual = True
            f_node["x"] = f_node.get("x") or 0.0
            f_node["y"] = f_node.get("y") or 0.0

    # Auto-detect direction for input panels (children are all inputs → row)
    if direction == _DEFAULT_DIRECTION and auto_ids:
        child_types = {
            nodes_map.get(cid, {}).get("type", "card") for cid in auto_ids
        }
        if child_types == {"input"}:
            direction = "row"

    # Auto-detect flow for large card sets (>3 cards in a row panel)
    if direction == "row" and len(auto_ids) > cfg["max_cols"]:
        all_cards = all(
            nodes_map.get(cid, {}).get("type") == "card" for cid in auto_ids
        )
        if all_cards:
            direction = "flow"

    # Fixed nodes (rigid anchors) for collision checking
    fixed_nodes = [
        nodes_map[cid] for cid in manual_ids 
        if cid in nodes_map
    ]

    # Pre-calculate title and subtitle text wrapping based on available width budget
    offsets = panel.get("layout_offsets", {})
    init_panel_w = max(panel.get("width", 0.0), 100.0)
    avail_w = max(50.0, init_panel_w - pad["left"] - pad["right"])
    if "badge" in offsets:
        avail_w = max(50.0, avail_w - (offsets["badge"]["w"] + 15.0))

    from PIL import Image, ImageDraw
    img_temp = Image.new("RGB", (1, 1))
    draw_temp = ImageDraw.Draw(img_temp)
    from scripts.flowdraft.compiler import _measure_text

    if "title" in offsets:
        offsets["title"]["w"] = avail_w
        title_text = panel.get("title", "")
        if title_text:
            _, t_size, t_w, t_h = _measure_text(
                draw_temp, title_text, avail_w, 200.0, offsets["title"]["size"],
                min_size=offsets["title"]["min_size"], hand=offsets["title"]["hand"], bold=offsets["title"]["bold"]
            )
            offsets["title"]["h"] = max(34.0, t_h)
            offsets["title"]["size"] = t_size

    if "subtitle" in offsets:
        sub_avail_w = max(50.0, init_panel_w - pad["left"] - pad["right"])
        offsets["subtitle"]["w"] = sub_avail_w
        subtitle_text = panel.get("subtitle", "")
        if subtitle_text:
            if "title" in offsets:
                offsets["subtitle"]["y"] = offsets["title"]["y"] + offsets["title"]["h"] + 6.0
            _, s_size, s_w, s_h = _measure_text(
                draw_temp, subtitle_text, sub_avail_w, 100.0, offsets["subtitle"]["size"],
                min_size=offsets["subtitle"]["min_size"], hand=offsets["subtitle"]["hand"], bold=offsets["subtitle"]["bold"]
            )
            offsets["subtitle"]["h"] = s_h
            offsets["subtitle"]["size"] = s_size

    # Calculate header height accurately to prevent children from overlapping titles
    header_h = 0.0
    if "title" in offsets:
        header_h = max(header_h, offsets["title"]["y"] + offsets["title"]["h"])
    if "subtitle" in offsets:
        header_h = max(header_h, offsets["subtitle"]["y"] + offsets["subtitle"]["h"])
    if "badge" in offsets:
        header_h = max(header_h, offsets["badge"]["y"] + offsets["badge"]["h"])
    if header_h > 0:
        header_h += 15.0  # add buffer below header area

    origin_x = pad["left"]
    origin_y = max(pad["top"], header_h)
    content_w, content_h = 0.0, 0.0

    if auto_ids:
        if direction == "column":
            content_w, content_h = _layout_column(
                auto_ids, nodes_map, gap, origin_x, origin_y, fixed_nodes
            )
        elif direction == "flow":
            content_w, content_h = _layout_flow(
                auto_ids, nodes_map, gap, cfg["max_cols"],
                origin_x, origin_y, fixed_nodes
            )
        elif direction == "grid":
            content_w, content_h = _layout_grid(
                auto_ids, nodes_map, gap, cfg["grid_cols"],
                origin_x, origin_y, fixed_nodes
            )
        else:  # "row" (default)
            content_w, content_h = _layout_row(
                auto_ids, nodes_map, gap, origin_x, origin_y, fixed_nodes
            )

    # ── Place auto-laid out footer ───────────────────────────────────
    if footer_id and footer_id in nodes_map and not footer_is_manual:
        ref_w = content_w
        if manual_ids:
            in_flow_manual = [nodes_map[cid] for cid in manual_ids if not nodes_map[cid].get("out_of_flow")]
            max_manual_x = max((n["x"] + n["width"] for n in in_flow_manual), default=0.0)
            ref_w = max(content_w, max_manual_x - origin_x)

        footer_node = nodes_map[footer_id]
        footer_w = max(200.0, ref_w)
        footer_node["width"] = footer_w

        from scripts.flowdraft.compiler import _measure_card
        res = _measure_card(footer_node, draw_temp, footer_node.get("_resolved_style", {}))
        footer_node["height"] = res["height"]
        footer_node["layout_offsets"] = res["layout_offsets"]

        footer_top = origin_y + content_h + _FOOTER_GAP
        footer_x = origin_x + max(0.0, (ref_w - footer_w) / 2.0)
        footer_node["x"] = footer_x
        footer_node["y"] = footer_top

    # ── Update panel dimensions to enclose all in-flow children ──────
    in_flow_child_nodes = [
        nodes_map[cid] for cid in children_ids 
        if cid in nodes_map and not nodes_map[cid].get("out_of_flow")
    ]
    if in_flow_child_nodes:
        max_child_x = max(n.get("x", 0.0) + n.get("width", 0.0) for n in in_flow_child_nodes)
        max_child_y = max(n.get("y", 0.0) + n.get("height", 0.0) for n in in_flow_child_nodes)
        panel["width"] = max(panel.get("width", 0.0), max_child_x + pad["right"])
        panel["height"] = max(panel.get("height", 0.0), max_child_y + pad["bottom"])
    else:
        panel["width"] = max(panel.get("width", 0.0), pad["left"] + pad["right"])
        panel["height"] = max(panel.get("height", 0.0), pad["top"] + pad["bottom"])


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Auto-layout top-level elements
# ═══════════════════════════════════════════════════════════════════════════

def _assign_tiers(
    toplevel_ids: list[str],
    nodes_map: dict[str, dict],
    fwd: dict[str, set[str]],
    rev: dict[str, set[str]],
) -> dict[int, list[str]]:
    """Group top-level elements into vertical tiers.

    Args:
        toplevel_ids: Topologically sorted top-level IDs.
        nodes_map:    id → node dict.
        fwd:          Top-level forward adjacency.
        rev:          Top-level reverse adjacency.

    Returns:
        ``{tier_number: [node_ids ...]}`` preserving topological order
        within each tier.
    """
    tiers: dict[int, list[str]] = defaultdict(list)

    for nid in toplevel_ids:
        node = nodes_map[nid]
        tier = _classify_element(node, nodes_map, fwd, rev)
        tiers[tier].append(nid)

    return dict(tiers)


def _place_tier_horizontal(
    tier_ids: list[str],
    nodes_map: dict[str, dict],
    start_x: float,
    start_y: float,
    gap: float,
    fixed_nodes: list[dict] = [],
) -> tuple[float, float]:
    """Place a tier's elements in a horizontal row, avoiding fixed nodes.

    Args:
        tier_ids:  IDs of elements in this tier.
        nodes_map: id → node dict.
        start_x:   Starting X.
        start_y:   Starting Y.
        gap:       Horizontal gap between elements.
        fixed_nodes: List of fixed anchor nodes.

    Returns:
        ``(total_width, max_height)`` of the tier row.
    """
    cursor_x = start_x
    max_h: float = 0.0

    for nid in tier_ids:
        node = nodes_map[nid]
        # Resolve collision against fixed nodes
        cursor_x = resolve_collision_row(cursor_x, start_y, node["width"], node["height"], fixed_nodes, gap)
        node["x"] = cursor_x
        node["y"] = start_y
        cursor_x += node["width"] + gap
        max_h = max(max_h, node["height"])

    total_w = cursor_x - gap - start_x if tier_ids else 0.0
    return total_w, max_h


def _auto_layout_toplevel(
    toplevel_ids: set[str],
    nodes_map: dict[str, dict],
    connections: list[dict],
    fixed_ids: set[str] = set(),
) -> None:
    """Position top-level elements using graph analysis.

    Algorithm:
    1. Build a directed graph among top-level elements.
    2. Topological sort to determine left-to-right order.
    3. Classify each element into a vertical tier (0–3).
    4. Lay out each tier as a horizontal row, stacking tiers vertically.
    5. Centre narrower tiers relative to the widest tier.

    Args:
        toplevel_ids: IDs of all top-level nodes.
        nodes_map:    id → node dict (mutated in-place with x, y).
        connections:  The IR connections list.
        fixed_ids:    IDs of top-level elements with fixed coordinates.
    """
    if not toplevel_ids:
        return

    fwd, rev = _build_toplevel_graph(connections, nodes_map, toplevel_ids | fixed_ids)
    topo_order = _topological_sort(toplevel_ids, fwd, rev)

    tiers = _assign_tiers(topo_order, nodes_map, fwd, rev)

    # ── Lay out each tier as a horizontal row ────────────────────────
    tier_numbers = sorted(tiers.keys())
    tier_extents: dict[int, tuple[float, float]] = {}  # tier → (width, height)
    cursor_y: float = 0.0
    
    fixed_nodes = [nodes_map[fid] for fid in fixed_ids if fid in nodes_map]

    # Calculate max tier width to estimate center
    max_tier_w = 0.0

    for tn in tier_numbers:
        tier_ids = tiers[tn]
        
        # Estimate height of tier
        tier_h = max((nodes_map[nid]["height"] for nid in tier_ids), default=0.0)
        
        # Check collision and shift cursor_y down if needed
        cursor_y = resolve_collision_col(0.0, cursor_y, max_tier_w or 1000.0, tier_h, fixed_nodes, _PANEL_GAP_V)
        
        tw, th = _place_tier_horizontal(
            tier_ids, nodes_map, 0.0, cursor_y, _PANEL_GAP_H, fixed_nodes
        )
        tier_extents[tn] = (tw, th)
        max_tier_w = max(max_tier_w, tw)
        cursor_y += th + _PANEL_GAP_V

    # ── Centre tiers relative to the widest ──────────────────────────
    for tn in tier_numbers:
        tw, _ = tier_extents[tn]
        offset_x = (max_tier_w - tw) / 2
        if offset_x > 0:
            for nid in tiers[tn]:
                nodes_map[nid]["x"] += offset_x


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Position free elements (not in any panel)
# ═══════════════════════════════════════════════════════════════════════════

def _position_free_elements(
    nodes: list[dict],
    nodes_map: dict[str, dict],
    connections: list[dict],
) -> None:
    """Position free-standing elements based on their connections.

    A "free" element is one with ``parent is None`` and no ``x`` value
    yet assigned by the tier layout (typically diamonds and standalone
    cards that sit outside panels).

    Strategy: find the predecessor(s) of the free element via connections,
    then place the free element to the right of the rightmost predecessor.

    Args:
        nodes:       Full flat node list.
        nodes_map:   id → node dict.
        connections: The IR connections list.
    """
    fwd_all, rev_all = _build_adjacency(connections)

    free_nodes = [
        n for n in nodes
        if n.get("parent") is None and n.get("x") is None
    ]
    if not free_nodes:
        return

    # Iteratively place free nodes that have at least one placed predecessor
    max_iterations = len(free_nodes) * 2  # safety bound
    placed: set[str] = set()

    for _ in range(max_iterations):
        progress = False
        for node in free_nodes:
            nid = node["id"]
            if nid in placed:
                continue

            preds = rev_all.get(nid, [])
            placed_preds = [
                p for p in preds
                if nodes_map.get(p, {}).get("x") is not None
            ]

            if placed_preds:
                # Place to the right of the rightmost predecessor
                ref = max(
                    placed_preds,
                    key=lambda p: (
                        nodes_map[p]["x"] + nodes_map[p]["width"]
                    ),
                )
                ref_node = nodes_map[ref]
                node["x"] = ref_node["x"] + ref_node["width"] + _FREE_ELEMENT_GAP
                # Vertically centre-align with the predecessor
                node["y"] = ref_node["y"] + (ref_node["height"] - node["height"]) / 2
                placed.add(nid)
                progress = True

            elif not preds:
                # No connections at all — try placing after a successor
                succs = fwd_all.get(nid, [])
                placed_succs = [
                    s for s in succs
                    if nodes_map.get(s, {}).get("x") is not None
                ]
                if placed_succs:
                    ref = min(
                        placed_succs,
                        key=lambda s: nodes_map[s]["x"],
                    )
                    ref_node = nodes_map[ref]
                    node["x"] = ref_node["x"] - node["width"] - _FREE_ELEMENT_GAP
                    node["y"] = ref_node["y"] + (ref_node["height"] - node["height"]) / 2
                    placed.add(nid)
                    progress = True

        if not progress:
            break

    # Last resort: stack any truly orphaned free nodes below everything
    all_placed = [
        n for n in nodes
        if n.get("x") is not None and n.get("y") is not None
    ]
    if all_placed:
        max_y = max(n["y"] + n["height"] for n in all_placed)
    else:
        max_y = 0.0

    orphan_x: float = 0.0
    for node in free_nodes:
        if node["id"] not in placed:
            node["x"] = orphan_x
            node["y"] = max_y + _PANEL_GAP_V
            orphan_x += node["width"] + _FREE_ELEMENT_GAP


# ═══════════════════════════════════════════════════════════════════════════
# Step 3b: Convert child positions from panel-relative to absolute
# ═══════════════════════════════════════════════════════════════════════════

def _absolutize_recursive(
    node_id: str,
    parent_x: float,
    parent_y: float,
    nodes_map: dict[str, dict],
) -> None:
    """Pre-order DFS walk to propagate coordinates to child elements recursively."""
    node = nodes_map[node_id]
    
    # If the node has relative coordinates, make them absolute
    if node.get("x") is not None:
        node["x"] += parent_x
    if node.get("y") is not None:
        node["y"] += parent_y
        
    curr_x = node.get("x", 0.0) or 0.0
    curr_y = node.get("y", 0.0) or 0.0
    
    for cid in node.get("children", []):
        if cid in nodes_map:
            _absolutize_recursive(cid, curr_x, curr_y, nodes_map)


def _absolutize_children(
    nodes: list[dict],
    nodes_map: dict[str, dict],
) -> None:
    """Convert child positions from panel-local to absolute coordinates using recursive DFS.

    Args:
        nodes:     Full flat node list.
        nodes_map: id → node dict.
    """
    toplevel_nodes = [n for n in nodes if n.get("parent") is None]
    for node in toplevel_nodes:
        _absolutize_recursive(node["id"], 0.0, 0.0, nodes_map)


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Canvas fitting
# ═══════════════════════════════════════════════════════════════════════════

def _compute_bounding_box(
    nodes: list[dict],
) -> tuple[float, float, float, float]:
    """Compute the axis-aligned bounding box of all positioned nodes across the hierarchy.

    Args:
        nodes: Flat node list (only nodes with ``x`` and ``y`` are counted).

    Returns:
        ``(min_x, min_y, max_x, max_y)``
    """
    positioned = [
        n for n in nodes
        if n.get("x") is not None and n.get("y") is not None
    ]
    if not positioned:
        return 0.0, 0.0, 1.0, 1.0

    min_x = min(n["x"] for n in positioned)
    min_y = min(n["y"] for n in positioned)
    max_x = max(n["x"] + n.get("width", 0.0) for n in positioned)
    max_y = max(n["y"] + n.get("height", 0.0) for n in positioned)

    return min_x, min_y, max_x, max_y


def _fit_to_canvas(
    nodes: list[dict],
    canvas_w: float,
    canvas_h: float,
    margin: float = _CANVAS_MARGIN,
    has_title: bool = False,
    scale_to_fit: bool = True,
) -> None:
    """Scale and translate top-level element positions to fit the canvas.

    The overall spacing is scaled to fit within the canvas while keeping
    element widths and heights unscaled (content-driven card sizes must
    be preserved to prevent text spill).

    Args:
        nodes:    Flat node list (mutated in-place).
        canvas_w: Target canvas width.
        canvas_h: Target canvas height.
        margin:   Margin on each side.
        scale_to_fit: If False, keep layout unscaled at 100%.
    """
    positioned_all = [
        n for n in nodes
        if n.get("x") is not None and n.get("y") is not None
    ]
    if not positioned_all:
        return

    min_x, min_y, max_x, max_y = _compute_bounding_box(nodes)
    content_w = max_x - min_x
    content_h = max_y - min_y

    if content_w <= 0 or content_h <= 0:
        return

    avail_w = canvas_w - 2 * margin
    if has_title:
        avail_h = canvas_h - 130.0 - 2 * margin
    else:
        avail_h = canvas_h - 2 * margin

    # Scale spacing independently in X and Y
    if scale_to_fit:
        scale_x = min(1.0, avail_w / content_w)
        scale_y = min(1.0, avail_h / content_h)
    else:
        scale_x = 1.0
        scale_y = 1.0

    # Ensure canvas offsets remain non-negative (>= margin) so top/left elements are never shifted off-screen
    scaled_w = content_w * scale_x
    scaled_h = content_h * scale_y
    offset_x = max(margin, margin + (avail_w - scaled_w) / 2.0)
    offset_y = max(margin, margin + (avail_h - scaled_h) / 2.0)

    toplevel_nodes = [n for n in positioned_all if n.get("parent") is None]
    for node in toplevel_nodes:
        node["x"] = (node["x"] - min_x) * scale_x + offset_x
        node["y"] = (node["y"] - min_y) * scale_y + offset_y

    # Resolve horizontal overlaps among top-level nodes
    toplevel_nodes.sort(key=lambda n: n["x"])
    for i in range(len(toplevel_nodes)):
        for j in range(i):
            prev = toplevel_nodes[j]
            curr = toplevel_nodes[i]
            prev_x2 = prev["x"] + prev.get("width", 0.0)
            prev_y1 = prev["y"]
            prev_y2 = prev["y"] + prev.get("height", 0.0)
            curr_x1 = curr["x"]
            curr_y1 = curr["y"]
            curr_y2 = curr["y"] + curr.get("height", 0.0)
            
            overlap_h = min(prev_y2, curr_y2) - max(prev_y1, curr_y1)
            min_h = min(prev.get("height", 0.0), curr.get("height", 0.0))
            y_overlap = (overlap_h > 0.3 * min_h)
            if y_overlap and curr_x1 < prev_x2 + 20.0:
                curr["x"] = prev_x2 + 20.0

    # Resolve vertical overlaps among top-level nodes
    toplevel_nodes.sort(key=lambda n: n["y"])
    for i in range(len(toplevel_nodes)):
        for j in range(i):
            prev = toplevel_nodes[j]
            curr = toplevel_nodes[i]
            prev_y2 = prev["y"] + prev.get("height", 0.0)
            prev_x1 = prev["x"]
            prev_x2 = prev["x"] + prev.get("width", 0.0)
            curr_y1 = curr["y"]
            curr_x1 = curr["x"]
            curr_x2 = curr["x"] + curr.get("width", 0.0)
            
            overlap_w = min(prev_x2, curr_x2) - max(prev_x1, curr_x1)
            min_w = min(prev.get("width", 0.0), curr.get("width", 0.0))
            x_overlap = (overlap_w > 0.3 * min_w)
            if x_overlap and curr_y1 < prev_y2 + 20.0:
                curr["y"] = prev_y2 + 20.0


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Position annotations
# ═══════════════════════════════════════════════════════════════════════════

def _position_annotations(
    annotations: list[dict],
    nodes: list[dict],
) -> None:
    """Position annotation labels relative to the layout.

    Annotations (loop_label, retry_label, etc.) are placed near the
    bottom-centre of the content area.

    Args:
        annotations: The annotation node list (mutated in-place).
        nodes:       The full positioned node list.
    """
    if not annotations:
        return

    positioned = [
        n for n in nodes
        if n.get("x") is not None and n.get("y") is not None
    ]
    if not positioned:
        return

    _, _, max_x, max_y = _compute_bounding_box(nodes)
    min_x = min(n["x"] for n in positioned)
    center_x = (min_x + max_x) / 2

    cursor_y = max_y + 10
    for ann in annotations:
        if ann.get("x") is not None and ann.get("y") is not None:
            continue
        ann_w = ann.get("width", 200)
        ann_h = ann.get("height", 20)
        ann["x"] = center_x - ann_w / 2
        ann["y"] = cursor_y
        ann["width"] = ann_w
        ann["height"] = ann_h
        cursor_y += ann_h + 8



# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def _center_layout_on_canvas(
    nodes: list[dict],
    canvas_w: float,
    canvas_h: float,
    has_title: bool = False,
) -> None:
    """Translate all diagram node coordinates so that the entire layout is centered on the canvas."""
    positioned = [n for n in nodes if n.get("x") is not None and n.get("y") is not None]
    if not positioned:
        return

    min_x = min(n["x"] for n in positioned)
    min_y = min(n["y"] for n in positioned)
    max_x = max(n["x"] + n["width"] for n in positioned)
    max_y = max(n["y"] + n["height"] for n in positioned)

    content_w = max_x - min_x
    content_h = max_y - min_y

    target_cx = canvas_w / 2.0
    if has_title:
        target_cy = 130.0 + (canvas_h - 130.0) / 2.0
    else:
        target_cy = canvas_h / 2.0

    current_cx = min_x + content_w / 2.0
    current_cy = min_y + content_h / 2.0

    dx = target_cx - current_cx
    dy = target_cy - current_cy

    for node in nodes:
        if node.get("x") is not None:
            node["x"] += dx
        if node.get("y") is not None:
            node["y"] += dy


def _scale_layout_uniformly(nodes: list[dict], scale: float) -> None:
    """Scale all element absolute positions, sizes, offsets, and styles uniformly by scale."""
    if scale == 1.0:
        return
        
    for node in nodes:
        if node.get("x") is not None:
            node["x"] *= scale
        if node.get("y") is not None:
            node["y"] *= scale
        if node.get("width") is not None:
            node["width"] *= scale
        if node.get("height") is not None:
            node["height"] *= scale
            
        style = node.get("_resolved_style", {})
        if "cornerRadius" in style and style["cornerRadius"] is not None:
            style["cornerRadius"] *= scale
        if "strokeWidth" in style and style["strokeWidth"] is not None:
            style["strokeWidth"] *= scale
        if "padding" in style and isinstance(style["padding"], dict):
            pad = style["padding"]
            pad["left"] *= scale
            pad["right"] *= scale
            pad["top"] *= scale
            pad["bottom"] *= scale
            
        offsets = node.get("layout_offsets", {})
        for key in ["title", "subtitle", "badge", "icon", "body"]:
            if key in offsets:
                obj = offsets[key]
                if "x" in obj: obj["x"] *= scale
                if "y" in obj: obj["y"] *= scale
                if "w" in obj: obj["w"] *= scale
                if "h" in obj: obj["h"] *= scale
                if "size" in obj: obj["size"] *= scale
                if "scale" in obj: obj["scale"] *= scale



def _run_legacy_node_placement(
    ir: dict,
    nodes: list[dict],
    nodes_map: dict[str, dict],
    connections: list[dict],
    toplevel_nodes: list[dict],
    toplevel_ids: set[str],
    canvas_mode: str,
    canvas_w: float,
    canvas_h: float
) -> None:
        for node in nodes:
            if node.get("x") is None:
                node.pop("x", None)
            if node.get("y") is None:
                node.pop("y", None)

        # ── Step 1: Layout children inside each panel bottom-up ──────────
        visited_panels = set()

        def layout_panel_hierarchical(panel_id: str, n_map: dict[str, dict]) -> None:
            if panel_id in visited_panels:
                return
            visited_panels.add(panel_id)
            panel = n_map[panel_id]
            for cid in panel.get("children", []):
                child = n_map.get(cid)
                if child and child.get("type") == "panel":
                    layout_panel_hierarchical(cid, n_map)
            layout_panel_children(panel, n_map)

        toplevel_panels = [n for n in toplevel_nodes if n.get("type") == "panel"]
        for panel in toplevel_panels:
            layout_panel_hierarchical(panel["id"], nodes_map)

        # Also handle nested panels not reached under top-level panels
        nested_panels = [
            n for n in nodes
            if n.get("type") == "panel" and n.get("parent") is not None
        ]
        for panel in nested_panels:
            layout_panel_hierarchical(panel["id"], nodes_map)

        # ── Step 2: Position top-level elements based on canvas mode ─────
        fixed_toplevel_ids = {
            nid for nid in toplevel_ids
            if nodes_map[nid].get("x") is not None and nodes_map[nid].get("y") is not None
        }
        unpositioned_toplevel_ids = toplevel_ids - fixed_toplevel_ids

        if canvas_mode == "absolute":
            # Keep nodes at specified coordinates, default to (0,0) if completely missing
            for nid in toplevel_ids:
                node = nodes_map[nid]
                if node.get("x") is None:
                    node["x"] = 0.0
                if node.get("y") is None:
                    node["y"] = 0.0

        elif canvas_mode == "graph":
            # Graph Mode: Compound force-directed layout solver
            try:
                import networkx as nx
                G = nx.Graph()
                for nid in toplevel_ids:
                    G.add_node(nid)
                for conn in connections:
                    path = conn.get("path", [])
                    if not path and "from" in conn and "to" in conn:
                        path = [conn["from"], conn["to"]]
                    if isinstance(path, str):
                        path = [path]
                    for a, b in zip(path, path[1:]):
                        ta = _resolve_to_toplevel(a, nodes_map)
                        tb = _resolve_to_toplevel(b, nodes_map)
                        if ta != tb and ta in toplevel_ids and tb in toplevel_ids:
                            G.add_edge(ta, tb)

                initial_pos = {}
                fixed_nodes_list = []
                for nid in toplevel_ids:
                    node = nodes_map[nid]
                    if nid in fixed_toplevel_ids:
                        initial_pos[nid] = [float(node["x"]), float(node["y"])]
                        fixed_nodes_list.append(nid)
                    else:
                        initial_pos[nid] = [canvas_w / 2.0, canvas_h / 2.0]

                pos = nx.spring_layout(G, pos=initial_pos, fixed=fixed_nodes_list or None, k=300.0, iterations=100, seed=42)

                for nid in toplevel_ids:
                    node = nodes_map[nid]
                    # spring_layout updates coordinates for both fixed and free nodes
                    node["x"] = pos[nid][0]
                    node["y"] = pos[nid][1]

            except ImportError:
                # Fallback deterministic pure Python spring/force-directed relaxation
                pos = {}
                for nid in toplevel_ids:
                    node = nodes_map[nid]
                    if nid in fixed_toplevel_ids:
                        pos[nid] = [float(node["x"]), float(node["y"])]
                    else:
                        # Deterministic spread using hash or index to avoid overlap starting positions
                        pos[nid] = [
                            canvas_w / 2.0 + (hash(nid) % 100 - 50),
                            canvas_h / 2.0 + (hash(nid) % 100 - 50)
                        ]

                for _ in range(100):
                    forces = {nid: [0.0, 0.0] for nid in toplevel_ids}
                    # Repulsion
                    for u in toplevel_ids:
                        for v in toplevel_ids:
                            if u == v:
                                continue
                            dx = pos[u][0] - pos[v][0]
                            dy = pos[u][1] - pos[v][1]
                            dist = math.hypot(dx, dy) + 0.1
                            fr = 10000.0 / (dist * dist)
                            forces[u][0] += (dx / dist) * fr
                            forces[u][1] += (dy / dist) * fr
                    # Attraction
                    for conn in connections:
                        path = conn.get("path", [])
                        if not path and "from" in conn and "to" in conn:
                            path = [conn["from"], conn["to"]]
                        if isinstance(path, str):
                            path = [path]
                        for a, b in zip(path, path[1:]):
                            ta = _resolve_to_toplevel(a, nodes_map)
                            tb = _resolve_to_toplevel(b, nodes_map)
                            if ta != tb and ta in toplevel_ids and tb in toplevel_ids:
                                dx = pos[tb][0] - pos[ta][0]
                                dy = pos[tb][1] - pos[ta][1]
                                dist = math.hypot(dx, dy) + 0.1
                                fa = 0.1 * dist
                                forces[ta][0] += (dx / dist) * fa
                                forces[ta][1] += (dy / dist) * fa
                                forces[tb][0] -= (dx / dist) * fa
                                forces[tb][1] -= (dy / dist) * fa
                    # Update non-fixed nodes
                    for nid in toplevel_ids:
                        if nid in fixed_toplevel_ids:
                            continue
                        fx, fy = forces[nid]
                        f_mag = math.hypot(fx, fy)
                        if f_mag > 20.0:
                            fx = (fx / f_mag) * 20.0
                            fy = (fy / f_mag) * 20.0
                        pos[nid][0] += fx
                        pos[nid][1] += fy

                for nid in toplevel_ids:
                    node = nodes_map[nid]
                    node["x"] = pos[nid][0]
                    node["y"] = pos[nid][1]

        else:
            # Dynamic Mode (Default auto-layout with topological tier placement)
            if unpositioned_toplevel_ids:
                _auto_layout_toplevel(unpositioned_toplevel_ids, nodes_map, connections, fixed_toplevel_ids)

        # ── Step 3: Position free elements ───────────────────────────────
        _position_free_elements(nodes, nodes_map, connections)

        # ── Step 3b: Fit top-level elements spacing to canvas ────────────
        # For absolute mode, we might not want to scale/shrink coordinate values,
        # but _fit_to_canvas handles scaling if it exceeds canvas bounds. Let's keep it.
        has_title = bool(ir.get("title"))
        canvas_mode = ir.get("canvas", {}).get("mode", "dynamic")
        _fit_to_canvas(nodes, canvas_w, canvas_h, has_title=has_title, scale_to_fit=False)

        # ── Step 4: Convert child positions to absolute recursively (Pass 5) ─
        _absolutize_children(nodes, nodes_map)

def layout(
    ir: dict,
    canvas_w: int = 1920,
    canvas_h: int = 1440,
) -> dict:
    """Assign absolute (x, y) positions to every node in the IR.

    This is the main entry point of the layout engine.

    Pipeline:
    1. **Pass 4: Hierarchical Layout Solver**
       - Bottom-up panel solvers.
       - Top-level solver based on mode (absolute, dynamic, graph).
       - Fixed constraint anchoring and out-of-flow inflation.
    2. **Pass 5: Structural Absolutizer**
       - Pre-Order DFS recursive coordinate absolutization.
       - Centering layout on target canvas.
    """
    nodes: list[dict] = ir.get("nodes", [])
    nodes = [n for n in nodes if not n["id"].startswith("decor_")]
    ir["nodes"] = nodes
    connections: list[dict] = ir.get("connections", [])
    annotations: list[dict] = ir.get("annotations", [])

    # ── Read canvas from IR meta if available ────────────────────────
    canvas_meta = ir.get("canvas", {})
    canvas_w = canvas_meta.get("width", canvas_w)
    canvas_h = canvas_meta.get("height", canvas_h)
    canvas_mode = canvas_meta.get("mode", "dynamic")
    has_title = bool(ir.get("title"))

    # ── Build lookup ─────────────────────────────────────────────────
    nodes_map: dict[str, dict] = {n["id"]: n for n in nodes}

    # ── Identify top-level vs. child nodes ───────────────────────────
    toplevel_nodes = [n for n in nodes if n.get("parent") is None]
    toplevel_ids = {n["id"] for n in toplevel_nodes}

    # Clear any stale coordinates (compiler sets x/y = None)

    # ── Try ELK layout engine first (for graph/dynamic auto-layout) ──
    elk_success = False
    has_fixed_nodes = any(
        n.get("x") is not None and n.get("y") is not None
        for n in nodes
    )
    if canvas_mode != "absolute" and not has_fixed_nodes:
        from .elk_layout import route_with_elk
        elk_success = route_with_elk(ir)

    if not elk_success:
        _run_legacy_node_placement(
            ir, nodes, nodes_map, connections, toplevel_nodes, toplevel_ids,
            canvas_mode, canvas_w, canvas_h
        )

    # ── Step 4b: Uniform Scaling (if not in dynamic canvas mode) ─────
    if canvas_mode != "dynamic":
        positioned = [
            n for n in nodes
            if n.get("parent") is None and n.get("x") is not None and n.get("y") is not None
        ]
        if positioned:
            min_x = min(n["x"] for n in positioned)
            min_y = min(n["y"] for n in positioned)
            max_x = max(n["x"] + n["width"] for n in positioned)
            max_y = max(n["y"] + n["height"] for n in positioned)
            
            content_w = max_x - min_x
            content_h = max_y - min_y
            
            margin = 18.0
            avail_w = canvas_w - 2 * margin
            if has_title:
                avail_h = canvas_h - 130.0 - 2 * margin
            else:
                avail_h = canvas_h - 2 * margin
                
            if content_w > 0 and content_h > 0:
                scale_x = min(1.0, avail_w / content_w)
                scale_y = min(1.0, avail_h / content_h)
                scale = min(scale_x, scale_y)
                
                if scale < 1.0:
                    _scale_layout_uniformly(nodes, scale)
                    nodes_map = {n["id"]: n for n in nodes}

    # ── Step 5: Center entire diagram on the target canvas (Pass 5) ──
    has_title = bool(ir.get("title"))
    if canvas_mode == "dynamic":
        positioned = [
            n for n in nodes
            if n.get("parent") is None and n.get("x") is not None and n.get("y") is not None
        ]
        if positioned:
            min_x = min(n["x"] for n in positioned)
            min_y = min(n["y"] for n in positioned)
            margin = 18.0
            target_x = margin + 10.0
            target_y = 135.0 if has_title else margin + 10.0
            
            dx = target_x - min_x
            dy = target_y - min_y
            
            for node in nodes:
                if node.get("x") is not None:
                    node["x"] += dx
                if node.get("y") is not None:
                    node["y"] += dy
            
            max_x = max(n["x"] + n["width"] for n in positioned)
            max_y = max(n["y"] + n["height"] for n in positioned)
            
            canvas_w = max(800.0 if has_title else 100.0, max_x + margin)
            canvas_h = max(200.0 if has_title else 100.0, max_y + margin)
            
            if "canvas" not in ir:
                ir["canvas"] = {}
            ir["canvas"]["width"] = int(math.ceil(canvas_w))
            ir["canvas"]["height"] = int(math.ceil(canvas_h))
    else:
        _center_layout_on_canvas(nodes, canvas_w, canvas_h, has_title=has_title)

    # Rebuild nodes_map after centering because we need correct absolute x, y
    nodes_map = {n["id"]: n for n in nodes}
    canvas_w = ir.get("canvas", {}).get("width", canvas_w)
    canvas_h = ir.get("canvas", {}).get("height", canvas_h)

    # ── Step 5b: Edge Routing and Label Injection (Pass 6) ───────────
    existing_label_boxes = []
    for conn in connections:
        src_id = conn.get("from")
        tgt_id = conn.get("to")
        src_node = nodes_map.get(src_id)
        tgt_node = nodes_map.get(tgt_id)
        if not src_node or not tgt_node:
            continue
            
        from_port = conn.get("fromPort", conn.get("exitPort", "bottom"))
        to_port = conn.get("toPort", conn.get("entryPort", "top"))
        
        src_center = (src_node["x"] + src_node["width"] / 2.0, src_node["y"] + src_node["height"] / 2.0)
        tgt_center = (tgt_node["x"] + tgt_node["width"] / 2.0, tgt_node["y"] + tgt_node["height"] / 2.0)
        
        p_start = get_shape_port_coords(src_node, from_port, tgt_center)
        p_end = get_shape_port_coords(tgt_node, to_port, src_center)
        
        # Define dynamic obstacle exclusions: exclude the src/tgt nodes and any of their ancestor panels
        excluded_ids = {src_id, tgt_id}
        for nid in (src_id, tgt_id):
            curr = nodes_map.get(nid)
            while curr and curr.get("parent"):
                excluded_ids.add(curr["parent"])
                curr = nodes_map.get(curr["parent"])
        obstacles = [n for n in nodes if n["id"] not in excluded_ids and not n["id"].startswith("decor_") and n.get("type") != "panel"]
        
        # Run A* or fallback (exclude src_node and tgt_node from soft_cards so start and end port cells are not penalized)
        soft_cards = []
        soft_panels = [n for n in nodes if n.get("type") == "panel" and n["id"] not in excluded_ids]
        for nid in (src_id, tgt_id):
            curr = nodes_map.get(nid)
            if curr and curr.get("parent"):
                p_node = nodes_map.get(curr["parent"])
                if p_node and p_node not in soft_panels:
                    soft_panels.append(p_node)
        
        routed_points = route_orthogonal_astar(
            p_start, p_end, obstacles, canvas_w, canvas_h,
            soft_cards=soft_cards, soft_panels=soft_panels
        )
        if not routed_points:
            routed_points = fallback_orthogonal_route(p_start, p_end)
            
        conn["points"] = routed_points
        
        # Position label
        conn_label = conn.get("label")
        if conn_label:
            lbl_x, lbl_y = position_connection_label(routed_points, conn_label, nodes, existing_label_boxes)
            existing_label_boxes.append((lbl_x - 50.0, lbl_y - 10.0, lbl_x + 50.0, lbl_y + 10.0))
            conn["layout_offsets"] = {
                "label": {
                    "x": lbl_x,
                    "y": lbl_y
                }
            }

    # ── Step 5c: Resolve target-attached and midpoint annotations ───
    resolve_annotations_positions(annotations, nodes_map, connections)

    # ── Step 6: Position annotations ─────────────────────────────────
    _position_annotations(annotations, nodes)

    # ── Step 7: Inject page layout decorations (Pass 7) ──────────────
    if nodes:
        raw_title = ir.get("title")
        if isinstance(raw_title, str):
            title_spec = {"highlight": raw_title}
        elif isinstance(raw_title, dict):
            title_spec = raw_title
        else:
            title_spec = {}
            
        highlight_text = title_spec.get("highlight", "") if isinstance(title_spec, dict) else ""
        prefix_text    = title_spec.get("prefix", "") if isinstance(title_spec, dict) else ""
        subtitle_text  = title_spec.get("subtitle", "") if isinstance(title_spec, dict) else ""
        
        # Outer border
        all_elements = nodes + annotations
        xs = [n["x"] for n in all_elements if n.get("x") is not None]
        ys = [n["y"] for n in all_elements if n.get("y") is not None]
        rights = [n["x"] + n["width"] for n in all_elements if n.get("x") is not None and n.get("width") is not None]
        bottoms = [n["y"] + n["height"] for n in all_elements if n.get("y") is not None and n.get("height") is not None]
        
        min_x = min(xs) if xs else 50.0
        min_y = min(ys) if ys else 117.0
        max_x = max(rights) if rights else canvas_w - 50.0
        max_y = max(bottoms) if bottoms else canvas_h - 50.0
        
        has_title = bool(title_spec)
        outer_border_x = max(0.0, min(18.0, canvas_w - 10.0))
        outer_border_y = max(135.0, min_y - 20.0) if has_title else max(18.0, min_y - 20.0)
        outer_border_y = max(0.0, min(outer_border_y, canvas_h - 10.0))
        
        outer_border_w = max(canvas_w - 36.0, max_x + 20.0 - outer_border_x)
        outer_border_h = max(canvas_h - 18.0 - outer_border_y, max_y + 20.0 - outer_border_y)
        
        if outer_border_x + outer_border_w > canvas_w:
            outer_border_w = max(10.0, canvas_w - outer_border_x)
        if outer_border_y + outer_border_h > canvas_h:
            outer_border_h = max(10.0, canvas_h - outer_border_y)
        
        border_node = {
            "id": "decor_outer_border",
            "type": "panel",
            "x": outer_border_x,
            "y": outer_border_y,
            "width": outer_border_w,
            "height": outer_border_h,
            "title": "",
            "subtitle": "",
            "badge": "",
            "children": [],
            "_resolved_style": {
                "strokeColor": THEME["frame"],
                "fillColor": None,
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "cornerRadius": 29,
            },
            "layout_offsets": {}
        }
        nodes.append(border_node)
        
        hand_val = ir.get("hand", True)
        
        if title_spec:
            # Line (represented as card)
            line_node = {
                "id": "decor_title_line",
                "type": "card",
                "x": 23.5,
                "y": 31.0,
                "width": 11.0,
                "height": 47.0,
                "title": "",
                "body": "",
                "_resolved_style": {
                    "fillColor": THEME["purple"],
                    "strokeColor": THEME["purple"],
                    "strokeWidth": 0,
                    "cornerRadius": 0
                },
                "layout_offsets": {}
            }
            nodes.append(line_node)
            
            # Prefix text
            if prefix_text:
                prefix_node = {
                    "id": "decor_title_prefix",
                    "type": "label",
                    "x": 45.0,
                    "y": 14.0,
                    "width": 535.0,
                    "height": 66.0,
                    "title": prefix_text,
                    "_resolved_style": {
                        "strokeColor": THEME["white"],
                        "strokeWidth": 0,
                        "bold": True,
                        "hand": hand_val
                    },
                    "layout_offsets": {
                        "title": {
                            "x": 0.0, "y": 0.0, "w": 535.0, "h": 66.0,
                            "size": 47.0, "min_size": 12, "bold": True, "hand": hand_val, "align": "left"
                        }
                    }
                }
                nodes.append(prefix_node)
                
            # Highlight text card
            if highlight_text:
                draw_scratch = _scratch_draw()
                _hl_font = load_font(44, hand=hand_val, bold=True)
                _hl_tw, _ = text_size(draw_scratch, highlight_text, _hl_font)
                _hl_tw = max(int(_hl_tw / SCALE), 200)
                _hl_pad_x = 22.0
                
                if prefix_text:
                    _pref_font = load_font(47, hand=hand_val, bold=True)
                    _pref_tw, _ = text_size(draw_scratch, prefix_text, _pref_font)
                    _pref_tw_scaled = _pref_tw / SCALE
                    hl_rect_x = max(600.0, float(45.0 + _pref_tw_scaled + 20.0))
                else:
                    hl_rect_x = 45.0
                hl_rect_w = float(_hl_tw + _hl_pad_x * 2)
                hl_rect_y = 27.0
                hl_rect_h = 72.0
                
                highlight_node = {
                    "id": "decor_title_highlight",
                    "type": "card",
                    "x": hl_rect_x,
                    "y": hl_rect_y,
                    "width": hl_rect_w,
                    "height": hl_rect_h,
                    "title": highlight_text,
                    "body": "",
                    "_resolved_style": {
                        "fillColor": THEME["highlight"],
                        "strokeColor": THEME["highlight"],
                        "strokeWidth": 2,
                        "cornerRadius": 16,
                        "bold": True,
                        "hand": hand_val
                    },
                    "layout_offsets": {
                        "title": {
                            "x": _hl_pad_x, "y": 19.0 - hl_rect_y, "w": hl_rect_w - _hl_pad_x * 2, "h": 76.0,
                            "size": 44.0, "min_size": 12, "bold": True, "hand": hand_val, "align": "center"
                        }
                    }
                }
                nodes.append(highlight_node)
                
            # Subtitle
            if subtitle_text:
                subtitle_node = {
                    "id": "decor_title_subtitle",
                    "type": "label",
                    "x": 104.0,
                    "y": 90.0,
                    "width": 420.0,
                    "height": 25.0,
                    "title": subtitle_text,
                    "_resolved_style": {
                        "strokeColor": THEME["muted"],
                        "strokeWidth": 0,
                        "bold": False,
                        "hand": hand_val
                    },
                    "layout_offsets": {
                        "title": {
                            "x": 0.0, "y": 0.0, "w": 420.0, "h": 25.0,
                            "size": 15.0, "min_size": 9, "bold": False, "hand": hand_val, "align": "left"
                        }
                    }
                }
                nodes.append(subtitle_node)
                
        # Watermark brand signature
        signature = ir.get("signature", "@FlowDraft")
        bw = 255.0
        bh = 40.0
        bx = (outer_border_x + outer_border_w) - bw
        by = 143.0
        if bx < 600.0:
            bx = canvas_w - 270.0
            
        bx = max(0.0, min(bx, canvas_w - bw))
        by = max(0.0, min(by, canvas_h - bh))
            
        brand_node = {
            "id": "decor_brand",
            "type": "decor_brand",
            "x": bx,
            "y": by,
            "signature": signature,
            "width": bw,
            "height": bh,
            "layout_offsets": {}
        }
        nodes.append(brand_node)

    return ir


# ═══════════════════════════════════════════════════════════════════════════
# Helpers for shape-aware docking, orthogonal routing, and annotations (Pass 6)
# ═══════════════════════════════════════════════════════════════════════════

def _get_node_corner_radius(node: dict) -> float:
    ntype = node.get("type", "card")
    style = node.get("_resolved_style") or node.get("style") or {}
    cr = style.get("cornerRadius")
    if cr is not None:
        return float(cr)
    if ntype == "panel":
        return 20.0
    if ntype == "input":
        return 8.0
    if ntype == "label":
        return 0.0
    return 12.0


def get_shape_port_coords(node: dict, port_name: str, target_center: tuple[float, float] = None) -> tuple[float, float]:
    x: float = node.get("x", 0.0) or 0.0
    y: float = node.get("y", 0.0) or 0.0
    w: float = node.get("width", 1.0) or 1.0
    h: float = node.get("height", 1.0) or 1.0
    xc = x + w / 2
    yc = y + h / 2

    # Map port name to angle
    angles = {
        "right": 0.0,
        "bottom-right": math.pi / 4,
        "bottom": math.pi / 2,
        "bottom-left": 3 * math.pi / 4,
        "left": math.pi,
        "top-left": -3 * math.pi / 4,
        "top": -math.pi / 2,
        "top-right": -math.pi / 4,
    }
    
    port_name = port_name.lower()
    theta = angles.get(port_name)
    if theta is None:
        if target_center:
            theta = math.atan2(target_center[1] - yc, target_center[0] - xc)
        else:
            theta = 0.0
            
    ntype = node.get("type", "card")
    
    if ntype in ("ellipse", "circle"):
        a = w / 2
        b = h / 2
        return (xc + a * math.cos(theta), yc + b * math.sin(theta))
        
    elif ntype == "diamond":
        a = w / 2
        b = h / 2
        denom = abs(math.cos(theta)) / a + abs(math.sin(theta)) / b
        if denom == 0:
            return (xc, yc)
        r = 1.0 / denom
        return (xc + r * math.cos(theta), yc + r * math.sin(theta))
        
    else:
        # Panel, Card, Input, Label, etc. - Rounded Rectangle
        cr = _get_node_corner_radius(node)
        cr = max(0.0, min(cr, w / 2.0, h / 2.0))
        
        # Intersect ray with rounded rect
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        
        lambda_x = (w / 2) / abs(cos_t) if abs(cos_t) > 1e-9 else float('inf')
        lambda_y = (h / 2) / abs(sin_t) if abs(sin_t) > 1e-9 else float('inf')
        lam = min(lambda_x, lambda_y)
        
        px = xc + lam * cos_t
        py = yc + lam * sin_t
        
        # Check if intersection is in any of the corners
        if px > xc + w / 2 - cr and py < yc - h / 2 + cr:
            cx = xc + w / 2 - cr
            cy = yc - h / 2 + cr
            return intersect_circle_corner(xc, yc, cx, cy, cr, theta)
        elif px > xc + w / 2 - cr and py > yc + h / 2 - cr:
            cx = xc + w / 2 - cr
            cy = yc + h / 2 - cr
            return intersect_circle_corner(xc, yc, cx, cy, cr, theta)
        elif px < xc - w / 2 + cr and py > yc + h / 2 - cr:
            cx = xc - w / 2 + cr
            cy = yc + h / 2 - cr
            return intersect_circle_corner(xc, yc, cx, cy, cr, theta)
        elif px < xc - w / 2 + cr and py < yc - h / 2 + cr:
            cx = xc - w / 2 + cr
            cy = yc - h / 2 + cr
            return intersect_circle_corner(xc, yc, cx, cy, cr, theta)
        else:
            return (px, py)


def intersect_circle_corner(xc: float, yc: float, cx: float, cy: float, cr: float, theta: float) -> tuple[float, float]:
    ux = xc - cx
    uy = yc - cy
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    
    B = ux * cos_t + uy * sin_t
    C_quad = ux**2 + uy**2 - cr**2
    disc = B**2 - C_quad
    if disc >= 0:
        lam = -B + math.sqrt(disc)
        return (xc + lam * cos_t, yc + lam * sin_t)
    return (xc + B * cos_t, yc + B * sin_t)


def simplify_orthogonal_path(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not path:
        return path
    # Deduplicate consecutive identical points first
    cleaned = [path[0]]
    for p in path[1:]:
        if math.hypot(p[0] - cleaned[-1][0], p[1] - cleaned[-1][1]) > 1e-3:
            cleaned.append(p)
    if len(cleaned) <= 2:
        return cleaned

    simplified = [cleaned[0]]
    for i in range(1, len(cleaned) - 1):
        prev = simplified[-1]
        curr = cleaned[i]
        nxt = cleaned[i+1]
        
        is_collinear_h = (abs(prev[1] - curr[1]) < 1e-3 and abs(curr[1] - nxt[1]) < 1e-3)
        is_collinear_v = (abs(prev[0] - curr[0]) < 1e-3 and abs(curr[0] - nxt[0]) < 1e-3)
        
        if not (is_collinear_h or is_collinear_v):
            simplified.append(curr)
    simplified.append(cleaned[-1])

    # Final cleanup of consecutive duplicates after collinear removal
    final_pts = [simplified[0]]
    for p in simplified[1:]:
        if math.hypot(p[0] - final_pts[-1][0], p[1] - final_pts[-1][1]) > 1e-3:
            final_pts.append(p)
    return final_pts


def route_orthogonal_astar(
    p_start: tuple[float, float],
    p_end: tuple[float, float],
    obstacles: list[dict],
    canvas_w: float,
    canvas_h: float,
    grid_size: float = 8.0,
    clearance: float = 6.0,
    soft_cards: list[dict] = [],
    soft_panels: list[dict] = [],
) -> list[tuple[float, float]] | None:
    start_gx = int(round(p_start[0] / grid_size))
    start_gy = int(round(p_start[1] / grid_size))
    end_gx = int(round(p_end[0] / grid_size))
    end_gy = int(round(p_end[1] / grid_size))
    
    min_gx = -5
    max_gx = int(canvas_w / grid_size) + 5
    min_gy = -5
    max_gy = int(canvas_h / grid_size) + 5

    grid_obstacles = []
    for obs in obstacles:
        ox = obs.get("x", 0.0) or 0.0
        oy = obs.get("y", 0.0) or 0.0
        ow = obs.get("width", 1.0) or 1.0
        oh = obs.get("height", 1.0) or 1.0
        
        x1 = ox - clearance
        y1 = oy - clearance
        x2 = ox + ow + clearance
        y2 = oy + oh + clearance
        
        g_x1 = int(math.floor(x1 / grid_size))
        g_y1 = int(math.floor(y1 / grid_size))
        g_x2 = int(math.ceil(x2 / grid_size))
        g_y2 = int(math.ceil(y2 / grid_size))
        grid_obstacles.append((g_x1, g_y1, g_x2, g_y2))
        
    soft_cards_grid = []
    for obs in soft_cards:
        ox = obs.get("x", 0.0) or 0.0
        oy = obs.get("y", 0.0) or 0.0
        ow = obs.get("width", 1.0) or 1.0
        oh = obs.get("height", 1.0) or 1.0
        
        g_x1 = int(math.floor(ox / grid_size))
        g_y1 = int(math.floor(oy / grid_size))
        g_x2 = int(math.ceil((ox + ow) / grid_size))
        g_y2 = int(math.ceil((oy + oh) / grid_size))
        soft_cards_grid.append((g_x1, g_y1, g_x2, g_y2))
        
    soft_panels_grid = []
    for obs in soft_panels:
        ox = obs.get("x", 0.0) or 0.0
        oy = obs.get("y", 0.0) or 0.0
        ow = obs.get("width", 1.0) or 1.0
        oh = obs.get("height", 1.0) or 1.0
        
        g_x1 = int(math.floor(ox / grid_size))
        g_y1 = int(math.floor(oy / grid_size))
        g_x2 = int(math.ceil((ox + ow) / grid_size))
        g_y2 = int(math.ceil((oy + oh) / grid_size))
        soft_panels_grid.append((g_x1, g_y1, g_x2, g_y2))
        
    def is_blocked(gx, gy):
        if (gx, gy) == (start_gx, start_gy) or (gx, gy) == (end_gx, end_gy):
            return False
        for g_x1, g_y1, g_x2, g_y2 in grid_obstacles:
            if g_x1 <= gx <= g_x2 and g_y1 <= gy <= g_y2:
                return True
        return False

    queue = []
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        h = abs(start_gx - end_gx) + abs(start_gy - end_gy)
        heapq.heappush(queue, (h, 0.0, start_gx, start_gy, dx, dy, [(start_gx, start_gy)]))
        
    visited = {}
    
    while queue:
        f, g, gx, gy, dx, dy, path = heapq.heappop(queue)
        
        if (gx, gy) == (end_gx, end_gy):
            canvas_path = [p_start]
            for pgx, pgy in path[1:-1]:
                canvas_path.append((pgx * grid_size, pgy * grid_size))
            canvas_path.append(p_end)
            return simplify_orthogonal_path(canvas_path)
            
        state_key = (gx, gy, dx, dy)
        if state_key in visited and visited[state_key] <= g:
            continue
        visited[state_key] = g
        
        for ndx, ndy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            if ndx == -dx and ndy == -dy:
                continue
                
            ngx = gx + ndx
            ngy = gy + ndy
            
            if not (min_gx <= ngx <= max_gx and min_gy <= ngy <= max_gy):
                continue
                
            if is_blocked(ngx, ngy):
                continue
                
            is_soft_card = False
            for sx1, sy1, sx2, sy2 in soft_cards_grid:
                if sx1 <= ngx <= sx2 and sy1 <= ngy <= sy2:
                    is_soft_card = True
                    break
            
            is_soft_panel = False
            if not is_soft_card:
                for sx1, sy1, sx2, sy2 in soft_panels_grid:
                    if sx1 <= ngx <= sx2 and sy1 <= ngy <= sy2:
                        is_soft_panel = True
                        break
            
            soft_penalty = 0.0
            if is_soft_card:
                soft_penalty = 100000.0
            elif is_soft_panel:
                soft_penalty = 100.0
            turn_penalty = 15.0 if (ndx != dx or ndy != dy) else 0.0
            new_g = g + 1.0 + turn_penalty + soft_penalty
            
            h = abs(ngx - end_gx) + abs(ngy - end_gy)
            new_f = new_g + h
            
            heapq.heappush(queue, (new_f, new_g, ngx, ngy, ndx, ndy, path + [(ngx, ngy)]))
            
    return None


def fallback_orthogonal_route(p_start: tuple[float, float], p_end: tuple[float, float]) -> list[tuple[float, float]]:
    if abs(p_start[0] - p_end[0]) > 1 and abs(p_start[1] - p_end[1]) > 1:
        mid_y = (p_start[1] + p_end[1]) / 2
        return [
            p_start,
            (p_start[0], mid_y),
            (p_end[0], mid_y),
            p_end,
        ]
    else:
        return [p_start, p_end]


def position_connection_label(
    path_points: list[tuple[float, float]],
    conn_label: str,
    nodes: list[dict],
    existing_label_boxes: list[tuple[float, float, float, float]],
) -> tuple[float, float]:
    mid_pt = point_at_fraction(path_points, 0.5)
    
    mid_segment_idx = 0
    total_len = path_len(path_points)
    target_dist = total_len * 0.5
    
    curr_dist = 0.0
    for i in range(len(path_points) - 1):
        p0 = path_points[i]
        p1 = path_points[i+1]
        seg_len = math.dist(p0, p1)
        if curr_dist + seg_len >= target_dist:
            mid_segment_idx = i
            break
        curr_dist += seg_len
        
    p0 = path_points[mid_segment_idx]
    p1 = path_points[mid_segment_idx+1]
    
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    seg_len = math.dist(p0, p1)
    
    if seg_len > 1e-9:
        ux = dx / seg_len
        uy = dy / seg_len
    else:
        ux = 1.0
        uy = 0.0
        seg_len = 0.0
        
    if abs(ux) > abs(uy):
        nx, ny = 0.0, -1.0
    else:
        nx, ny = 1.0, 0.0
        
    offset_val = 12.0
    lbl_x = mid_pt[0] + offset_val * nx
    lbl_y = mid_pt[1] + offset_val * ny
    
    lbl_w = 100.0
    lbl_h = 20.0
    
    obstacles = []
    for node in nodes:
        if node.get("type") != "panel":
            obstacles.append((
                node["x"],
                node["y"],
                node["x"] + node["width"],
                node["y"] + node["height"]
            ))
            
    def collides(lx, ly):
        lbox = (lx - lbl_w / 2, ly - lbl_h / 2, lx + lbl_w / 2, ly + lbl_h / 2)
        for ox1, oy1, ox2, oy2 in obstacles:
            if not (lbox[2] < ox1 or lbox[0] > ox2 or lbox[3] < oy1 or lbox[1] > oy2):
                return True
        for elbox in existing_label_boxes:
            if not (lbox[2] < elbox[0] or lbox[0] > elbox[2] or lbox[3] < elbox[1] or lbox[1] > elbox[3]):
                return True
        return False
        
    best_x, best_y = lbl_x, lbl_y
    if collides(lbl_x, lbl_y):
        max_slide = min(50.0, seg_len / 2)
        steps = [s for s in range(5, int(max_slide) + 1, 5)]
        slide_steps = []
        for step in steps:
            slide_steps.extend([step, -step])
            
        for s in slide_steps:
            candidate_x = lbl_x + s * ux
            candidate_y = lbl_y + s * uy
            if not collides(candidate_x, candidate_y):
                best_x, best_y = candidate_x, candidate_y
                break
                
    return best_x, best_y


def resolve_annotations_positions(
    annotations: list[dict],
    nodes_map: dict[str, dict],
    connections: list[dict],
) -> None:
    conn_map = {}
    for conn in connections:
        src = conn.get("from")
        tgt = conn.get("to")
        if src and tgt:
            conn_map[(src, tgt)] = conn

    for ann in annotations:
        if ann.get("x") is not None and ann.get("y") is not None:
            continue
            
        ax, ay = None, None
        
        ann_from = ann.get("from")
        ann_to = ann.get("to")
        if ann_from and ann_to:
            conn = conn_map.get((ann_from, ann_to))
            if conn and conn.get("points"):
                pts = [tuple(p) for p in conn["points"]]
                mid_pt = point_at_fraction(pts, 0.5)
                ax, ay = mid_pt[0], mid_pt[1]
                
        if ax is None or ay is None:
            target_id = ann.get("attachTo") or ann.get("target")
            target = nodes_map.get(target_id) if target_id else None
            if target:
                x = target["x"]
                y = target["y"]
                w = target["width"]
                h = target["height"]
                xc = x + w / 2
                yc = y + h / 2
                
                pos = ann.get("position", "top").lower()
                if pos in ("center", "midpoint"):
                    ax, ay = xc, yc
                elif pos in ("top", "top-label"):
                    ax, ay = xc, y - 15
                elif pos == "bottom":
                    ax, ay = xc, y + h + 15
                elif pos == "left":
                    ax, ay = x - 15, yc
                elif pos == "right":
                    ax, ay = x + w + 15, yc
                elif pos == "top-left":
                    ax, ay = x + 100, y - 15
                elif pos == "top-right":
                    ax, ay = x + w - 100, y - 15
                elif pos == "bottom-left":
                    ax, ay = x + 100, y + h + 15
                elif pos == "bottom-right":
                    ax, ay = x + w - 100, y + h + 15
                else:
                    ax, ay = xc, y - 15
                    
        if ax is not None and ay is not None:
            offset = ann.get("offset", {})
            ax += offset.get("dx", 0)
            ay += offset.get("dy", 0)
            ann["x"] = ax
            ann["y"] = ay

