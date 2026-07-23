export interface GridChild {
  id: string;
  width: number;
  height: number;
  x?: number;
  y?: number;
}

export function computeGridCols(
  panelWidth: number,
  padLeft: number = 20,
  padRight: number = 20,
  gap: number = 20,
  avgCardWidth: number = 200
): number {
  const innerWidth = panelWidth - padLeft - padRight;
  if (innerWidth <= 0) return 1;
  const cols = Math.floor((innerWidth + gap) / (avgCardWidth + gap));
  return Math.max(1, cols);
}

export function layoutGridChildren(
  children: GridChild[],
  maxCols: number,
  gap: number = 20,
  padLeft: number = 20,
  padTop: number = 40
): { children: GridChild[]; totalWidth: number; totalHeight: number } {
  if (!children || children.length === 0) {
    return { children: [], totalWidth: padLeft * 2 + 200, totalHeight: padTop + 40 };
  }

  const cols = Math.max(1, maxCols);
  let rowMaxHeight = 0;
  let currX = padLeft;
  let currY = padTop;
  let maxColWidths: number[] = [];

  const positioned: GridChild[] = [];

  children.forEach((child, index) => {
    const colIdx = index % cols;

    if (colIdx === 0 && index > 0) {
      currX = padLeft;
      currY += rowMaxHeight + gap;
      rowMaxHeight = 0;
    }

    const w = child.width || 200;
    const h = child.height || 80;

    positioned.push({
      ...child,
      x: currX,
      y: currY,
    });

    maxColWidths[colIdx] = Math.max(maxColWidths[colIdx] || 0, w);
    rowMaxHeight = Math.max(rowMaxHeight, h);
    currX += w + gap;
  });

  const totalWidth = padLeft + maxColWidths.reduce((sum, w) => sum + w, 0) + (maxColWidths.length - 1) * gap + padLeft;
  const totalHeight = currY + rowMaxHeight + gap;

  return { children: positioned, totalWidth, totalHeight };
}
