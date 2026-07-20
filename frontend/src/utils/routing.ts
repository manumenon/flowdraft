/**
 * Computes a parallel offset path for a given polyline.
 * Useful for routing multiple parallel connections between the same nodes.
 */
export function computeParallelOffset(points: [number, number][], offset: number): [number, number][] {
  if (offset === 0 || points.length < 2) return points;

  const result: [number, number][] = [];
  const n = points.length;

  for (let i = 0; i < n; i++) {
    const p = points[i];
    if (i === 0) {
      const next = points[1];
      const dx = next[0] - p[0];
      const dy = next[1] - p[1];
      const len = Math.hypot(dx, dy);
      if (len === 0) {
        result.push([p[0], p[1]]);
      } else {
        const nx = -dy / len;
        const ny = dx / len;
        result.push([p[0] + nx * offset, p[1] + ny * offset]);
      }
    } else if (i === n - 1) {
      const prev = points[n - 2];
      const dx = p[0] - prev[0];
      const dy = p[1] - prev[1];
      const len = Math.hypot(dx, dy);
      if (len === 0) {
        result.push([p[0], p[1]]);
      } else {
        const nx = -dy / len;
        const ny = dx / len;
        result.push([p[0] + nx * offset, p[1] + ny * offset]);
      }
    } else {
      const prev = points[i - 1];
      const next = points[i + 1];

      const dx1 = p[0] - prev[0];
      const dy1 = p[1] - prev[1];
      const len1 = Math.hypot(dx1, dy1);

      const dx2 = next[0] - p[0];
      const dy2 = next[1] - p[1];
      const len2 = Math.hypot(dx2, dy2);

      if (len1 === 0 && len2 === 0) {
        result.push([p[0], p[1]]);
      } else if (len1 === 0) {
        const nx = -dy2 / len2;
        const ny = dx2 / len2;
        result.push([p[0] + nx * offset, p[1] + ny * offset]);
      } else if (len2 === 0) {
        const nx = -dy1 / len1;
        const ny = dx1 / len1;
        result.push([p[0] + nx * offset, p[1] + ny * offset]);
      } else {
        const n1x = -dy1 / len1;
        const n1y = dx1 / len1;
        const n2x = -dy2 / len2;
        const n2y = dx2 / len2;

        let nx = (n1x + n2x) / 2;
        let ny = (n1y + n2y) / 2;
        let nLen = Math.hypot(nx, ny);

        if (nLen < 1e-4) {
          result.push([p[0] + n1x * offset, p[1] + n1y * offset]);
        } else {
          nx /= nLen;
          ny /= nLen;
          const cosTheta = n1x * nx + n1y * ny;
          const factor = Math.min(2.0, 1.0 / Math.max(0.1, cosTheta));
          result.push([p[0] + nx * offset * factor, p[1] + ny * offset * factor]);
        }
      }
    }
  }

  return result;
}

/**
 * Converts a list of points into an SVG path string, drawing rounded corner curves at turns.
 * Perfect for orthogonal/Manhattan lines.
 */
export function getRoundedPath(points: [number, number][], radius: number): string {
  if (points.length === 0) return '';
  if (points.length === 1) return `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;
  if (points.length === 2) {
    return `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)} L ${points[1][0].toFixed(1)} ${points[1][1].toFixed(1)}`;
  }

  let path = `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;

  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const next = points[i + 1];

    const dx1 = curr[0] - prev[0];
    const dy1 = curr[1] - prev[1];
    const d1 = Math.hypot(dx1, dy1);

    const dx2 = next[0] - curr[0];
    const dy2 = next[1] - curr[1];
    const d2 = Math.hypot(dx2, dy2);

    if (d1 === 0 || d2 === 0) {
      path += ` L ${curr[0].toFixed(1)} ${curr[1].toFixed(1)}`;
      continue;
    }

    const r = Math.min(radius, d1 / 2, d2 / 2);

    if (r <= 0) {
      path += ` L ${curr[0].toFixed(1)} ${curr[1].toFixed(1)}`;
      continue;
    }

    const p1x = curr[0] - (dx1 / d1) * r;
    const p1y = curr[1] - (dy1 / d1) * r;
    const p2x = curr[0] + (dx2 / d2) * r;
    const p2y = curr[1] + (dy2 / d2) * r;

    path += ` L ${p1x.toFixed(1)} ${p1y.toFixed(1)} Q ${curr[0].toFixed(1)} ${curr[1].toFixed(1)} ${p2x.toFixed(1)} ${p2y.toFixed(1)}`;
  }

  const last = points[points.length - 1];
  path += ` L ${last[0].toFixed(1)} ${last[1].toFixed(1)}`;

  return path;
}

/**
 * Computes an orthogonal Manhattan path between two points.
 */
export function getManhattanPath(
  startX: number,
  startY: number,
  startDir: string,
  endX: number,
  endY: number,
  endDir: string,
  midpointOffset: number = 0
): [number, number][] {
  const points: [number, number][] = [];
  points.push([startX, startY]);

  const offset = 24;

  const getDirVec = (dir: string) => {
    switch (dir.toLowerCase()) {
      case 'left': return [-1, 0];
      case 'right': return [1, 0];
      case 'top': return [0, -1];
      case 'bottom': return [0, 1];
      default: return [0, 1];
    }
  };

  const vStart = getDirVec(startDir);
  const vEnd = getDirVec(endDir);

  const p1x = startX + vStart[0] * offset;
  const p1y = startY + vStart[1] * offset;

  const p2x = endX + vEnd[0] * offset;
  const p2y = endY + vEnd[1] * offset;

  points.push([p1x, p1y]);

  const isStartHorizontal = startDir.toLowerCase() === 'left' || startDir.toLowerCase() === 'right';
  const isEndHorizontal = endDir.toLowerCase() === 'left' || endDir.toLowerCase() === 'right';

  if (isStartHorizontal && isEndHorizontal) {
    const midX = (p1x + p2x) / 2 + midpointOffset;
    points.push([midX, p1y]);
    points.push([midX, p2y]);
  } else if (!isStartHorizontal && !isEndHorizontal) {
    const midY = (p1y + p2y) / 2 + midpointOffset;
    points.push([p1x, midY]);
    points.push([p2x, midY]);
  } else {
    if (isStartHorizontal) {
      points.push([p2x, p1y]);
    } else {
      points.push([p1x, p2y]);
    }
  }

  points.push([p2x, p2y]);
  points.push([endX, endY]);

  const deduped: [number, number][] = [];
  for (const pt of points) {
    if (deduped.length === 0) {
      deduped.push(pt);
    } else {
      const last = deduped[deduped.length - 1];
      if (Math.hypot(pt[0] - last[0], pt[1] - last[1]) > 0.1) {
        deduped.push(pt);
      }
    }
  }

  return deduped;
}
