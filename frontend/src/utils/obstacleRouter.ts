export interface Point {
  x: number;
  y: number;
}

export interface BoundingBox {
  id?: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export function routeAroundObstacles(
  start: Point,
  end: Point,
  obstacles: BoundingBox[],
  margin: number = 12
): Point[] {
  if (!obstacles || obstacles.length === 0) {
    return [start, end];
  }

  // Expanded obstacle bounding boxes with clearance margin
  const expanded = obstacles.map((obs) => ({
    minX: obs.x - margin,
    maxX: obs.x + obs.width + margin,
    minY: obs.y - margin,
    maxY: obs.y + obs.height + margin,
  }));

  const isSegmentColliding = (p1: Point, p2: Point): boolean => {
    const segMinX = Math.min(p1.x, p2.x);
    const segMaxX = Math.max(p1.x, p2.x);
    const segMinY = Math.min(p1.y, p2.y);
    const segMaxY = Math.max(p1.y, p2.y);

    return expanded.some((b) => {
      // Check if orthogonal segment intersects interior of obstacle box
      const overlapsX = segMaxX > b.minX && segMinX < b.maxX;
      const overlapsY = segMaxY > b.minY && segMinY < b.maxY;
      return overlapsX && overlapsY;
    });
  };

  // Direct line check
  if (!isSegmentColliding(start, end)) {
    return [start, end];
  }

  // Build grid coordinates along X and Y axes
  const xCoords = new Set<number>([start.x, end.x]);
  const yCoords = new Set<number>([start.y, end.y]);

  expanded.forEach((b) => {
    xCoords.add(b.minX);
    xCoords.add(b.maxX);
    yCoords.add(b.minY);
    yCoords.add(b.maxY);
  });

  const sortedX = Array.from(xCoords).sort((a, b) => a - b);
  const sortedY = Array.from(yCoords).sort((a, b) => a - b);

  // A* Search on Orthogonal Grid
  interface GridNode {
    key: string;
    p: Point;
    g: number;
    h: number;
    f: number;
    parent?: GridNode;
  }

  const pointKey = (p: Point) => `${Math.round(p.x)},${Math.round(p.y)}`;
  const heuristic = (p: Point) => Math.abs(p.x - end.x) + Math.abs(p.y - end.y);

  const openSet: GridNode[] = [];
  const closedSet = new Set<string>();

  const startNode: GridNode = {
    key: pointKey(start),
    p: start,
    g: 0,
    h: heuristic(start),
    f: heuristic(start),
  };

  openSet.push(startNode);

  while (openSet.length > 0) {
    openSet.sort((a, b) => a.f - b.f);
    const current = openSet.shift()!;

    if (Math.abs(current.p.x - end.x) < 2 && Math.abs(current.p.y - end.y) < 2) {
      // Reconstruct path
      const path: Point[] = [];
      let curr: GridNode | undefined = current;
      while (curr) {
        path.unshift(curr.p);
        curr = curr.parent;
      }
      return simplifyPath(path);
    }

    closedSet.add(current.key);

    // Neighbors along grid axes
    const neighbors: Point[] = [];
    sortedX.forEach((x) => {
      if (Math.abs(x - current.p.x) > 0.1) {
        neighbors.push({ x, y: current.p.y });
      }
    });
    sortedY.forEach((y) => {
      if (Math.abs(y - current.p.y) > 0.1) {
        neighbors.push({ x: current.p.x, y });
      }
    });

    for (const np of neighbors) {
      const nKey = pointKey(np);
      if (closedSet.has(nKey)) continue;

      if (isSegmentColliding(current.p, np)) continue;

      const dist = Math.abs(np.x - current.p.x) + Math.abs(np.y - current.p.y);
      const tentativeG = current.g + dist;

      let existing = openSet.find((node) => node.key === nKey);
      if (!existing) {
        const newNode: GridNode = {
          key: nKey,
          p: np,
          g: tentativeG,
          h: heuristic(np),
          f: tentativeG + heuristic(np),
          parent: current,
        };
        openSet.push(newNode);
      } else if (tentativeG < existing.g) {
        existing.g = tentativeG;
        existing.f = tentativeG + existing.h;
        existing.parent = current;
      }
    }
  }

  // Fallback to simple midpoint orthogonal route if no grid path found
  const midX = (start.x + end.x) / 2;
  return [
    start,
    { x: midX, y: start.y },
    { x: midX, y: end.y },
    end,
  ];
}

function simplifyPath(path: Point[]): Point[] {
  if (path.length <= 2) return path;

  const result: Point[] = [path[0]];

  for (let i = 1; i < path.length - 1; i++) {
    const prev = result[result.length - 1];
    const curr = path[i];
    const next = path[i + 1];

    // Collinear check (horizontal or vertical line continuation)
    const isCollinearX = Math.abs(prev.x - curr.x) < 0.1 && Math.abs(curr.x - next.x) < 0.1;
    const isCollinearY = Math.abs(prev.y - curr.y) < 0.1 && Math.abs(curr.y - next.y) < 0.1;

    if (!isCollinearX && !isCollinearY) {
      result.push(curr);
    }
  }

  result.push(path[path.length - 1]);
  return result;
}
