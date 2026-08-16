import type { QualityNode, QualityConnection, QualityCheckResult } from './types';
import { resolveLabelPositions } from '../workers/layoutCore';
import { checkZeroNodeOverlaps } from './checkZeroNodeOverlaps';
import { checkNonNegativeCanvasBounds } from './checkNonNegativeCanvasBounds';
import { checkUniqueNodeIds } from './checkUniqueNodeIds';
import { checkPanelHeaderFits } from './checkPanelHeaderFits';
import { checkDirectionalPortNormalStubs } from './checkDirectionalPortNormalStubs';
import { checkMultiConnectionPortSpacing } from './checkMultiConnectionPortSpacing';
import { checkNoUnrelatedPanelCrossings } from './checkNoUnrelatedPanelCrossings';
import { checkNoLabelOverlaps } from './checkNoLabelOverlaps';

export type { QualityNode, QualityConnection, QualityCheckResult };
export {
  flattenLayoutNodes,
  flattenLayoutEdges,
} from './types';
export { checkZeroNodeOverlaps } from './checkZeroNodeOverlaps';
export { checkNonNegativeCanvasBounds } from './checkNonNegativeCanvasBounds';
export { checkUniqueNodeIds } from './checkUniqueNodeIds';
export { checkPanelHeaderFits } from './checkPanelHeaderFits';
export { checkDirectionalPortNormalStubs } from './checkDirectionalPortNormalStubs';
export { checkMultiConnectionPortSpacing } from './checkMultiConnectionPortSpacing';
export { checkNoUnrelatedPanelCrossings } from './checkNoUnrelatedPanelCrossings';
export { checkNoLabelOverlaps } from './checkNoLabelOverlaps';

export interface LayoutQualityReport {
  ok: boolean;
  checks: QualityCheckResult[];
}

/**
 * Executes the complete layout quality assertion suite against a flattened
 * positioned graph (see types.ts's flattenLayoutNodes/flattenLayoutEdges for
 * how to produce these from a computeLayout() result).
 *
 * Mirrors layout_quality.py's check_layout_quality(). Skips the two Python
 * checks that don't apply frontend-side: check_gif_has_motion (GIF export
 * verification — a rendering-pipeline concern, not a layout one) and
 * check_title_badge_clearance (Python's decor_title_* page-decoration
 * concept has no frontend equivalent).
 */
export function checkLayoutQuality(
  nodes: QualityNode[],
  connections: QualityConnection[]
): LayoutQualityReport {
  // Resolve every labeled connection's on-canvas label position once,
  // globally — mirrors exactly what useFlowLayout.ts's runtime pipeline
  // does after layout, so this check verifies the SAME resolution logic
  // production actually renders with (see layoutCore.ts's
  // resolveLabelPositions for the full port of
  // scripts/flowdraft/layout_engine.py's position_connection_label).
  const labelNodes = nodes.map((n) => ({
    id: n.id,
    type: n.type,
    x: n.absX,
    y: n.absY,
    width: n.width,
    height: n.height,
  }));
  const labelEdges = connections.map((c, i) => ({
    id: c.id || `conn-${i}`,
    points: c.points,
    label: c.label,
  }));
  const labelPositions = resolveLabelPositions(labelEdges, labelNodes);
  const connectionsWithLabels: QualityConnection[] = connections.map((c, i) => {
    const pos = labelPositions.get(c.id || `conn-${i}`);
    return pos ? { ...c, labelX: pos.x, labelY: pos.y } : c;
  });

  const checks = [
    checkZeroNodeOverlaps(nodes),
    checkNonNegativeCanvasBounds(nodes),
    checkUniqueNodeIds(nodes),
    checkPanelHeaderFits(nodes),
    checkDirectionalPortNormalStubs(connections),
    checkMultiConnectionPortSpacing(connections),
    checkNoUnrelatedPanelCrossings(nodes, connections),
    checkNoLabelOverlaps(connectionsWithLabels),
  ];

  return {
    ok: checks.every((c) => c.ok),
    checks,
  };
}
