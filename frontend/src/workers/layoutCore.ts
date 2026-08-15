// Pure, Node-callable ELK graph-building + invocation + post-processing logic,
// extracted from layout.worker.ts so it can be called directly by vitest and a
// future CLI (no browser/Worker/DOM dependencies here).
//
// NOTE on why layout.worker.ts doesn't just call `computeLayout()` below:
// elkjs's plain `new ELK()` constructor auto-detects its execution context by
// checking `typeof document === 'undefined' && typeof self !== 'undefined'`.
// That condition is true inside any real Worker global scope (a Worker has
// `self` but no `document`), which makes elkjs take its "this whole script IS
// a dedicated ELK worker" branch: it hijacks `self.onmessage` as a side effect
// and never exports the constructor `new ELK()` needs, so construction throws
// ("_Worker is not a constructor") and clobbers the worker's own message
// handler in the process (verified empirically). Plain elkjs is therefore only
// safe to use outside a real Worker context (Node, or a browser main thread).
// layout.worker.ts keeps using its existing GWT worker-bundle dispatch for the
// actual ELK invocation, and calls `buildElkGraph`/`postProcessLayoutResult`
// from here around that invocation. `computeLayout` (which does use plain
// elkjs end-to-end) is for non-Worker callers: vitest and the future CLI.
import ELK from 'elkjs';
import type { ElementSpec, ConnectionSpec, TitleConfig } from '../types/spec';

export interface LayoutRequest {
  elements: ElementSpec[];
  connections: ConnectionSpec[];
  title?: TitleConfig | string;
  layoutDirection?: 'vertical' | 'horizontal' | string;
  layoutAlgorithm?: string;
}

export function findFeedbackEdges(elements: any[], connections: any[]): Set<string> {
  const adj: Record<string, string[]> = {};
  elements.forEach((n: any) => {
    adj[n.id] = [];
  });

  connections?.forEach((conn: any) => {
    const from = conn.from;
    const to = conn.to;
    if (adj[from] && adj[to]) {
      adj[from].push(to);
    }
  });

  const visited = new Set<string>();
  const recStack = new Set<string>();
  const feedbackEdges = new Set<string>();

  const dfs = (node: string) => {
    visited.add(node);
    recStack.add(node);

    const neighbors = adj[node] || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        dfs(neighbor);
      } else if (recStack.has(neighbor)) {
        feedbackEdges.add(`${node}->${neighbor}`);
      }
    }

    recStack.delete(node);
  };

  elements.forEach((n: any) => {
    if (!visited.has(n.id)) {
      dfs(n.id);
    }
  });

  return feedbackEdges;
}

export function computeNodeDimensions(node: any): { width: number; height: number } {
  const w = Number(node.width || 0);
  const h = Number(node.height || 0);
  if (w > 0 && h > 0) {
    return { width: w, height: h };
  }

  const title = String(node.title || node.label || node.id || '');
  const subtitle = String(node.subtitle || '');
  const badge = String(node.badge || '');
  const hasIcon = Boolean(node.icon);

  const horizPad = 36 + (hasIcon ? 28 : 0) + (badge ? 30 : 0);
  const charsPerLine = 22;
  const lines = title ? Math.max(1, Math.ceil(title.length / charsPerLine)) : 1;

  const maxLineLen = title ? Math.max(...title.split('\n').map((l: string) => l.length)) : 0;
  const calcW = title ? Math.max(180, Math.min(360, maxLineLen * 9.5 + horizPad)) : 200;
  const calcH = Math.max(72, 36 + lines * 20 + (subtitle ? 18 : 0));

  return { width: Math.max(w, calcW), height: Math.max(h, calcH) };
}

function isFooterNode(node: any): boolean {
  if (!node) return false;
  if (node._role === 'footer' || node.data?.role === 'footer') return true;
  if (typeof node.id === 'string' && node.id.toLowerCase().includes('footer')) return true;
  return false;
}

type PortSideWord = 'top' | 'bottom' | 'left' | 'right';

const SIDE_TO_ELK: Record<PortSideWord, string> = {
  top: 'NORTH',
  bottom: 'SOUTH',
  left: 'WEST',
  right: 'EAST',
};

/** A single unshared port at a side's midpoint (the original, pre-fanning shape). */
function makeSidePort(side: PortSideWord, W: number, H: number, id: string): any {
  const coords: Record<PortSideWord, { x: number; y: number }> = {
    top: { x: W / 2, y: 0 },
    bottom: { x: W / 2, y: H },
    left: { x: 0, y: H / 2 },
    right: { x: W, y: H / 2 },
  };
  const c = coords[side];
  return { id, width: 1, height: 1, x: c.x, y: c.y, layoutOptions: { 'org.eclipse.elk.port.side': SIDE_TO_ELK[side] } };
}

/**
 * `count` distinct ports spread along `side`, symmetric around its midpoint
 * at PORT_PITCH apart. Used when more than one connection shares the same
 * (node, side, direction) — without this, they'd all resolve to the exact
 * same single-port coordinate `makeSidePort` returns, giving zero on-canvas
 * separation between their endpoints (the root cause behind
 * checkMultiConnectionPortSpacing failures against the real default spec,
 * where 5 connections converge on `core_1`'s left side alone).
 */
function makeFannedPorts(
  nid: string,
  side: PortSideWord,
  W: number,
  H: number,
  direction: 'exit' | 'entry',
  count: number
): any[] {
  const PORT_PITCH = 20; // > checkMultiConnectionPortSpacing's 16px minimum, with margin.
  const isVerticalSide = side === 'left' || side === 'right';
  const along = isVerticalSide ? H / 2 : W / 2;
  const fixed = side === 'top' ? 0 : side === 'bottom' ? H : side === 'left' ? 0 : W;

  const ports: any[] = [];
  for (let idx = 0; idx < count; idx++) {
    const offset = (idx - (count - 1) / 2) * PORT_PITCH;
    const alongCoord = along + offset;
    const x = isVerticalSide ? fixed : alongCoord;
    const y = isVerticalSide ? alongCoord : fixed;
    ports.push({
      id: `${nid}-port-${side}-${direction}-${idx}`,
      width: 1,
      height: 1,
      x,
      y,
      layoutOptions: { 'org.eclipse.elk.port.side': SIDE_TO_ELK[side] },
    });
  }
  return ports;
}

/**
 * Groups connection indices by the (node, side) they exit/enter through, so
 * `buildElkGraph` can give each side either a single shared port (the common
 * case — one or zero connections touching it) or a fanned-out set of
 * distinct ports (when multiple connections share a side), and so edges can
 * look up which specific port id they were assigned.
 */
function computePortGroups(connections: any[]): {
  exitGroups: Map<string, number[]>;
  entryGroups: Map<string, number[]>;
} {
  const exitGroups = new Map<string, number[]>();
  const entryGroups = new Map<string, number[]>();

  connections?.forEach((conn: any, i: number) => {
    const exitPort = conn.exitPort || conn.fromPort || 'bottom';
    const entryPort = conn.entryPort || conn.toPort || 'top';
    const exitKey = `${conn.from}|${exitPort}`;
    const entryKey = `${conn.to}|${entryPort}`;
    if (!exitGroups.has(exitKey)) exitGroups.set(exitKey, []);
    exitGroups.get(exitKey)!.push(i);
    if (!entryGroups.has(entryKey)) entryGroups.set(entryKey, []);
    entryGroups.get(entryKey)!.push(i);
  });

  return { exitGroups, entryGroups };
}

/**
 * Extends an edge's initial and final orthogonal segments to at least
 * `minStubLen`, if ELK routed either one shorter — a purely geometric,
 * port-side-agnostic correction: it stretches the first/last leg further in
 * the direction it already travels (guaranteed axis-aligned, since ports use
 * FIXED_SIDE and routing is ORTHOGONAL) and shifts the adjacent bend point
 * by the same delta on whichever coordinate it shares with the corner being
 * moved, so the polyline stays connected and every corner stays a right
 * angle. This is what checkDirectionalPortNormalStubs (quality/) checks for;
 * without it, ELK sometimes turns almost immediately off a port (observed:
 * ~10px before the first bend against the real default spec), which reads
 * as the line clipping the node's edge at a glance.
 *
 * No-ops on edges with fewer than 4 points: with exactly 3 points the single
 * interior point is shared by both the start and end correction, and with 2
 * points there's no bend at all — extending either would mean moving the
 * other end's actual port coordinate, not a bend, which isn't safe here.
 */
function ensureMinimumEdgeStubs(points: [number, number][], minStubLen: number): [number, number][] {
  if (points.length < 4) return points;
  const pts = points.map((p) => [...p] as [number, number]);

  const extendLeg = (portIdx: number, cornerIdx: number, neighborIdx: number) => {
    const [px, py] = pts[portIdx];
    const [cx, cy] = pts[cornerIdx];
    const dx = cx - px;
    const dy = cy - py;
    const len = Math.hypot(dx, dy);
    if (len === 0 || len >= minStubLen) return;

    const ux = dx / len;
    const uy = dy / len;
    const newCx = px + ux * minStubLen;
    const newCy = py + uy * minStubLen;
    const shiftX = newCx - cx;
    const shiftY = newCy - cy;
    pts[cornerIdx] = [newCx, newCy];

    // Keep the next corner's shared coordinate aligned so that segment
    // stays orthogonal too.
    const [nx, ny] = pts[neighborIdx];
    if (Math.abs(cx - nx) < 0.01) {
      pts[neighborIdx] = [nx + shiftX, ny];
    } else if (Math.abs(cy - ny) < 0.01) {
      pts[neighborIdx] = [nx, ny + shiftY];
    }
  };

  extendLeg(0, 1, 2);
  extendLeg(pts.length - 1, pts.length - 2, pts.length - 3);

  return pts;
}

/**
 * Walks the full layout result tree and applies `ensureMinimumEdgeStubs` to
 * every edge's routed section (each container's own `.edges`, at every
 * nesting level — root's cross-panel edges and every panel's intra-panel
 * edges alike).
 */
function fixShortEdgeStubs(node: any, minStubLen = 16): void {
  (node.edges || []).forEach((edge: any) => {
    (edge.sections || []).forEach((sec: any) => {
      const points: [number, number][] = [
        [sec.startPoint.x, sec.startPoint.y],
        ...(sec.bendPoints || []).map((bp: any) => [bp.x, bp.y] as [number, number]),
        [sec.endPoint.x, sec.endPoint.y],
      ];
      if (points.length < 4) return;
      const fixed = ensureMinimumEdgeStubs(points, minStubLen);
      sec.startPoint = { x: fixed[0][0], y: fixed[0][1] };
      sec.endPoint = { x: fixed[fixed.length - 1][0], y: fixed[fixed.length - 1][1] };
      sec.bendPoints = fixed.slice(1, -1).map(([x, y]) => ({ x, y }));
    });
  });
  (node.children || []).forEach((child: any) => fixShortEdgeStubs(child, minStubLen));
}

/**
 * Box-packs a panel's children into row-major "flow" (wrap after N columns,
 * row height = tallest child in that row) or fixed-column "grid" (uniform
 * cell pitch = max width/height across ALL children, row-major placement)
 * positions — ported from scripts/flowdraft/layout_engine.py's `_layout_flow`
 * / `_layout_grid`.
 *
 * ELK has no native algorithm that preserves this exact row-major packing,
 * so panels using these directions don't rely on ELK's own placement for
 * their children at all: this function is the sole source of truth for
 * their x/y. It mutates `x`/`y` (in the same origin-relative coordinate
 * space ELK positions siblings in, i.e. relative to the panel's own
 * top-left, offset by `originX`/`originY` — typically the panel's
 * left/top content padding) directly onto each child's entry in
 * `nodesMap`, matching this file's existing mutate-in-place convention
 * (see `computeNodeDimensions`). Children not present in `nodesMap` are
 * skipped (defensive; shouldn't happen for well-formed input).
 *
 * Returns the packed content's bounding box (width/height, NOT including
 * the origin offset) — the panel's own width/height is derived from the
 * final child positions by the generic panel-resize logic in
 * `postProcessLayoutResult`, so callers don't strictly need this, but it's
 * returned for parity with the Python function and for tests.
 */
export function computeFlowGridPositions(
  childIds: string[],
  nodesMap: Map<string, any>,
  gap: number,
  mode: 'flow' | 'grid',
  maxColsOrGridCols: number,
  originX: number = 0,
  originY: number = 0
): { width: number; height: number } {
  if (!childIds.length) {
    return { width: 0, height: 0 };
  }

  if (mode === 'grid') {
    const gridCols = Math.max(1, Math.floor(maxColsOrGridCols) || 1);

    // Uniform cell size: max width/height across ALL children (not per-row/col).
    let colW = 0;
    let rowH = 0;
    childIds.forEach((cid) => {
      const child = nodesMap.get(cid);
      if (child) {
        colW = Math.max(colW, Number(child.width) || 0);
        rowH = Math.max(rowH, Number(child.height) || 0);
      }
    });

    childIds.forEach((cid, idx) => {
      const child = nodesMap.get(cid);
      if (!child) return;
      const col = idx % gridCols;
      const row = Math.floor(idx / gridCols);
      child.x = originX + col * (colW + gap);
      child.y = originY + row * (rowH + gap);
    });

    const placed = childIds.map((cid) => nodesMap.get(cid)).filter(Boolean);
    if (!placed.length) {
      const numRows = Math.ceil(childIds.length / gridCols);
      return {
        width: gridCols * colW + (gridCols - 1) * gap,
        height: numRows * rowH + (numRows - 1) * gap
      };
    }
    const maxX = Math.max(...placed.map((n) => (n.x || 0) + (Number(n.width) || 0)));
    const maxY = Math.max(...placed.map((n) => (n.y || 0) + (Number(n.height) || 0)));
    return { width: maxX - originX, height: maxY - originY };
  }

  // mode === 'flow': row-major, wrap after maxCols children per row.
  const maxCols = Math.max(1, Math.floor(maxColsOrGridCols) || 1);
  const rows: string[][] = [];
  for (let i = 0; i < childIds.length; i += maxCols) {
    rows.push(childIds.slice(i, i + maxCols));
  }

  let cursorY = originY;
  let overallW = 0;

  rows.forEach((rowIds) => {
    let cursorX = originX;
    let rowMaxH = 0;
    rowIds.forEach((cid) => {
      const child = nodesMap.get(cid);
      if (!child) return;
      child.x = cursorX;
      child.y = cursorY;
      cursorX += (Number(child.width) || 0) + gap;
      rowMaxH = Math.max(rowMaxH, Number(child.height) || 0);
    });
    const rowW = rowIds.length ? cursorX - gap - originX : 0;
    overallW = Math.max(overallW, rowW);
    cursorY += rowMaxH + gap;
  });

  const totalH = rows.length ? cursorY - gap - originY : 0;
  return { width: overallW, height: totalH };
}

// Reserved top padding (title/subtitle) for each panel, computed from a
// fixed assumed chars-per-line since the panel's real final width isn't
// known until ELK has laid it out. Shared by buildElkGraph (which uses it to
// pad ELK's own child layout) and postProcessLayoutResult (which reconciles
// it against the panel's real final width).
function computePanelHeaderPad(elements: any[]): Record<string, number> {
  const panelHeaders: Record<string, number> = {};
  elements.forEach((node: any) => {
    if (node.type === 'panel') {
      let topPad = 40.0;
      const titleText = node.title || '';
      const titleLines = Math.max(1, Math.ceil(titleText.length / 28));
      const subtitleText = node.subtitle || '';
      const subtitleLines = subtitleText ? Math.max(1, Math.ceil(subtitleText.length / 32)) : 0;
      topPad = Math.max(44, 20 + titleLines * 20 + subtitleLines * 16);
      panelHeaders[node.id] = topPad + 15.0;
    }
  });
  return panelHeaders;
}

/**
 * Builds the ELK input graph from a layout request: leaf/panel node
 * construction (with ports), panel padding/header reservation, footer space
 * reservation, top-level topological ordering, and feedback-edge marking.
 *
 * Mutates `width`/`height` onto leaf elements as a side effect (matching the
 * layout worker's prior behavior).
 */
export function buildElkGraph(request: LayoutRequest): any {
  const { elements, connections, title, layoutDirection, layoutAlgorithm } = request;
  const feedbackEdges = findFeedbackEdges(elements, connections);
  const isFeedback = (srcId: string, tgtId: string): boolean => {
    return feedbackEdges.has(`${srcId}->${tgtId}`);
  };

  const nodesMap = new Map<string, any>();
  elements.forEach((n: any) => nodesMap.set(n.id, n));

  const getTopParent = (id: string): string => {
    const visited = new Set<string>();
    let current = id;
    while (nodesMap.get(current)?.parent) {
      if (visited.has(current)) break;
      visited.add(current);
      current = nodesMap.get(current)!.parent!;
    }
    return current;
  };

  const panelHeaders = computePanelHeaderPad(elements);
  const { exitGroups, entryGroups } = computePortGroups(connections);

  // Resolves the ELK port id a given connection endpoint should target: the
  // plain per-side id when it's the only connection touching that (node,
  // side, direction), or its own fanned-out sub-port id when it shares that
  // side with others (see makeFannedPorts/computePortGroups above).
  const resolvePortId = (
    nodeId: string,
    side: string,
    direction: 'exit' | 'entry',
    connIdx: number
  ): string => {
    const group = (direction === 'exit' ? exitGroups : entryGroups).get(`${nodeId}|${side}`);
    if (!group || group.length <= 1) {
      return `${nodeId}-port-${side}`;
    }
    return `${nodeId}-port-${side}-${direction}-${group.indexOf(connIdx)}`;
  };

  // Pre-pass: compute leaf-node (non-panel/group) width/height for every
  // element up front, before building any ELK nodes. A flow/grid panel
  // needs to know its children's sizes to box-pack them (below), but
  // children can appear later than their parent panel in the flat
  // `elements` array — this pass makes dimensions available regardless of
  // array order. (Mutates `width`/`height` onto leaf elements, same as the
  // per-node computation this replaces the ordering dependency of.)
  elements.forEach((node: any) => {
    if (node.type !== 'panel' && node.type !== 'group') {
      const { width: W, height: H } = computeNodeDimensions(node);
      node.width = W;
      node.height = H;
    }
  });

  const elkNodes: Record<string, any> = {};
  elements.forEach((node: any) => {
    const nid = node.id;
    if (isFooterNode(node)) {
      return;
    }
    const ntype = node.type;
    const elkNode: any = { id: nid, children: [], edges: [] };

    if (ntype === 'panel' || ntype === 'group') {
      const direction = node.layout?.direction || 'row';
      const gap = node.layout?.gap ?? 20;
      const topPad = panelHeaders[nid] || 40.0;
      let padLeft = 20, padBottom = 20, padRight = 20;
      if (node.layout?.padding) {
        const p = node.layout.padding;
        if (typeof p === 'number') {
          padLeft = p; padBottom = p; padRight = p;
        } else {
          padLeft = p.left ?? 20;
          padBottom = p.bottom ?? 20;
          padRight = p.right ?? 20;
        }
      }
      const footerNode = elements.find(
        (el: any) => el.parent === nid && isFooterNode(el)
      );
      if (footerNode) {
        const footerW = 260.0;
        const titleText = footerNode.title || footerNode.body || '';
        const lineCount = Math.max(1, Math.ceil((titleText.length * 7) / (footerW - 40)));
        const footerH = Math.max(48, 32 + lineCount * 18);
        padBottom += footerH + 16.0;
      }

      elkNode.layoutOptions = {
        'org.eclipse.elk.algorithm': 'layered',
        'org.eclipse.elk.direction': direction === 'column' ? 'DOWN' : 'RIGHT',
        'org.eclipse.elk.spacing.nodeNode': String(gap),
        'org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers': String(gap + 15),
        'org.eclipse.elk.spacing.edgeNode': '20',
        'org.eclipse.elk.layered.nodePlacement.strategy': 'BALANCED',
        'org.eclipse.elk.edgeRouting': 'ORTHOGONAL',
        'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
        'org.eclipse.elk.padding': `[top=${topPad},left=${padLeft},bottom=${padBottom},right=${padRight}]`
      };

      if (direction === 'flow' || direction === 'grid') {
        // flow/grid children aren't placed by ELK's own layered algorithm —
        // they keep an ELK node entry (with ports, added as a normal child
        // below) purely so edges to/from them still resolve, but this
        // function is the sole source of truth for their x/y. The result is
        // spliced back in during postProcessLayoutResult, which reads the
        // x/y set here off the same node objects (via `nodesMap`) and
        // overwrites the panel's ELK-computed child positions with them.
        const childIds = elements
          .filter((el: any) => el.parent === nid && !isFooterNode(el))
          .map((el: any) => el.id);
        const maxColsOrGridCols = direction === 'flow'
          ? Number(node.layout?.max_cols ?? 3)
          : Number(node.layout?.grid_cols ?? 2);
        const { width: contentW, height: contentH } =
          computeFlowGridPositions(childIds, nodesMap, gap, direction, maxColsOrGridCols, padLeft, topPad);

        // ELK doesn't know about this box-packed content up front — its own
        // (discarded) child layout would typically be far more compact than
        // the real packed size, so without a hint the ROOT-level algorithm
        // reserves too little space between this panel and its siblings,
        // and the real (larger) size we splice in later ends up overlapping
        // them. Giving the panel its true final width/height as a minimum
        // size constraint here fixes root-level spacing to match reality.
        const panelW = padLeft + contentW + padRight;
        const panelH = topPad + contentH + padBottom;
        elkNode.width = panelW;
        elkNode.height = panelH;
        elkNode.layoutOptions['org.eclipse.elk.nodeSize.constraints'] = 'MINIMUM_SIZE';
        elkNode.layoutOptions['org.eclipse.elk.nodeSize.minimum'] = `(${panelW}, ${panelH})`;
      }

    } else {
      const { width: W, height: H } = computeNodeDimensions(node);
      node.width = W;
      node.height = H;
      elkNode.width = W;
      elkNode.height = H;

      elkNode.layoutOptions = {
        'org.eclipse.elk.portConstraints': 'FIXED_SIDE'
      };

      // Each side gets either one plain shared port (0 or 1 connection
      // touching it — the common case, geometry unchanged from before) or a
      // fanned-out set of distinct ports (multiple connections sharing that
      // side, each direction independently) so they don't all collide on
      // the exact same coordinate.
      elkNode.ports = [];
      (['top', 'bottom', 'left', 'right'] as const).forEach((side) => {
        const key = `${nid}|${side}`;
        const exitCount = exitGroups.get(key)?.length || 0;
        const entryCount = entryGroups.get(key)?.length || 0;

        if (exitCount <= 1 && entryCount <= 1) {
          elkNode.ports.push(makeSidePort(side, W, H, `${nid}-port-${side}`));
          return;
        }
        if (exitCount > 1) {
          elkNode.ports.push(...makeFannedPorts(nid, side, W, H, 'exit', exitCount));
        } else if (exitCount === 1) {
          elkNode.ports.push(makeSidePort(side, W, H, `${nid}-port-${side}`));
        }
        if (entryCount > 1) {
          elkNode.ports.push(...makeFannedPorts(nid, side, W, H, 'entry', entryCount));
        } else if (entryCount === 1) {
          elkNode.ports.push(makeSidePort(side, W, H, `${nid}-port-${side}`));
        }
      });
    }
    elkNodes[nid] = elkNode;
  });

  const topRootPad = title ? 150 : 60;
  const rootAlgorithm = layoutAlgorithm || 'layered';
  const rootDirection = layoutDirection === 'vertical' ? 'DOWN' : 'RIGHT';

  const elkRoot: any = {
    id: 'root',
    layoutOptions: {
      'org.eclipse.elk.algorithm': rootAlgorithm,
      'org.eclipse.elk.direction': rootDirection,
      'org.eclipse.elk.spacing.nodeNode': '70',
      'org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers': '80',
      'org.eclipse.elk.spacing.edgeNode': '25',
      'org.eclipse.elk.spacing.edgeEdge': '15',
      'org.eclipse.elk.layered.nodePlacement.strategy': 'BALANCED',
      'org.eclipse.elk.cycleBreaking.strategy': 'GREEDY',
      'org.eclipse.elk.edgeRouting': 'ORTHOGONAL',
      'org.eclipse.elk.hierarchyHandling': 'INCLUDE_CHILDREN',
      'org.eclipse.elk.portConstraints': 'FIXED_SIDE',
      'org.eclipse.elk.padding': `[top=${topRootPad},left=50,bottom=50,right=50]`
    },
    children: [],
    edges: []
  };


  elements.forEach((node: any) => {
    const nid = node.id;
    const elkNode = elkNodes[nid];
    if (!elkNode) return;
    const parentId = node.parent;
    if (parentId && elkNodes[parentId]) {
      elkNodes[parentId].children.push(elkNode);
    } else {
      elkRoot.children.push(elkNode);
    }
  });

  const topLevelIds = new Set<string>(elkRoot.children.map((c: any) => c.id as string));
  if (topLevelIds.size > 0) {
    const adj: Record<string, Set<string>> = {};
    const inDegree: Record<string, number> = {};
    topLevelIds.forEach((id) => {
      adj[id] = new Set<string>();
      inDegree[id] = 0;
    });

    connections?.forEach((conn: any) => {
      const srcId = conn.from;
      const tgtId = conn.to;
      if (isFeedback(srcId, tgtId)) return;
      const srcTop = getTopParent(srcId);
      const tgtTop = getTopParent(tgtId);
      if (srcTop !== tgtTop && topLevelIds.has(srcTop) && topLevelIds.has(tgtTop)) {
        if (!adj[srcTop].has(tgtTop)) {
          adj[srcTop].add(tgtTop);
          inDegree[tgtTop] = (inDegree[tgtTop] || 0) + 1;
        }
      }
    });

    const topoOrder: string[] = [];
    const inDegCopy = { ...inDegree };

    while (topoOrder.length < topLevelIds.size) {
      const zeros = Array.from(topLevelIds).filter(
        (id: string) => inDegCopy[id] === 0 && !topoOrder.includes(id)
      );

      if (zeros.length === 0) {
        const remaining = Array.from(topLevelIds).filter((id: string) => !topoOrder.includes(id));
        if (remaining.length === 0) break;
        const minId = remaining.reduce((min: string, id: string) =>
          (inDegCopy[id] || 0) < (inDegCopy[min] || 0) ? id : min
        , remaining[0]);
        zeros.push(minId);
      }

      const curr = zeros[0];
      topoOrder.push(curr);
      adj[curr]?.forEach((neighbor: string) => {
        if (inDegCopy[neighbor] > 0) {
          inDegCopy[neighbor]--;
        }
      });
    }

    const rank: Record<string, number> = {};
    topLevelIds.forEach((id: string) => {
      rank[id] = 0;
    });
    topoOrder.forEach((nodeId: string) => {
      adj[nodeId]?.forEach((neighbor: string) => {
        rank[neighbor] = Math.max(rank[neighbor], rank[nodeId] + 1);
      });
    });

    const elementIndexMap: Record<string, number> = {};
    elements.forEach((node: any, idx: number) => {
      elementIndexMap[node.id] = idx;
    });

    elkRoot.children.sort((a: any, b: any) => {
      const rA = rank[a.id] ?? 999;
      const rB = rank[b.id] ?? 999;
      if (rA === rB) {
        const idxA = elementIndexMap[a.id] ?? 999;
        const idxB = elementIndexMap[b.id] ?? 999;
        return idxA - idxB;
      }
      return rA - rB;
    });
  }

  connections?.forEach((conn: any, i: number) => {
    const srcId = conn.from;
    const tgtId = conn.to;
    if (!elkNodes[srcId] || !elkNodes[tgtId]) return;

    const edgeOpts: any = {};
    if (isFeedback(srcId, tgtId)) {
      edgeOpts['org.eclipse.elk.layered.feedback'] = 'true';
    }

    const src = getTopParent(srcId);
    const tgt = getTopParent(tgtId);
    const exitPort = conn.exitPort || conn.fromPort || 'bottom';
    const entryPort = conn.entryPort || conn.toPort || 'top';
    const srcPortId = resolvePortId(srcId, exitPort, 'exit', i);
    const tgtPortId = resolvePortId(tgtId, entryPort, 'entry', i);

    if (src !== tgt) {
      const edge: any = {
        id: `edge-${srcId}-${tgtId}-${i}`,
        sources: [srcPortId],
        targets: [tgtPortId]
      };
      if (Object.keys(edgeOpts).length > 0) {
        edge.layoutOptions = edgeOpts;
      }
      elkRoot.edges.push(edge);
    } else {
      const edge: any = {
        id: `edge-${srcId}-${tgtId}-${i}`,
        sources: [srcPortId],
        targets: [tgtPortId]
      };
      if (Object.keys(edgeOpts).length > 0) {
        edge.layoutOptions = edgeOpts;
      }
      if (elkNodes[src]) {
        elkNodes[src].edges.push(edge);
      } else {
        elkRoot.edges.push(edge);
      }
    }
  });

  return elkRoot;
}

/**
 * Post-processes a raw ELK layout result (the positioned graph ELK produced
 * from the input `buildElkGraph` returned): reconciles panel width/height and
 * header/badge sizing against the panel's real final width, places footer
 * nodes, and positions hero/hero_card summary nodes top-centered, shifting
 * the rest of the graph down to make room.
 *
 * Mutates and returns the same graph object that was passed in (matching the
 * layout worker's prior behavior of mutating `layoutResult.data` in place).
 */
export function postProcessLayoutResult(layoutResultData: any, elements: any[]): any {
  const nodesMap = new Map<string, any>();
  elements.forEach((n: any) => nodesMap.set(n.id, n));

  const flatResultNodes: any[] = [];
  const collectNodes = (node: any) => {
    flatResultNodes.push(node);
    node.children?.forEach(collectNodes);
  };
  collectNodes(layoutResultData);
  const resultMap = new Map<string, any>();
  flatResultNodes.forEach((n) => resultMap.set(n.id, n));

  // Post-process manually positioned panel footers and container bounds (bottom-up depth order)
  const getPanelDepth = (id: string): number => {
    let depth = 0;
    let curr = nodesMap.get(id);
    while (curr && curr.parent) {
      depth++;
      curr = nodesMap.get(curr.parent);
    }
    return depth;
  };

  const panelHeaders = computePanelHeaderPad(elements);

  const panelElements = elements.filter((node: any) => node.type === 'panel' || node.type === 'group');
  panelElements.sort((a: any, b: any) => getPanelDepth(b.id) - getPanelDepth(a.id));

  panelElements.forEach((node: any) => {
    const panelId = node.id;
    const resultPanel = resultMap.get(panelId);
    if (!resultPanel) return;

    let padLeft = 20, padBottom = 20, padRight = 20;
    if (node.layout?.padding) {
      const p = node.layout.padding;
      if (typeof p === 'number') {
        padLeft = p; padBottom = p; padRight = p;
      } else {
        padLeft = p.left ?? 20;
        padBottom = p.bottom ?? 20;
        padRight = p.right ?? 20;
      }
    }

    const allChildren = flatResultNodes.filter(
      (n) => nodesMap.get(n.id)?.parent === panelId
    );

    // flow/grid panels: overwrite ELK's own (discarded) child positions with
    // the ones computeFlowGridPositions already computed and stashed onto
    // the input node objects during buildElkGraph, before anything below
    // reads allChildren's x/y to size the panel or reconcile the header.
    const panelDirection = node.layout?.direction;
    if (panelDirection === 'flow' || panelDirection === 'grid') {
      allChildren.forEach((c: any) => {
        const srcNode = nodesMap.get(c.id);
        if (srcNode && typeof srcNode.x === 'number' && typeof srcNode.y === 'number') {
          c.x = srcNode.x;
          c.y = srcNode.y;
        }
      });
    }

    if (allChildren.length > 0) {
      const maxRight = Math.max(...allChildren.map((c) => (c.x || 0) + (c.width || 200)));
      resultPanel.width = Math.max(resultPanel.width || 200, maxRight + padRight);
    }

    // Reconcile the header (title/subtitle) against the panel's REAL final width.
    // panelHeaders[] was computed before layout ran, using a fixed assumed
    // chars-per-line, because the panel's actual width is only known now
    // (ELK auto-sizes containers from their children). If the panel ended up
    // narrower than that assumption implied, the title/subtitle will wrap
    // into more lines in the browser than were reserved for, and the header
    // text would overlap the first row of children. Re-measure using the
    // real width and push children down (growing the panel) if it falls short.
    const headerTitleText = String(node.title || '');
    const headerSubtitleText = String(node.subtitle || '');
    if (headerTitleText || headerSubtitleText) {
      // The header's text insets are fixed by PanelNode.tsx ("left-4 right-4" = 16px
      // each), independent of this panel's configurable layout.padding (used for
      // child placement) — use the real CSS inset here, not padLeft/padRight.
      const headerInset = 16;
      const badgeReserve = node.badge ? 46 : 0;
      const avgCharPx = 9.0; // ~10px bold uppercase tracking-widest glyph width (measured)
      const titleAvailPx = Math.max(30, resultPanel.width - headerInset * 2 - badgeReserve);
      const titleCharsPerLine = Math.max(4, Math.floor(titleAvailPx / avgCharPx));
      const realTitleLines = headerTitleText ? Math.max(1, Math.ceil(headerTitleText.length / titleCharsPerLine)) : 0;

      const subtitleAvailPx = Math.max(30, resultPanel.width - headerInset * 2);
      const subtitleCharsPerLine = Math.max(4, Math.floor(subtitleAvailPx / (avgCharPx * 0.85)));
      const realSubtitleLines = headerSubtitleText ? Math.max(1, Math.ceil(headerSubtitleText.length / subtitleCharsPerLine)) : 0;

      // 14px top offset ("top-3.5") + ~12.5px per wrapped line + a little breathing room.
      const realHeaderH = 14 + realTitleLines * 13.5 + realSubtitleLines * 13.5 + 12;
      const reservedTopPad = panelHeaders[panelId] || 40.0;
      const shortfall = realHeaderH - reservedTopPad;

      if (shortfall > 0) {
        allChildren.forEach((c: any) => {
          c.y = (c.y || 0) + shortfall;
        });
      }
    }

    if (allChildren.length > 0) {
      const maxBottom = Math.max(...allChildren.map((c) => (c.y || 0) + (c.height || 80)));
      resultPanel.height = Math.max(resultPanel.height || 100, maxBottom + padBottom);
    }

      // Find the footer child node in the input elements list if present
      const footerNode = elements.find(
        (el: any) => el.parent === panelId && isFooterNode(el)
      );
      if (!footerNode) return;

      const otherChildren = allChildren.filter((n) => n.id !== footerNode.id);
      let maxY = 40;
      if (otherChildren.length > 0) {
        maxY = Math.max(...otherChildren.map((c) => (c.y || 0) + (c.height || 80)));
      }

      const footerW = Math.max(200.0, resultPanel.width - padLeft - padRight);
      const titleText = footerNode.title || footerNode.body || '';
      const lineCount = Math.max(1, Math.ceil((titleText.length * 7) / (footerW - 40)));
      const footerH = Math.max(48, 32 + lineCount * 18);

      const inputFooter = elements.find((el: any) => el.id === footerNode.id);
      if (inputFooter) {
        inputFooter.width = footerW;
        inputFooter.height = footerH;
      }

      const footerX = padLeft + (resultPanel.width - padLeft - padRight - footerW) / 2.0;
      const footerY = maxY + 16.0;

      const resultFooter: any = {
        id: footerNode.id,
        x: footerX,
        y: footerY,
        width: footerW,
        height: footerH
      };

      if (!resultPanel.children) {
        resultPanel.children = [];
      }
      if (!resultPanel.children.some((c: any) => c.id === footerNode.id)) {
        resultPanel.children.push(resultFooter);
      }
  });

  // Post-process hero summary nodes to position them top-centered and shift other graph nodes down
  const heroNodes = elements.filter((n: any) =>
    n.type === 'hero' || n.type === 'hero_card' || n.variant === 'hero' || n.variant === 'hero_card' || (n.id && n.id.startsWith('hero'))
  );
  if (heroNodes.length > 0) {
    let totalHeroH = 0;
    heroNodes.forEach((h: any) => {
      totalHeroH += (h.height || 120.0) + 30.0;
    });

    // Shift top-level non-hero nodes down
    flatResultNodes.forEach((n: any) => {
      if (!nodesMap.get(n.id)?.parent && !heroNodes.some((hn: any) => hn.id === n.id) && n.y !== undefined) {
        n.y += totalHeroH;
      }
    });

    // Center hero nodes across main graph bounding box
    const otherNodes = flatResultNodes.filter((n: any) =>
      !nodesMap.get(n.id)?.parent && !heroNodes.some((hn: any) => hn.id === n.id) && n.x !== undefined
    );
    let graphCenterX = 1000.0;
    if (otherNodes.length > 0) {
      const minX = Math.min(...otherNodes.map((n: any) => n.x || 0));
      const maxR = Math.max(...otherNodes.map((n: any) => (n.x || 0) + (n.width || 0)));
      graphCenterX = (minX + maxR) / 2.0;
    }

    let currHeroY = 130.0;
    heroNodes.forEach((hero: any) => {
      const resHero = resultMap.get(hero.id);
      if (resHero) {
        const hw = hero.width || 1400.0;
        resHero.x = graphCenterX - (hw / 2.0);
        resHero.y = currHeroY;
        resHero.width = hw;
        resHero.height = hero.height || 120.0;
        currHeroY += (hero.height || 120.0) + 20.0;
      }
    });
  }

  fixShortEdgeStubs(layoutResultData);

  return layoutResultData;
}

/**
 * Full Node-callable layout pipeline: builds the ELK input graph, runs it
 * through plain (non-Worker) elkjs, and post-processes the result into the
 * final positioned graph. This is the entry point for vitest and the future
 * layout-cli — layout.worker.ts does NOT call this (see the note at the top
 * of this file for why); it calls `buildElkGraph`/`postProcessLayoutResult`
 * directly around its own existing GWT dispatch.
 */
export async function computeLayout(request: LayoutRequest): Promise<any> {
  const elkRoot = buildElkGraph(request);
  const elk = new ELK();
  const layoutResultData = await elk.layout(elkRoot);
  return postProcessLayoutResult(layoutResultData, request.elements);
}
