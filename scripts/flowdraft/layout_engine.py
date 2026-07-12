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
from collections import defaultdict, deque
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

_CANVAS_MARGIN: float = 50.0          # px margin on all sides
_PANEL_GAP_H: float = 40.0           # horizontal gap between top-level elements
_PANEL_GAP_V: float = 35.0           # vertical gap between tiers
_FREE_ELEMENT_GAP: float = 30.0      # gap when placing free elements next to peers

# Default panel inner-layout values (used when panel has no layout dict)
_DEFAULT_DIRECTION: str = "row"
_DEFAULT_GAP: float = 16.0
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
        0 — "input tier": panels whose children are all type ``input``.
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

    # Tier 0: input panels (children are all inputs)
    if ntype == "panel" and child_types and child_types <= {"input"}:
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
                "left":   pad.get("left", 20),
                "right":  pad.get("right", 20),
                "top":    pad.get("top", 60),
                "bottom": pad.get("bottom", 20),
            }

    # 2. Try _resolved_style (set by compiler)
    style = panel.get("_resolved_style", {})
    pad = style.get("padding")
    if isinstance(pad, dict):
        return {
            "left":   pad.get("left", 20),
            "right":  pad.get("right", 20),
            "top":    pad.get("top", 60),
            "bottom": pad.get("bottom", 20),
        }

    # 3. Try explicit style.padding
    explicit_style = panel.get("style", {})
    pad = explicit_style.get("padding")
    if isinstance(pad, dict):
        return {
            "left":   pad.get("left", 20),
            "right":  pad.get("right", 20),
            "top":    pad.get("top", 60),
            "bottom": pad.get("bottom", 20),
        }

    return {"left": 20, "right": 20, "top": 60, "bottom": 20}


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


def _layout_row(
    child_ids: list[str],
    nodes_map: dict[str, dict],
    gap: float,
    origin_x: float,
    origin_y: float,
) -> tuple[float, float]:
    """Lay children out left-to-right in a single row.

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Horizontal gap between children.
        origin_x:  X start for first child.
        origin_y:  Y start for first child.

    Returns:
        ``(total_width, max_height)`` of the row.
    """
    cursor_x = origin_x
    max_h: float = 0.0

    for i, cid in enumerate(child_ids):
        child = nodes_map.get(cid)
        if child is None:
            continue
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
) -> tuple[float, float]:
    """Lay children out top-to-bottom in a single column.

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Vertical gap between children.
        origin_x:  X start for all children.
        origin_y:  Y start for first child.

    Returns:
        ``(max_width, total_height)`` of the column.
    """
    cursor_y = origin_y
    max_w: float = 0.0

    for cid in child_ids:
        child = nodes_map.get(cid)
        if child is None:
            continue
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
) -> tuple[float, float]:
    """Lay children in rows, wrapping after *max_cols* per row.

    Within each row children are left-to-right with *gap* spacing.
    Rows are stacked top-to-bottom with *gap* vertical spacing.

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Spacing in both axes.
        max_cols:  Maximum children per row before wrapping.
        origin_x:  X start.
        origin_y:  Y start.

    Returns:
        ``(total_width, total_height)`` bounding box of all rows.
    """
    rows: list[list[str]] = []
    for i in range(0, len(child_ids), max_cols):
        rows.append(child_ids[i : i + max_cols])

    cursor_y = origin_y
    overall_w: float = 0.0

    for row_ids in rows:
        row_w, row_h = _layout_row(row_ids, nodes_map, gap, origin_x, cursor_y)
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
) -> tuple[float, float]:
    """Lay children in a fixed-column grid.

    Column widths and row heights are uniform (max of each row / column).

    Args:
        child_ids: Ordered child IDs.
        nodes_map: id → node dict.
        gap:       Spacing in both axes.
        grid_cols: Number of columns.
        origin_x:  X start.
        origin_y:  Y start.

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
        child["x"] = origin_x + c_col * (col_w + gap)
        child["y"] = origin_y + c_row * (row_h + gap)

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
            node["x"] = (node.get("x") or 0.0) - parent_x
            node["y"] = (node.get("y") or 0.0) - parent_y
        else:
            auto_ids.append(cid)

    footer_is_manual = False
    if footer_id and footer_id in nodes_map:
        f_node = nodes_map[footer_id]
        if f_node.get("x") is not None or f_node.get("y") is not None:
            footer_is_manual = True
            f_node["x"] = (f_node.get("x") or 0.0) - parent_x
            f_node["y"] = (f_node.get("y") or 0.0) - parent_y

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

    # ── Place auto-laid out main children ────────────────────────────
    origin_x = pad["left"]
    origin_y = pad["top"]
    content_w, content_h = 0.0, 0.0

    if auto_ids:
        if direction == "column":
            content_w, content_h = _layout_column(
                auto_ids, nodes_map, gap, origin_x, origin_y,
            )
        elif direction == "flow":
            content_w, content_h = _layout_flow(
                auto_ids, nodes_map, gap, cfg["max_cols"],
                origin_x, origin_y,
            )
        elif direction == "grid":
            content_w, content_h = _layout_grid(
                auto_ids, nodes_map, gap, cfg["grid_cols"],
                origin_x, origin_y,
            )
        else:  # "row" (default)
            content_w, content_h = _layout_row(
                auto_ids, nodes_map, gap, origin_x, origin_y,
            )

    # ── Place auto-laid out footer ───────────────────────────────────
    if footer_id and footer_id in nodes_map and not footer_is_manual:
        ref_w = content_w
        if manual_ids:
            max_manual_x = max((nodes_map[cid]["x"] + nodes_map[cid]["width"] for cid in manual_ids), default=0.0)
            ref_w = max(content_w, max_manual_x - origin_x)

        footer_node = nodes_map[footer_id]
        footer_top = origin_y + content_h + _FOOTER_GAP
        footer_w = footer_node["width"]
        footer_x = origin_x + max(0, (ref_w - footer_w) / 2)
        footer_node["x"] = footer_x
        footer_node["y"] = footer_top

    # ── Update panel dimensions to enclose all children ─────────────
    all_child_nodes = [nodes_map[cid] for cid in children_ids if cid in nodes_map]
    if all_child_nodes:
        max_child_x = max(n["x"] + n["width"] for n in all_child_nodes)
        max_child_y = max(n["y"] + n["height"] for n in all_child_nodes)
        panel["width"] = max_child_x + pad["right"]
        panel["height"] = max_child_y + pad["bottom"]
    else:
        panel["width"] = pad["left"] + pad["right"]
        panel["height"] = pad["top"] + pad["bottom"]


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
) -> tuple[float, float]:
    """Place a tier's elements in a horizontal row.

    Args:
        tier_ids:  IDs of elements in this tier.
        nodes_map: id → node dict.
        start_x:   Starting X.
        start_y:   Starting Y.
        gap:       Horizontal gap between elements.

    Returns:
        ``(total_width, max_height)`` of the tier row.
    """
    cursor_x = start_x
    max_h: float = 0.0

    for nid in tier_ids:
        node = nodes_map[nid]
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
    """
    if not toplevel_ids:
        return

    fwd, rev = _build_toplevel_graph(connections, nodes_map, toplevel_ids)
    topo_order = _topological_sort(toplevel_ids, fwd, rev)

    tiers = _assign_tiers(topo_order, nodes_map, fwd, rev)

    # ── Lay out each tier as a horizontal row ────────────────────────
    tier_numbers = sorted(tiers.keys())
    tier_extents: dict[int, tuple[float, float]] = {}  # tier → (width, height)
    cursor_y: float = 0.0

    for tn in tier_numbers:
        tier_ids = tiers[tn]
        tw, th = _place_tier_horizontal(
            tier_ids, nodes_map, 0.0, cursor_y, _PANEL_GAP_H,
        )
        tier_extents[tn] = (tw, th)
        cursor_y += th + _PANEL_GAP_V

    # ── Centre tiers relative to the widest ──────────────────────────
    max_tier_w = max((tw for tw, _ in tier_extents.values()), default=0.0)

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

def _absolutize_children(
    nodes: list[dict],
    nodes_map: dict[str, dict],
) -> None:
    """Convert child positions from panel-local to absolute coordinates.

    ``layout_panel_children`` sets child x/y relative to the panel's
    inner coordinate system.  This function adds the parent's absolute
    position to make them absolute.

    Args:
        nodes:     Full flat node list.
        nodes_map: id → node dict.
    """
    for node in nodes:
        parent_id = node.get("parent")
        if parent_id is None:
            continue
        parent = nodes_map.get(parent_id)
        if parent is None or parent.get("x") is None:
            continue
        # Children already have relative x/y from layout_panel_children
        if node.get("x") is not None:
            node["x"] += parent["x"]
        if node.get("y") is not None:
            node["y"] += parent["y"]


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Canvas fitting
# ═══════════════════════════════════════════════════════════════════════════

def _compute_bounding_box(
    nodes: list[dict],
) -> tuple[float, float, float, float]:
    """Compute the axis-aligned bounding box of all positioned nodes.

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
    max_x = max(n["x"] + n["width"] for n in positioned)
    max_y = max(n["y"] + n["height"] for n in positioned)

    return min_x, min_y, max_x, max_y


def _fit_to_canvas(
    nodes: list[dict],
    canvas_w: float,
    canvas_h: float,
    margin: float = _CANVAS_MARGIN,
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
    """
    positioned = [
        n for n in nodes
        if n.get("parent") is None and n.get("x") is not None and n.get("y") is not None
    ]
    if not positioned:
        return

    min_x = min(n["x"] for n in positioned)
    min_y = min(n["y"] for n in positioned)
    max_x = max(n["x"] + n["width"] for n in positioned)
    max_y = max(n["y"] + n["height"] for n in positioned)

    content_w = max_x - min_x
    content_h = max_y - min_y

    if content_w <= 0 or content_h <= 0:
        return

    avail_w = canvas_w - 2 * margin
    avail_h = canvas_h - 2 * margin

    # Scale the layout spacing only if content exceeds canvas bounds
    scale = min(1.0, avail_w / content_w, avail_h / content_h)

    # Translate so content starts at margin and is centered
    scaled_w = content_w * scale
    scaled_h = content_h * scale
    offset_x = margin + (avail_w - scaled_w) / 2
    offset_y = margin + (avail_h - scaled_h) / 2

    for node in positioned:
        # Scale spacing from origin, leaving size intact
        node["x"] = (node["x"] - min_x) * scale + offset_x
        node["y"] = (node["y"] - min_y) * scale + offset_y


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

def layout(
    ir: dict,
    canvas_w: int = 1920,
    canvas_h: int = 1440,
) -> dict:
    """Assign absolute (x, y) positions to every node in the IR.

    This is the main entry point of the layout engine.

    Pipeline:
    1. **Panel children layout** — arrange children inside each panel and
       compute panel dimensions.
    2. **Top-level auto-layout** — use connection graph analysis to place
       panels and free elements.
    3. **Free element placement** — position diamonds, standalone cards,
       etc. based on their connections.
    4. **Absolutize children** — convert panel-relative child positions
       to absolute canvas coordinates.
    5. **Canvas fitting** — scale and translate to fit the canvas.
    6. **Annotation placement** — position labels below the content.

    Args:
        ir:       The IR dict from ``compile_spec`` with keys ``nodes``,
                  ``connections``, ``annotations``.
        canvas_w: Target canvas width in logical pixels.
        canvas_h: Target canvas height in logical pixels.

    Returns:
        The same *ir* dict, with every node augmented with absolute
        ``x``, ``y`` (and possibly adjusted ``width``, ``height``).
    """
    nodes: list[dict] = ir.get("nodes", [])
    connections: list[dict] = ir.get("connections", [])
    annotations: list[dict] = ir.get("annotations", [])

    # ── Read canvas from IR meta if available ────────────────────────
    canvas_meta = ir.get("canvas", {})
    canvas_w = canvas_meta.get("width", canvas_w)
    canvas_h = canvas_meta.get("height", canvas_h)

    # ── Build lookup ─────────────────────────────────────────────────
    nodes_map: dict[str, dict] = {n["id"]: n for n in nodes}

    # ── Identify top-level vs. child nodes ───────────────────────────
    toplevel_nodes = [n for n in nodes if n.get("parent") is None]
    toplevel_ids = {n["id"] for n in toplevel_nodes}

    # Clear any stale coordinates (compiler sets x/y = None)
    for node in nodes:
        if node.get("x") is None:
            node.pop("x", None)
        if node.get("y") is None:
            node.pop("y", None)

    # ── Step 1: Layout children inside each panel ────────────────────
    panels = [n for n in toplevel_nodes if n.get("type") == "panel"]
    for panel in panels:
        layout_panel_children(panel, nodes_map)

    # Also handle nested panels (panels inside panels)
    nested_panels = [
        n for n in nodes
        if n.get("type") == "panel" and n.get("parent") is not None
    ]
    for panel in nested_panels:
        layout_panel_children(panel, nodes_map)

    # ── Step 2: Auto-layout top-level elements ───────────────────────
    unpositioned_toplevel_ids = {
        nid for nid in toplevel_ids
        if nodes_map[nid].get("x") is None or nodes_map[nid].get("y") is None
    }
    if unpositioned_toplevel_ids:
        _auto_layout_toplevel(unpositioned_toplevel_ids, nodes_map, connections)

    # ── Step 3: Position free elements ───────────────────────────────
    _position_free_elements(nodes, nodes_map, connections)

    # ── Step 3b: Fit top-level elements to canvas ────────────────────
    _fit_to_canvas(nodes, canvas_w, canvas_h)

    # ── Step 4: Convert child positions to absolute ─────────────────
    _absolutize_children(nodes, nodes_map)

    # ── Step 5: Position annotations ─────────────────────────────────
    _position_annotations(annotations, nodes)

    return ir
