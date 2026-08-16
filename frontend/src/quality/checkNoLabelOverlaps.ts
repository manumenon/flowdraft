import type { QualityConnection, QualityCheckResult } from './types';
import { estimateLabelBoxSize } from '../workers/layoutCore';

/**
 * Assert no two connections' rendered label bounding boxes overlap.
 *
 * This is a pure verification step — it does NOT compute label positions
 * itself, only checks the `labelX`/`labelY` already resolved onto each
 * connection (by `layoutCore.ts`'s `resolveLabelPositions`, called once,
 * globally, before this check runs — see `checkLayoutQuality`). That
 * mirrors every other check in this suite (e.g. `checkZeroNodeOverlaps`
 * verifies node placement rather than computing it).
 *
 * Guards against a real, confirmed bug from this session: RoutedEdge.tsx
 * used to compute each edge's label position independently at render time
 * (`getArcLengthMidpoint(basePoints)`, with zero awareness of any other
 * edge's label), which let two nearly-parallel connections' labels ("VOD
 * REQUEST" and "EMIT PLAYBACK EVENT") land stacked directly on top of each
 * other in a dense, real rendered export. See
 * `checkLayoutQuality.test.ts`'s "label overlap regression" tests for a
 * reproduction of exactly that pattern, including a demonstration that this
 * check fails without `resolveLabelPositions`'s collision avoidance.
 */
export function checkNoLabelOverlaps(connections: QualityConnection[]): QualityCheckResult {
  const labeled = connections.filter(
    (c) => c.label && typeof c.labelX === 'number' && typeof c.labelY === 'number'
  );

  const boxes = labeled.map((c) => {
    const { width, height } = estimateLabelBoxSize(c.label!);
    const x = c.labelX!;
    const y = c.labelY!;
    return {
      id: c.id,
      label: c.label,
      x1: x - width / 2,
      y1: y - height / 2,
      x2: x + width / 2,
      y2: y + height / 2,
    };
  });

  const overlaps: { a?: string; b?: string; aLabel?: string; bLabel?: string }[] = [];
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i];
      const b = boxes[j];
      if (a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1) {
        overlaps.push({ a: a.id, b: b.id, aLabel: a.label, bLabel: b.label });
      }
    }
  }

  return { name: 'no_label_overlaps', ok: overlaps.length === 0, overlaps };
}
