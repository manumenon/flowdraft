import type { QualityNode, QualityCheckResult } from './types';

/**
 * Assert no pair of sibling nodes (nodes sharing the same parent — panels
 * never overlap each other structurally by construction, so only
 * intra-container overlap needs checking, matching Python's scope) overlap
 * bounding boxes. Ported from layout_quality.py's check_zero_node_overlaps.
 *
 * Uses parent-relative x/y (not absX/absY): since both nodes in every
 * comparison share the same parent, both coordinates carry the identical
 * offset, so relative vs. absolute makes no difference to the comparison —
 * relative is used because it's the layout's native per-node output.
 */
export function checkZeroNodeOverlaps(nodes: QualityNode[]): QualityCheckResult {
  const overlaps: [string, string][] = [];

  const byParent = new Map<string | null, QualityNode[]>();
  nodes.forEach((n) => {
    const key = n.parent ?? null;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key)!.push(n);
  });

  byParent.forEach((group) => {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const n1 = group[i];
        const n2 = group[j];

        // Skip panel/container/group nodes (containers are expected to
        // enclose their children, not stay disjoint from them) and any
        // out-of-flow or decorative node.
        if (n1.type === 'panel' || n1.type === 'container' || n1.type === 'group') continue;
        if (n2.type === 'panel' || n2.type === 'container' || n2.type === 'group') continue;
        if (n1.out_of_flow || n2.out_of_flow) continue;
        if (n1.id.startsWith('decor_') || n2.id.startsWith('decor_')) continue;

        const x1 = n1.x, y1 = n1.y, w1 = n1.width, h1 = n1.height;
        const x2 = n2.x, y2 = n2.y, w2 = n2.width, h2 = n2.height;

        // Strict interior intersection.
        if (x1 < x2 + w2 && x1 + w1 > x2 && y1 < y2 + h2 && y1 + h1 > y2) {
          overlaps.push([n1.id, n2.id]);
        }
      }
    }
  });

  return { name: 'zero_node_overlaps', ok: overlaps.length === 0, overlaps };
}
