"""
ts_layout_bridge
-----------------
Subprocess bridge from Python to the real TypeScript diagram layout engine
(``frontend/src/workers/layoutCore.ts``, bundled with its ``elkjs`` dependency
into a single self-contained CLI via ``npm run build:layout-cli`` --
``frontend/dist-cli/layout-cli.cjs``).

This follows the exact ``_find_node()`` / env / timeout / error-handling
pattern already established by ``scripts/flowdraft/elk_layout.py``'s
``route_with_elk()`` for the legacy (still Python-side) ELK bridge. The one
deliberate difference: ``route_with_elk()`` silently returns ``False`` on any
failure and lets its caller fall back to a pure-Python layout, which is how
that bridge has been silently no-op'ing in production (no Node.js in
``backend/Dockerfile`` historically) without anyone noticing. There is no
such fallback here -- the TS engine IS the layout engine for
``compile_diagram`` now, so every failure mode is logged clearly *and*
raised, so the caller surfaces a real error instead of silently returning
data computed by a different, unadvertised engine.
"""
import json
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class TsLayoutError(RuntimeError):
    """Raised whenever the TS layout engine subprocess bridge cannot produce a positioned graph."""


def _find_node() -> Optional[str]:
    """Find path to the Node.js executable (same lookup as elk_layout.py's ``_find_node()``)."""
    return shutil.which("node")


def _repo_root() -> str:
    """
    Walk up from this file's directory until one containing a ``frontend``
    subdirectory is found (mirrors the project-root discovery already used
    at the top of ``backend/app/api/v1/mcp.py``, which walks up looking for
    a ``scripts`` subdirectory instead). Falls back to the fixed
    ``backend/app/services/`` -> repo-root offset (four levels up) if that
    search fails for some reason, so this never raises.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    while current_dir and current_dir != os.path.dirname(current_dir):
        if os.path.isdir(os.path.join(current_dir, "frontend")):
            return current_dir
        current_dir = os.path.dirname(current_dir)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _default_bundle_path() -> str:
    return os.path.join(_repo_root(), "frontend", "dist-cli", "layout-cli.cjs")


def _find_bundle() -> Optional[str]:
    """
    Locate the bundled ``layout-cli.cjs``. Checked in order:

    1. ``$FLOWDRAFT_LAYOUT_CLI_PATH``, if set -- lets a deployment (e.g. the
       multi-stage Docker build) pin an exact location without relying on
       the bridge re-deriving the repo layout.
    2. ``<repo_root>/frontend/dist-cli/layout-cli.cjs`` -- the default
       ``npm run build:layout-cli`` output location, resolved relative to
       the repo root the same way ``elk_bridge.js`` is resolved relative to
       ``elk_layout.py``'s own directory.
    """
    env_path = os.environ.get("FLOWDRAFT_LAYOUT_CLI_PATH")
    if env_path:
        if os.path.exists(env_path):
            return env_path
        log.warning(f"FLOWDRAFT_LAYOUT_CLI_PATH is set to '{env_path}' but no file exists there.")
        return None

    candidate = _default_bundle_path()
    if os.path.exists(candidate):
        return candidate
    return None


def _flatten_graph(graph: Dict[str, Any], connection_count: int) -> Tuple[Dict[str, Dict[str, Any]], List[List[List[float]]]]:
    """
    Flattens the TS engine's raw ELK-shaped result tree (``root`` ->
    ``children[]`` recursively, each level also carrying its own
    ``edges[]``) into absolute canvas-space positions.

    The TS engine's node coordinates are parent-relative (the same
    convention React Flow's ``parentId``/``extent: 'parent'`` nodes use --
    see ``frontend/src/hooks/useFlowLayout.ts``'s ``collectNodes``, which
    deliberately does *not* accumulate through the parent chain because RF
    does that accumulation itself at render time). Python's legacy engine
    (``scripts/flowdraft/elk_layout.py``) instead stores absolute
    canvas-space coordinates on every node, which is what ``compile_diagram``'s
    external contract exposes -- so this reproduces that accumulation,
    ported from ``useFlowLayout.ts``'s ``collectEdges`` (which *does*
    accumulate, since edge points must be absolute for canvas rendering
    regardless of the node-parenting convention).

    Returns ``(positioned_nodes, connection_points)`` where:
      - ``positioned_nodes`` maps element id -> ``{x, y, width, height, parent}``
        (all absolute).
      - ``connection_points`` is a list aligned by index with the original
        ``connections`` array passed to ``run_ts_layout`` (length ==
        ``connection_count``), each entry a list of ``[x, y]`` absolute
        points, or ``[]`` if that connection wasn't routed (e.g. an
        endpoint id that didn't resolve to a node -- ``buildElkGraph`` skips
        creating an edge for those, same as the TS engine's own behavior).
    """
    positioned_nodes: Dict[str, Dict[str, Any]] = {}
    edges_by_index: Dict[int, List[List[float]]] = {}

    def parse_edge_index(edge_id: str) -> Optional[int]:
        # Edge ids are generated by buildElkGraph as `edge-${srcId}-${tgtId}-${i}`
        # where `i` is the original index into the `connections` array and is
        # always the last '-'-separated token (srcId/tgtId may themselves
        # contain hyphens, so only the trailing token is safe to parse).
        if not edge_id:
            return None
        try:
            return int(edge_id.rsplit("-", 1)[-1])
        except (ValueError, IndexError):
            return None

    def walk(node: Dict[str, Any], parent_id: Optional[str], abs_x: float, abs_y: float) -> None:
        is_root = node.get("id") == "root"
        node_abs_x = abs_x + (node.get("x") or 0)
        node_abs_y = abs_y + (node.get("y") or 0)

        if not is_root and node.get("id"):
            positioned_nodes[node["id"]] = {
                "x": node_abs_x,
                "y": node_abs_y,
                "width": node.get("width") or 0,
                "height": node.get("height") or 0,
                "parent": parent_id,
            }

        # Edges declared at this level live in this node's own coordinate
        # frame (offset by this node's absolute position; 0 at the root).
        origin_x = 0.0 if is_root else node_abs_x
        origin_y = 0.0 if is_root else node_abs_y

        for edge in node.get("edges") or []:
            points: List[List[float]] = []
            for sec in edge.get("sections") or []:
                sp = sec["startPoint"]
                points.append([sp["x"] + origin_x, sp["y"] + origin_y])
                for bp in sec.get("bendPoints") or []:
                    points.append([bp["x"] + origin_x, bp["y"] + origin_y])
                ep = sec["endPoint"]
                points.append([ep["x"] + origin_x, ep["y"] + origin_y])
            idx = parse_edge_index(edge.get("id", ""))
            if idx is not None:
                edges_by_index[idx] = points

        for child in node.get("children") or []:
            walk(child, None if is_root else node.get("id"), origin_x, origin_y)

    if graph and graph.get("id"):
        walk(graph, None, 0.0, 0.0)

    connection_points = [edges_by_index.get(i, []) for i in range(connection_count)]
    return positioned_nodes, connection_points


def resolve_annotation_positions(
    annotations: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
    positioned_nodes: Dict[str, Dict[str, Any]],
    connection_points: List[List[List[float]]],
) -> List[Dict[str, Any]]:
    """
    Computes concrete x/y (and, for annotations that need a synthesised
    box, width/height) for every annotation, ported from
    ``scripts/flowdraft/layout_engine.py``'s ``resolve_annotations_positions()``
    (connection-midpoint / ``attachTo``-relative placement) plus its
    ``_position_annotations()`` fallback (stacked bottom-centre for anything
    left unresolved).

    This lives here, in the Python MCP-facing bridge layer, rather than in
    the TS engine itself: annotation coordinates are purely an MCP JSON
    contract concern. The frontend never consumes them -- it attaches an
    annotation directly onto its target node's own data
    (``specCompiler.ts``'s ``nodeData.annotations``) and renders/positions it
    via that node's own component + CSS at render time, not via any
    layout-computed x/y. Only an external MCP/AI client reading
    ``compile_diagram``'s JSON needs real coordinates, so that's the only
    place this needs to be computed -- from the already-positioned nodes and
    routed connection points the TS bridge just returned.

    Returns a NEW list; does not mutate the input ``annotations``.
    """
    from scripts.flowdraft.geometry import point_at_fraction

    conn_index_by_pair: Dict[Tuple[str, str], int] = {}
    for i, conn in enumerate(connections):
        src, tgt = conn.get("from"), conn.get("to")
        if src and tgt:
            conn_index_by_pair[(src, tgt)] = i

    resolved: List[Dict[str, Any]] = []
    unpositioned: List[Dict[str, Any]] = []

    for raw_ann in annotations:
        ann = dict(raw_ann)
        if ann.get("x") is not None and ann.get("y") is not None:
            resolved.append(ann)
            continue

        ax = ay = None

        ann_from, ann_to = ann.get("from"), ann.get("to")
        if ann_from and ann_to:
            idx = conn_index_by_pair.get((ann_from, ann_to))
            pts = connection_points[idx] if idx is not None and idx < len(connection_points) else None
            if pts:
                mid = point_at_fraction([tuple(p) for p in pts], 0.5)
                ax, ay = mid[0], mid[1]

        if ax is None or ay is None:
            target_id = ann.get("attachTo") or ann.get("target")
            target = positioned_nodes.get(target_id) if target_id else None
            if target:
                x, y, w, h = target["x"], target["y"], target["width"], target["height"]
                xc, yc = x + w / 2, y + h / 2
                pos = str(ann.get("position", "top")).lower()
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
            offset = ann.get("offset") or {}
            ann["x"] = ax + offset.get("dx", 0)
            ann["y"] = ay + offset.get("dy", 0)
            resolved.append(ann)
        else:
            unpositioned.append(ann)

    if unpositioned:
        if positioned_nodes:
            min_x = min(n["x"] for n in positioned_nodes.values())
            max_x = max(n["x"] + n["width"] for n in positioned_nodes.values())
            max_y = max(n["y"] + n["height"] for n in positioned_nodes.values())
            center_x = (min_x + max_x) / 2
            cursor_y = max_y + 10
        else:
            center_x, cursor_y = 0.0, 0.0

        for ann in unpositioned:
            ann_w = ann.get("width", 200)
            ann_h = ann.get("height", 20)
            ann["x"] = center_x - ann_w / 2
            ann["y"] = cursor_y
            ann["width"] = ann_w
            ann["height"] = ann_h
            cursor_y += ann_h + 8
            resolved.append(ann)

    return resolved


def run_ts_layout(
    elements: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
    title: Optional[Any] = None,
    layout_direction: Optional[str] = None,
    layout_algorithm: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Runs the bundled TS layout engine (``frontend/dist-cli/layout-cli.cjs``)
    as a subprocess and returns::

        {
          "nodes": {node_id: {"x", "y", "width", "height", "parent"}, ...},
          "connection_points": [[[x, y], ...], ...],  # aligned by index with `connections`
          "canvas": {"width": float, "height": float},
        }

    with all coordinates absolute (canvas-space) -- see ``_flatten_graph``.

    Args:
        elements: Flat element list (each with ``id``/``type``/``parent``
            already resolved), e.g. ``validate_spec(spec)["elements"]``.
        connections: The spec's connection list, e.g.
            ``validate_spec(spec)["connections"]``.
        title: Truthy iff the diagram has a title (only used by the TS
            engine to reserve extra top padding for a title banner).
        layout_direction: The TS engine's own convention -- pass exactly
            ``"vertical"`` for a top-to-bottom layout, anything else
            (including ``None``) means left-to-right. Callers translating
            from the legacy Python/ELK convention (``"DOWN"``/``"RIGHT"``/
            ``"LR"``/``"TB"``/etc., defaulting to ``"DOWN"``) must convert
            before calling this -- this function does not guess.
        layout_algorithm: Passed through verbatim as ELK's
            ``org.eclipse.elk.algorithm`` value (defaults to ``"layered"``
            inside the TS engine if omitted).
        timeout: Subprocess timeout in seconds.

    Raises:
        TsLayoutError: On any failure -- Node.js missing, the bundle
            missing, a subprocess error or timeout, unparseable output, or
            an explicit ``{success: false}`` result from the CLI. There is
            no fallback: unlike ``elk_layout.py``'s ``route_with_elk()``,
            this bridge IS the layout engine, so a failure here must be a
            visible error, not a silent switch to different output.
    """
    node_exe = _find_node()
    if not node_exe:
        log.error("Node.js not found on PATH -- cannot run the TS layout engine bridge.")
        raise TsLayoutError(
            "Node.js not found on PATH. The TS layout engine bridge requires a Node.js "
            "runtime to execute frontend/dist-cli/layout-cli.cjs."
        )

    bundle_path = _find_bundle()
    if not bundle_path:
        log.error(
            "TS layout CLI bundle not found. Checked $FLOWDRAFT_LAYOUT_CLI_PATH and "
            f"'{_default_bundle_path()}'. Run 'npm run build:layout-cli' in frontend/ "
            "(or set FLOWDRAFT_LAYOUT_CLI_PATH)."
        )
        raise TsLayoutError(
            "TS layout CLI bundle not found. Build it with 'npm run build:layout-cli' in "
            "frontend/, or set FLOWDRAFT_LAYOUT_CLI_PATH to its location."
        )

    payload = {
        "elements": elements,
        "connections": connections,
        "title": title,
        "layoutDirection": layout_direction,
        "layoutAlgorithm": layout_algorithm,
    }

    env = os.environ.copy()

    try:
        proc = subprocess.run(
            [node_exe, bundle_path],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        log.error(f"TS layout subprocess timed out after {timeout}s.")
        raise TsLayoutError(f"TS layout subprocess timed out after {timeout}s.") from e
    except Exception as e:
        log.error(f"Failed to run TS layout subprocess: {e}")
        raise TsLayoutError(f"Failed to run TS layout subprocess: {e}") from e

    if not proc.stdout or not proc.stdout.strip():
        log.error(f"TS layout subprocess produced no stdout output. stderr: {proc.stderr}")
        raise TsLayoutError(f"TS layout subprocess produced no output. stderr: {proc.stderr}")

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        log.error(
            f"TS layout subprocess returned invalid JSON: {e}. "
            f"stdout(head): {proc.stdout[:500]!r} stderr: {proc.stderr}"
        )
        raise TsLayoutError(f"TS layout subprocess returned invalid JSON: {e}") from e

    if not result.get("success"):
        err = result.get("error") or f"exit code {proc.returncode}, stderr: {proc.stderr}"
        log.error(f"TS layout engine reported failure: {err}")
        raise TsLayoutError(f"TS layout engine failed: {err}")

    graph = result.get("graph") or {}
    positioned_nodes, connection_points = _flatten_graph(graph, len(connections))

    return {
        "nodes": positioned_nodes,
        "connection_points": connection_points,
        "canvas": {
            "width": graph.get("width") or 0,
            "height": graph.get("height") or 0,
        },
    }
