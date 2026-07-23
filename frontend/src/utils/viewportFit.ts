export interface NodeBox {
  id?: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  position?: { x: number; y: number };
  measured?: { width?: number; height?: number };
}

export interface DiagramBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  width: number;
  height: number;
  centerX: number;
  centerY: number;
}

export interface ViewportTransform {
  x: number;
  y: number;
  zoom: number;
}

export function computeDiagramBounds(nodes: NodeBox[]): DiagramBounds {
  if (!nodes || nodes.length === 0) {
    return { minX: 0, minY: 0, maxX: 1920, maxY: 1080, width: 1920, height: 1080, centerX: 960, centerY: 540 };
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  nodes.forEach((n) => {
    const x = n.x ?? n.position?.x ?? 0;
    const y = n.y ?? n.position?.y ?? 0;
    const w = n.width ?? n.measured?.width ?? 200;
    const h = n.height ?? n.measured?.height ?? 80;

    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + w);
    maxY = Math.max(maxY, y + h);
  });

  if (minX === Infinity) {
    minX = 0;
    minY = 0;
    maxX = 1920;
    maxY = 1080;
  }

  const width = maxX - minX;
  const height = maxY - minY;
  const centerX = (minX + maxX) / 2.0;
  const centerY = (minY + maxY) / 2.0;

  return { minX, minY, maxX, maxY, width, height, centerX, centerY };
}

export function computeFitViewTransform(
  bounds: DiagramBounds,
  viewportWidth: number,
  viewportHeight: number,
  padding: number = 40.0,
  minZoom: number = 0.2,
  maxZoom: number = 2.0
): ViewportTransform {
  const availW = Math.max(100, viewportWidth - padding * 2.0);
  const availH = Math.max(100, viewportHeight - padding * 2.0);

  const scaleX = availW / Math.max(1, bounds.width);
  const scaleY = availH / Math.max(1, bounds.height);
  const zoom = Math.min(maxZoom, Math.max(minZoom, Math.min(scaleX, scaleY)));

  const x = viewportWidth / 2.0 - bounds.centerX * zoom;
  const y = viewportHeight / 2.0 - bounds.centerY * zoom;

  return { x, y, zoom };
}
