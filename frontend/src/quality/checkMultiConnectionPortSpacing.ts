import type { QualityConnection, QualityCheckResult } from './types';

const VERTICAL_SIDES = new Set(['left', 'right', 'west', 'east']);

/**
 * Assert parallel connections sharing the same node side maintain at least
 * min_spacing (16px) between their port offsets along that side. Ported
 * from layout_quality.py's check_multi_connection_port_spacing.
 *
 * Relies on `points` already being canvas-absolute (see types.ts /
 * flattenLayoutEdges) — connections converging on the same node/side can
 * originate from different ELK containers (a panel's own edge list vs.
 * root's), so comparing their raw parent-relative coordinates would compare
 * apples to oranges; absolute coordinates put every connection touching a
 * given node in one consistent frame.
 */
export function checkMultiConnectionPortSpacing(
  connections: QualityConnection[],
  minSpacing = 16.0
): QualityCheckResult {
  const invalid: any[] = [];
  const tol = 0.5;

  // Key: `${nodeId}|${side}|${'exit'|'entry'}` -> offsets along that side.
  const sidePorts = new Map<string, number[]>();

  connections.forEach((conn) => {
    const pts = conn.points;
    if (!pts || pts.length < 2) return;

    const fromSide = (conn.exitPort || conn.fromPort || 'bottom').toLowerCase();
    if (conn.from) {
      const [x0, y0] = pts[0];
      const pos0 = VERTICAL_SIDES.has(fromSide) ? y0 : x0;
      const key = `${conn.from}|${fromSide}|exit`;
      if (!sidePorts.has(key)) sidePorts.set(key, []);
      sidePorts.get(key)!.push(pos0);
    }

    const toSide = (conn.entryPort || conn.toPort || 'top').toLowerCase();
    if (conn.to) {
      const [xN, yN] = pts[pts.length - 1];
      const posN = VERTICAL_SIDES.has(toSide) ? yN : xN;
      const key = `${conn.to}|${toSide}|entry`;
      if (!sidePorts.has(key)) sidePorts.set(key, []);
      sidePorts.get(key)!.push(posN);
    }
  });

  sidePorts.forEach((positions, key) => {
    if (positions.length < 2) return;
    const [nodeId, side, direction] = key.split('|');
    const sorted = [...positions].sort((a, b) => a - b);
    for (let i = 0; i < sorted.length - 1; i++) {
      const gap = sorted[i + 1] - sorted[i];
      if (gap < minSpacing - tol) {
        invalid.push({
          node: nodeId,
          side,
          direction,
          spacing: gap,
          minRequired: minSpacing,
        });
      }
    }
  });

  return { name: 'multi_connection_port_spacing', ok: invalid.length === 0, invalid };
}
