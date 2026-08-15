import type { QualityNode, QualityCheckResult } from './types';

/**
 * Assert every node's canvas-absolute position satisfies x >= minX (20) and
 * y >= minY (20). Ported from layout_quality.py's check_non_negative_canvas_bounds.
 *
 * Deliberately uses absX/absY (accumulated through the full parent chain),
 * not the node's parent-relative x/y: layoutCore.ts panels take a
 * user-configurable `layout.padding.left` that can legitimately be well
 * under 20 (the default spec's panels use 12), so a nested child's raw
 * relative x can be e.g. 12 without that indicating any real problem — the
 * "stays on canvas, not clipped at the top-left" invariant this check exists
 * for is inherently a statement about the single global canvas frame.
 */
export function checkNonNegativeCanvasBounds(
  nodes: QualityNode[],
  minX = 20,
  minY = 20
): QualityCheckResult {
  const invalid: [string, number, number][] = [];

  nodes.forEach((n) => {
    if (n.id.startsWith('decor_') || n.out_of_flow) return;
    if (n.absX < minX || n.absY < minY) {
      invalid.push([n.id, n.absX, n.absY]);
    }
  });

  return { name: 'non_negative_canvas_bounds', ok: invalid.length === 0, invalid };
}
