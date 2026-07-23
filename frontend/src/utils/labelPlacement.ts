export interface Point {
  x: number;
  y: number;
}

export interface LabelPositionResult {
  x: number;
  y: number;
  angle: number;
  offsetX: number;
  offsetY: number;
  segmentIndex: number;
}

export function computeConnectionLabelPos(
  points: Point[],
  ports: Point[] = [],
  clearanceMargin: number = 24.0,
  perpOffset: number = 12.0
): LabelPositionResult {
  if (!points || points.length < 2) {
    return { x: 0, y: 0, angle: 0, offsetX: 0, offsetY: 0, segmentIndex: 0 };
  }

  let longestIndex = 0;
  let maxLen = 0;

  for (let i = 0; i < points.length - 1; i++) {
    const p1 = points[i];
    const p2 = points[i + 1];
    const len = Math.hypot(p2.x - p1.x, p2.y - p1.y);
    if (len > maxLen) {
      maxLen = len;
      longestIndex = i;
    }
  }

  const p1 = points[longestIndex];
  const p2 = points[longestIndex + 1];
  let midX = (p1.x + p2.x) / 2.0;
  let midY = (p1.y + p2.y) / 2.0;

  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const isHorizontal = Math.abs(dx) >= Math.abs(dy);

  let nearConflict = false;
  for (const port of ports) {
    if (Math.hypot(midX - port.x, midY - port.y) < clearanceMargin) {
      nearConflict = true;
      break;
    }
  }

  let offsetX = 0;
  let offsetY = 0;
  if (nearConflict) {
    if (isHorizontal) {
      offsetY = -perpOffset;
    } else {
      offsetX = perpOffset;
    }
  }

  const angle = isHorizontal ? 0 : 90;

  return {
    x: midX + offsetX,
    y: midY + offsetY,
    angle,
    offsetX,
    offsetY,
    segmentIndex: longestIndex,
  };
}
