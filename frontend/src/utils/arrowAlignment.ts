export interface Point {
  x: number;
  y: number;
}

export function straightenConnectionPath(
  points: Point[],
  snapThreshold: number = 12.0
): Point[] {
  if (!points || points.length < 2) return points || [];

  const straightened: Point[] = points.map((p) => ({ ...p }));

  const start = straightened[0];
  const end = straightened[straightened.length - 1];

  // Snap horizontal axis
  if (Math.abs(start.y - end.y) < snapThreshold) {
    const avgY = (start.y + end.y) / 2.0;
    for (let i = 0; i < straightened.length; i++) {
      straightened[i].y = avgY;
    }
  }

  // Snap vertical axis
  if (Math.abs(start.x - end.x) < snapThreshold) {
    const avgX = (start.x + end.x) / 2.0;
    for (let i = 0; i < straightened.length; i++) {
      straightened[i].x = avgX;
    }
  }

  // Simplify collinear intermediate points
  const res: Point[] = [straightened[0]];
  for (let i = 1; i < straightened.length - 1; i++) {
    const prev = res[res.length - 1];
    const curr = straightened[i];
    const next = straightened[i + 1];

    const collinearX = Math.abs(prev.x - curr.x) < 0.1 && Math.abs(curr.x - next.x) < 0.1;
    const collinearY = Math.abs(prev.y - curr.y) < 0.1 && Math.abs(curr.y - next.y) < 0.1;

    if (!collinearX && !collinearY) {
      res.push(curr);
    }
  }
  res.push(straightened[straightened.length - 1]);

  return res;
}
