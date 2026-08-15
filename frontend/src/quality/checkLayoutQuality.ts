import type { QualityNode, QualityConnection, QualityCheckResult } from './types';
import { checkZeroNodeOverlaps } from './checkZeroNodeOverlaps';
import { checkNonNegativeCanvasBounds } from './checkNonNegativeCanvasBounds';
import { checkUniqueNodeIds } from './checkUniqueNodeIds';
import { checkPanelHeaderFits } from './checkPanelHeaderFits';
import { checkDirectionalPortNormalStubs } from './checkDirectionalPortNormalStubs';
import { checkMultiConnectionPortSpacing } from './checkMultiConnectionPortSpacing';
import { checkNoUnrelatedPanelCrossings } from './checkNoUnrelatedPanelCrossings';

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
  const checks = [
    checkZeroNodeOverlaps(nodes),
    checkNonNegativeCanvasBounds(nodes),
    checkUniqueNodeIds(nodes),
    checkPanelHeaderFits(nodes),
    checkDirectionalPortNormalStubs(connections),
    checkMultiConnectionPortSpacing(connections),
    checkNoUnrelatedPanelCrossings(nodes, connections),
  ];

  return {
    ok: checks.every((c) => c.ok),
    checks,
  };
}
