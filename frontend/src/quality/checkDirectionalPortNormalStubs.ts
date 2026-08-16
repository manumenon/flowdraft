import { getPortNormal, type PortSide } from '../utils/directionalPorts';
import type { QualityConnection, QualityCheckResult } from './types';

// Spec-level port words ('top'/'bottom'/'left'/'right' — see PortType in
// types/spec.ts) map onto directionalPorts.ts's compass-side vocabulary.
const PORT_WORD_TO_SIDE: Record<string, PortSide> = {
  top: 'NORTH',
  bottom: 'SOUTH',
  left: 'WEST',
  right: 'EAST',
};

function resolveSide(word: string | undefined, fallback: PortSide): PortSide {
  if (!word) return fallback;
  return PORT_WORD_TO_SIDE[word.toLowerCase()] || fallback;
}

/**
 * Assert initial and final connection segments extend at least min_stub_len
 * (16px) perpendicular to the port's side before the route bends. Ported
 * from layout_quality.py's check_directional_port_normal_stubs, reusing
 * `getPortNormal` from directionalPorts.ts (already correct, previously
 * unused) exactly as Python's port reused `get_port_normal` from geometry.py.
 *
 * A bend-free 2-point connection (pts.length === 2 — the whole path is a
 * single straight segment directly between its two ports, no bend at all)
 * is exempt from the length floor: the "stub" concept this guards against
 * is a route that turns too sharply right after leaving a port, reading as
 * the line clipping the node's edge — with FIXED_SIDE ports and ORTHOGONAL
 * routing, a 2-point segment can only exist when the two ports already sit
 * directly in line, so it's inherently a single clean run the full
 * distance in the correct direction with no turn to clip against,
 * regardless of how short that distance is (e.g. two directly-stacked
 * panel children only `layout.gap` apart, which can legitimately be well
 * under 16px — see layoutCore.ts's postProcessLayoutResult's row/column
 * reprojection, whose adjacent-stack connectors are exactly this shape).
 */
export function checkDirectionalPortNormalStubs(
  connections: QualityConnection[],
  minStubLen = 16.0
): QualityCheckResult {
  const invalid: any[] = [];
  const tol = 0.5;

  connections.forEach((conn) => {
    const cid = conn.id || `${conn.from}->${conn.to}`;
    const pts = conn.points;
    if (!pts || pts.length < 2) return;
    if (pts.length === 2) return;

    const p0 = pts[0];
    const p1 = pts[1];
    const pN1 = pts[pts.length - 2];
    const pN = pts[pts.length - 1];

    const fromSide = resolveSide(conn.exitPort || conn.fromPort, 'SOUTH');
    const toSide = resolveSide(conn.entryPort || conn.toPort, 'NORTH');

    // Start stub: vector leaving the start port along its outward normal.
    const startNorm = getPortNormal(fromSide);
    const startVecX = p1[0] - p0[0];
    const startVecY = p1[1] - p0[1];
    const startStubProj = startVecX * startNorm.x + startVecY * startNorm.y;
    if (startStubProj < minStubLen - tol) {
      invalid.push({
        connection: cid,
        port: 'exitPort',
        side: fromSide,
        expectedStub: minStubLen,
        actualStub: startStubProj,
      });
    }

    // End stub: vector leaving the end port outwards (pN-1 - pN) along its normal.
    const endNorm = getPortNormal(toSide);
    const endOutVecX = pN1[0] - pN[0];
    const endOutVecY = pN1[1] - pN[1];
    const endStubProj = endOutVecX * endNorm.x + endOutVecY * endNorm.y;
    if (endStubProj < minStubLen - tol) {
      invalid.push({
        connection: cid,
        port: 'entryPort',
        side: toSide,
        expectedStub: minStubLen,
        actualStub: endStubProj,
      });
    }
  });

  return { name: 'directional_port_normal_stubs', ok: invalid.length === 0, invalid };
}
