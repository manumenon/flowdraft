import type { QualityNode, QualityConnection, QualityCheckResult } from './types';

/**
 * Segment-vs-rectangle intersection test (Liang-Barsky line clipping),
 * shrinking the rectangle inward by `margin` first so a segment that merely
 * runs flush along a panel's boundary (e.g. exiting right alongside a
 * neighboring sibling panel's edge) doesn't register as "cutting through the
 * interior" — only a segment that actually enters the shrunk interior does.
 * Works for both axis-aligned (the common case here — ELK's own routing is
 * always orthogonal) and arbitrary segments alike.
 */
function segmentIntersectsRectInterior(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  rx: number,
  ry: number,
  rw: number,
  rh: number,
  margin = 0.5
): boolean {
  const xmin = rx + margin;
  const xmax = rx + rw - margin;
  const ymin = ry + margin;
  const ymax = ry + rh - margin;
  if (xmin >= xmax || ymin >= ymax) return false;

  const dx = x2 - x1;
  const dy = y2 - y1;
  const p = [-dx, dx, -dy, dy];
  const q = [x1 - xmin, xmax - x1, y1 - ymin, ymax - y1];

  let t0 = 0;
  let t1 = 1;

  for (let i = 0; i < 4; i++) {
    if (p[i] === 0) {
      if (q[i] < 0) return false; // segment parallel to this edge and outside it
    } else {
      const r = q[i] / p[i];
      if (p[i] < 0) {
        if (r > t1) return false;
        if (r > t0) t0 = r;
      } else {
        if (r < t0) return false;
        if (r < t1) t1 = r;
      }
    }
  }

  return t0 < t1;
}

/**
 * Assert no connection's routed segments cut through the interior of a panel
 * that isn't an ancestor of that connection's own source or target (i.e. a
 * genuinely unrelated panel/card it should have routed around, not a
 * container it legitimately starts or ends inside of).
 *
 * This is the geometric evidence-gathering check for plan item 3's "prove
 * the static (exported) routing is clean" — it runs against ELK's own
 * `edge.sections`-derived routing (via `flattenLayoutEdges`/`flattenLayoutNodes`
 * in types.ts), NOT the RoutedEdge.tsx live-drag fallback, since the static
 * ELK path is what actually gets exported/screenshotted.
 */
export function checkNoUnrelatedPanelCrossings(
  nodes: QualityNode[],
  connections: QualityConnection[]
): QualityCheckResult {
  const violations: any[] = [];

  const nodesById = new Map<string, QualityNode>();
  nodes.forEach((n) => nodesById.set(n.id, n));

  const panels = nodes.filter((n) => n.type === 'panel');

  // Ancestor panel ids of a node (walking `parent` up to the root), NOT
  // including the node's own id — mirrors RoutedEdge.tsx's getAbsPosition
  // parent-chain walk.
  const ancestorsOf = (id: string | undefined): Set<string> => {
    const result = new Set<string>();
    let curr = id ? nodesById.get(id) : undefined;
    while (curr && curr.parent) {
      result.add(curr.parent);
      curr = nodesById.get(curr.parent);
    }
    return result;
  };

  connections.forEach((conn) => {
    const pts = conn.points;
    if (!pts || pts.length < 2) return;

    // A panel is "related" to this connection if it's an ancestor of the
    // source, an ancestor of the target, or is the source/target itself
    // (a connection legitimately starts/ends flush against its own
    // container's boundary — that's not a crossing).
    const related = new Set<string>([
      ...ancestorsOf(conn.from),
      ...ancestorsOf(conn.to),
    ]);
    if (conn.from) related.add(conn.from);
    if (conn.to) related.add(conn.to);

    const unrelatedPanels = panels.filter((p) => !related.has(p.id));
    if (unrelatedPanels.length === 0) return;

    for (let i = 0; i < pts.length - 1; i++) {
      const [x1, y1] = pts[i];
      const [x2, y2] = pts[i + 1];

      for (const panel of unrelatedPanels) {
        if (
          segmentIntersectsRectInterior(
            x1,
            y1,
            x2,
            y2,
            panel.absX,
            panel.absY,
            panel.width,
            panel.height
          )
        ) {
          violations.push({
            connection: conn.id || `${conn.from}->${conn.to}`,
            panel: panel.id,
            segmentIndex: i,
            segment: [
              [x1, y1],
              [x2, y2],
            ],
          });
        }
      }
    }
  });

  return { name: 'no_unrelated_panel_crossings', ok: violations.length === 0, violations };
}
