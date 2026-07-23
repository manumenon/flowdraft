export type PortSide = 'NORTH' | 'SOUTH' | 'EAST' | 'WEST';

export interface Point {
  x: number;
  y: number;
}

export function getPortNormal(side: PortSide): Point {
  switch (side) {
    case 'NORTH':
      return { x: 0, y: -1 };
    case 'SOUTH':
      return { x: 0, y: 1 };
    case 'EAST':
      return { x: 1, y: 0 };
    case 'WEST':
      return { x: -1, y: 0 };
    default:
      return { x: 0, y: 1 };
  }
}

export function addDirectionalStubs(
  start: Point,
  end: Point,
  startSide: PortSide = 'SOUTH',
  endSide: PortSide = 'NORTH',
  stubLen: number = 16.0
): Point[] {
  const startNorm = getPortNormal(startSide);
  const endNorm = getPortNormal(endSide);

  const startStub: Point = {
    x: start.x + startNorm.x * stubLen,
    y: start.y + startNorm.y * stubLen,
  };

  const endStub: Point = {
    x: end.x + endNorm.x * stubLen,
    y: end.y + endNorm.y * stubLen,
  };

  return [start, startStub, endStub, end];
}
