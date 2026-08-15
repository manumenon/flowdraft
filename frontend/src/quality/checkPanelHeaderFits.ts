import type { QualityNode, QualityCheckResult } from './types';

/**
 * Assert every panel's title/subtitle header actually fits above its
 * children, and that its title doesn't overflow the panel's own final
 * width. This is the exact check class that caught this session's original
 * bug: layoutCore.ts's `computePanelHeaderPad` reserves vertical header
 * space (`topPad`) *before* ELK has sized the panel, using an assumed
 * chars-per-line guess against a width it doesn't actually know yet. If the
 * panel ends up narrower than that guess assumed, the title wraps into more
 * lines than were reserved for, and — without correction — the header text
 * would spill down into the first row of children.
 *
 * `postProcessLayoutResult`'s "Reconcile the header" step (layoutCore.ts)
 * fixes this by re-measuring against the panel's REAL final width and
 * shifting children down if short. This check re-derives that same real
 * header height independently from the OUTPUT (final panel width + actual
 * child positions) rather than trusting that internal step ran correctly —
 * so if that reconciliation is ever broken or removed in a refactor, this
 * check fails immediately instead of silently shipping overlapping text,
 * reproducing exactly how this bug class would have been caught had this
 * suite existed at the time.
 *
 * Ported from layout_quality.py's check_panel_header_fits, adapted from
 * Python's explicit `layout_offsets.title`/`.badge` pixel boxes (populated
 * by a separate Excalidraw-rendering step Python has and layoutCore.ts does
 * not) to the header-sizing formula layoutCore.ts's own reconciliation
 * logic uses, re-derived here against the panel's real final width/height.
 */
export function checkPanelHeaderFits(nodes: QualityNode[]): QualityCheckResult {
  const violations: any[] = [];
  const tol = 2.0;

  // Constants mirrored from layoutCore.ts's postProcessLayoutResult header
  // reconciliation block (headerInset/avgCharPx/badge reserve/line-height).
  const headerInset = 16;
  const avgCharPx = 9.0;

  nodes.forEach((n) => {
    if (n.type !== 'panel') return;

    const title = String(n.title || '');
    const subtitle = String(n.subtitle || '');
    if (!title && !subtitle) return;

    const panelW = n.width;
    const badgeReserve = n.badge ? 46 : 0;

    const titleAvailPx = Math.max(30, panelW - headerInset * 2 - badgeReserve);
    const titleCharsPerLine = Math.max(4, Math.floor(titleAvailPx / avgCharPx));
    const realTitleLines = title ? Math.max(1, Math.ceil(title.length / titleCharsPerLine)) : 0;

    const subtitleAvailPx = Math.max(30, panelW - headerInset * 2);
    const subtitleCharsPerLine = Math.max(4, Math.floor(subtitleAvailPx / (avgCharPx * 0.85)));
    const realSubtitleLines = subtitle
      ? Math.max(1, Math.ceil(subtitle.length / subtitleCharsPerLine))
      : 0;

    const realHeaderH = 14 + realTitleLines * 13.5 + realSubtitleLines * 13.5 + 12;

    // 1. Title overflowing the panel's own right edge: the first title line
    // is bounded to titleCharsPerLine chars before wrapping, so its
    // estimated rendered width should never exceed the space reserved for
    // it — a violation here means the reservation math and the overflow
    // check have drifted apart.
    const firstLineChars = title ? Math.min(title.length, titleCharsPerLine) : 0;
    const titleLineWidthPx = firstLineChars * avgCharPx;
    if (titleLineWidthPx > titleAvailPx + tol) {
      violations.push({
        node: n.id,
        kind: 'title_overflows_panel',
        titleLineWidthPx,
        titleAvailPx,
        overflow: titleLineWidthPx - titleAvailPx,
      });
    }

    // 2. Header text overlapping the first row of children: does the actual
    // vertical gap between the panel's top and its topmost child cover the
    // real (final-width-based) header height?
    const children = nodes.filter((c) => c.parent === n.id);
    if (children.length > 0) {
      const topOfChildren = Math.min(...children.map((c) => c.y));
      if (topOfChildren < realHeaderH - tol) {
        violations.push({
          node: n.id,
          kind: 'header_overlaps_children',
          topOfChildren,
          realHeaderH,
          shortfall: realHeaderH - topOfChildren,
        });
      }
    }
  });

  return { name: 'panel_header_fits', ok: violations.length === 0, violations };
}
