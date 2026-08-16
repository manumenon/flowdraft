// Shared types + adapters for the layout quality-check suite.
//
// Python's scripts/flowdraft/layout_quality.py checks operate on a flat list
// of IR node dicts that already carry both geometry (x/y/width/height) and
// content (title/badge/type/parent/...) in one place. layoutCore.ts's output
// is split instead: `computeLayout()` returns a nested ELK-shaped tree with
// only geometry, while the content lives on the separate `elements` array
// passed into the request. `flattenLayoutNodes`/`flattenLayoutEdges` below
// re-merge those into the flat shape the checks expect, mirroring the exact
// coordinate conventions the real app already relies on downstream
// (`useFlowLayout.ts`'s `collectNodes`/`collectEdges`):
//   - node x/y stay PARENT-RELATIVE (same as React Flow's `position` for a
//     node with `parentId` + `extent: 'parent'` — see specCompiler.ts).
//   - node absX/absY are the accumulated CANVAS-ABSOLUTE position (summing
//     every ancestor's relative offset), needed for checks like canvas
//     bounds where "20px from the edge" only means something in a single
//     global frame.
//   - connection points are always CANVAS-ABSOLUTE (ELK routes an edge's
//     sections relative to whichever container owns that edge — the edge's
//     nearest common-ancestor panel, or root for cross-panel edges — so
//     comparing raw points across connections is only valid once they've
//     all been normalized into one frame, exactly what `collectEdges` does).

export interface QualityNode {
  id: string;
  type?: string;
  parent: string | null;
  /** Position relative to the immediate parent container (0,0 for top-level). */
  x: number;
  y: number;
  /** Position accumulated through the full parent chain (canvas-absolute). */
  absX: number;
  absY: number;
  width: number;
  height: number;
  title?: string;
  subtitle?: string;
  badge?: string;
  layout?: any;
  out_of_flow?: boolean;
}

export interface QualityConnection {
  id?: string;
  from: string;
  to: string;
  exitPort?: string;
  entryPort?: string;
  fromPort?: string;
  toPort?: string;
  /** Canvas-absolute [x, y] points along the routed edge, start to end. */
  points: [number, number][];
  label?: string;
  /** Canvas-absolute resolved label position (see layoutCore.ts's resolveLabelPositions). */
  labelX?: number;
  labelY?: number;
}

export interface QualityCheckResult {
  name: string;
  ok: boolean;
  [key: string]: any;
}

/**
 * Flattens a `computeLayout()` result into a flat list of `QualityNode`,
 * merging each ELK result node's geometry with its matching input element's
 * content fields (title/subtitle/badge/type/layout/...) looked up by id.
 * Skips the synthetic 'root' node, same as `useFlowLayout.ts`'s `collectNodes`.
 */
export function flattenLayoutNodes(layoutResult: any, elements: any[]): QualityNode[] {
  const elementsById = new Map<string, any>();
  elements.forEach((el) => elementsById.set(el.id, el));

  const nodes: QualityNode[] = [];

  const collect = (
    resultNode: any,
    parentId: string | null,
    parentAbsX: number,
    parentAbsY: number
  ) => {
    const relX = Number(resultNode.x) || 0;
    const relY = Number(resultNode.y) || 0;
    const isRoot = resultNode.id === 'root';
    const absX = isRoot ? 0 : parentAbsX + relX;
    const absY = isRoot ? 0 : parentAbsY + relY;

    if (!isRoot) {
      const srcEl = elementsById.get(resultNode.id) || {};
      nodes.push({
        id: resultNode.id,
        type: srcEl.type,
        parent: srcEl.parent ?? parentId,
        x: relX,
        y: relY,
        absX,
        absY,
        width: Number(resultNode.width) || 0,
        height: Number(resultNode.height) || 0,
        title: srcEl.title,
        subtitle: srcEl.subtitle,
        badge: srcEl.badge,
        layout: srcEl.layout,
        out_of_flow: srcEl.out_of_flow,
      });
    }

    (resultNode.children || []).forEach((child: any) =>
      collect(child, isRoot ? null : resultNode.id, absX, absY)
    );
  };

  collect(layoutResult, null, 0, 0);
  return nodes;
}

/**
 * Flattens a `computeLayout()` result's per-container edges into a flat list
 * of `QualityConnection` with canvas-absolute points, and re-attaches each
 * edge's originating `exitPort`/`entryPort` by recovering its index from the
 * ELK edge id (`edge-${from}-${to}-${i}`, the exact format buildElkGraph
 * assigns) — the trailing `-\d+` is always the array index since `i` is a
 * plain integer with no hyphens, so anchoring the match to the end of the
 * string finds it regardless of what characters appear in `from`/`to`.
 * Mirrors `useFlowLayout.ts`'s `collectEdges` absolute-position accumulation.
 */
export function flattenLayoutEdges(layoutResult: any, connections: any[]): QualityConnection[] {
  const raw: { id: string; points: [number, number][] }[] = [];

  const collect = (resultNode: any, absX: number, absY: number) => {
    const isRoot = resultNode.id === 'root';
    const nodeAbsX = absX + (resultNode.x || 0);
    const nodeAbsY = absY + (resultNode.y || 0);

    (resultNode.edges || []).forEach((edge: any) => {
      const points: [number, number][] = [];
      (edge.sections || []).forEach((sec: any) => {
        points.push([sec.startPoint.x + nodeAbsX, sec.startPoint.y + nodeAbsY]);
        (sec.bendPoints || []).forEach((bp: any) => {
          points.push([bp.x + nodeAbsX, bp.y + nodeAbsY]);
        });
        points.push([sec.endPoint.x + nodeAbsX, sec.endPoint.y + nodeAbsY]);
      });
      raw.push({ id: edge.id, points });
    });

    (resultNode.children || []).forEach((child: any) => {
      const parentX = isRoot ? 0 : nodeAbsX;
      const parentY = isRoot ? 0 : nodeAbsY;
      collect(child, parentX, parentY);
    });
  };

  collect(layoutResult, 0, 0);

  return raw.map((e) => {
    const match = /-(\d+)$/.exec(e.id);
    const idx = match ? Number(match[1]) : -1;
    const conn = connections[idx] || {};
    return {
      id: e.id,
      from: conn.from,
      to: conn.to,
      exitPort: conn.exitPort,
      entryPort: conn.entryPort,
      fromPort: conn.fromPort,
      toPort: conn.toPort,
      points: e.points,
      label: conn.label,
    };
  });
}
