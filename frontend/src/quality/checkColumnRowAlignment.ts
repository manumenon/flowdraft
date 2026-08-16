import type { QualityNode, QualityCheckResult } from './types';
import { computePanelHeaderPad } from '../workers/layoutCore';

/**
 * Assert that every 'column'-direction panel's direct children share a
 * consistent x (a clean vertical stack) and every 'row'-direction panel's
 * direct children share a consistent y (a clean horizontal stack) —
 * restricted to panels whose declared direction actually MISMATCHES the
 * root's effective direction (`rootLayoutDirection`, the same
 * `canvas.layoutDirection` spec field buildElkGraph/postProcessLayoutResult
 * resolve via resolveRootElkDirection: 'vertical' => DOWN, anything else
 * => RIGHT).
 *
 * This is the literal symptom of the elkjs#26 direction-mismatch bug this
 * check exists to catch: when a panel's own declared
 * 'org.eclipse.elk.direction' doesn't match the root's effective direction,
 * INCLUDE_CHILDREN hierarchy handling silently ignores it and ranks the
 * panel's children along the ROOT's own primary axis instead — producing a
 * diagonal cascade (both x AND y increasing together) rather than a clean
 * single-axis stack, and inflating the panel's bounding box to match. See
 * layoutCore.ts's postProcessLayoutResult (search "row/column panels whose
 * declared ELK direction") for the reprojection fix this check guards.
 *
 * The mismatch restriction matters, not just as an optimization: a panel
 * whose direction already MATCHES the root gets ELK's normal, correct
 * layered placement — which is free to legitimately vary the cross-axis
 * coordinate between differently-sized children (e.g. a 'row' panel
 * mixing plain cards with a much taller nested sub-panel will not
 * generally line every child up on one exact y, and that's fine, not a
 * bug). Asserting strict alignment there produces false positives against
 * real, healthy data (confirmed against stressSpec.ts's core_panel/
 * storage_panel/edge_gateway_panel while building this check) — only
 * mismatched panels are guaranteed (by the reprojection fix) to come out
 * perfectly axis-aligned, so only they are asserted here.
 *
 * Only panels with >= 2 children are checked (a single child trivially has
 * a "consistent" position with itself, and the bug can't manifest as a
 * cascade with nothing to cascade against). 'flow'/'grid' panels are a
 * different, already-covered box-packing mode and are skipped here.
 *
 * One more restriction, mirroring a real limit of the fix itself: a
 * mismatched panel is only reprojected into a clean stack when doing so
 * fits within ELK's own already-reserved footprint for it (computed here
 * the same way layoutCore.ts's postProcessLayoutResult does, down to
 * reusing its own computePanelHeaderPad). A panel whose stacked children
 * include one disproportionately large nested sub-panel (see
 * stressSpec.ts's right_agent_panel, stacking a 943px-tall nested flow
 * panel below two 140px cards) can genuinely need MORE room laid out
 * cleanly than ELK's diagonal cascade did — reprojecting it anyway was
 * confirmed, during development, to newly violate
 * checkNoUnrelatedPanelCrossings (other, unrelated edges routed by ELK
 * assuming only the original, smaller footprint was reserved space). The
 * fix bails out of reprojecting such a panel rather than risk that
 * regression, so this check derives the identical "would it fit" condition
 * from geometry (not by exempting specific panel ids, which would go
 * stale) and only asserts alignment where the fix actually guarantees it.
 */
export function checkColumnRowAlignment(
  nodes: QualityNode[],
  rootLayoutDirection?: string
): QualityCheckResult {
  const violations: any[] = [];
  const tol = 1.5;
  const rootElkDir = rootLayoutDirection === 'vertical' ? 'DOWN' : 'RIGHT';
  const headerPads = computePanelHeaderPad(nodes);

  const panels = nodes.filter((n) => n.type === 'panel' || n.type === 'group');

  panels.forEach((panel) => {
    const direction = panel.layout?.direction;
    if (direction !== 'row' && direction !== 'column') return;

    const panelElkDir = direction === 'column' ? 'DOWN' : 'RIGHT';
    if (panelElkDir === rootElkDir) return;

    const children = nodes.filter((n) => n.parent === panel.id);
    if (children.length < 2) return;

    let padLeft = 20, padBottom = 20, padRight = 20;
    const rawPad = panel.layout?.padding;
    if (typeof rawPad === 'number') {
      padLeft = rawPad; padBottom = rawPad; padRight = rawPad;
    } else if (rawPad) {
      padLeft = rawPad.left ?? 20;
      padBottom = rawPad.bottom ?? 20;
      padRight = rawPad.right ?? 20;
    }
    const gap = panel.layout?.gap ?? 20;
    const topPad = headerPads[panel.id] || 40;

    const neededWidth = direction === 'column'
      ? padLeft + Math.max(...children.map((c) => c.width)) + padRight
      : padLeft + children.reduce((sum, c) => sum + c.width, 0) + (children.length - 1) * gap + padRight;
    const neededHeight = direction === 'column'
      ? topPad + children.reduce((sum, c) => sum + c.height, 0) + (children.length - 1) * gap + padBottom
      : topPad + Math.max(...children.map((c) => c.height)) + padBottom;

    if (neededWidth > panel.width + 0.5 || neededHeight > panel.height + 0.5) return;

    const axis: 'x' | 'y' = direction === 'column' ? 'x' : 'y';
    const values = children.map((c) => c[axis]);
    const minV = Math.min(...values);
    const maxV = Math.max(...values);
    const spread = maxV - minV;

    if (spread > tol) {
      violations.push({
        panel: panel.id,
        direction,
        axis,
        spread,
        children: children.map((c) => ({ id: c.id, [axis]: c[axis] })),
      });
    }
  });

  return { name: 'column_row_alignment', ok: violations.length === 0, violations };
}
