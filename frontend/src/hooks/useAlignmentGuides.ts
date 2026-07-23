import { useState, useCallback } from 'react';

export interface AlignmentGuide {
  id: string;
  type: 'horizontal' | 'vertical';
  x?: number;
  y?: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
  label?: string;
}

export interface SnapResult {
  x: number;
  y: number;
  guides: AlignmentGuide[];
}

export function useAlignmentGuides(
  snapThreshold: number = 6,
  enabled: boolean = true
) {
  const [guides, setGuides] = useState<AlignmentGuide[]>([]);

  const calculateSnap = useCallback(
    (
      draggedNode: any,
      allNodes: any[],
      mouseEvent?: any
    ): SnapResult => {
      if (!enabled || mouseEvent?.altKey) {
        setGuides([]);
        return { x: draggedNode.position.x, y: draggedNode.position.y, guides: [] };
      }

      const draggedW = draggedNode.measured?.width || draggedNode.width || 200;
      const draggedH = draggedNode.measured?.height || draggedNode.height || 80;

      let newX = draggedNode.position.x;
      let newY = draggedNode.position.y;

      const activeGuides: AlignmentGuide[] = [];

      const targetXCenter = newX + draggedW / 2;
      const targetXRight = newX + draggedW;
      const targetYMiddle = newY + draggedH / 2;
      const targetYBottom = newY + draggedH;

      let minDiffX = snapThreshold;
      let minDiffY = snapThreshold;

      const otherNodes = allNodes.filter((n) => n.id !== draggedNode.id && n.position);

      otherNodes.forEach((node) => {
        const nw = node.measured?.width || node.width || 200;
        const nh = node.measured?.height || node.height || 80;
        const nx = node.position.x;
        const ny = node.position.y;

        const nodeXCenter = nx + nw / 2;
        const nodeXRight = nx + nw;
        const nodeYMiddle = ny + nh / 2;
        const nodeYBottom = ny + nh;

        // --- Vertical snapping (X axis match) ---
        const xPointsDragged = [
          { type: 'left', val: newX },
          { type: 'center', val: targetXCenter },
          { type: 'right', val: targetXRight },
        ];
        const xPointsOther = [
          { type: 'left', val: nx },
          { type: 'center', val: nodeXCenter },
          { type: 'right', val: nodeXRight },
        ];

        xPointsDragged.forEach((pd) => {
          xPointsOther.forEach((po) => {
            const diff = Math.abs(pd.val - po.val);
            if (diff < minDiffX) {
              minDiffX = diff;
              if (pd.type === 'left') newX = po.val;
              else if (pd.type === 'center') newX = po.val - draggedW / 2;
              else if (pd.type === 'right') newX = po.val - draggedW;

              const guideX = po.val;
              const minY = Math.min(newY, ny) - 20;
              const maxY = Math.max(newY + draggedH, ny + nh) + 20;

              activeGuides.push({
                id: `v-${node.id}-${pd.type}`,
                type: 'vertical',
                x: guideX,
                y1: minY,
                y2: maxY,
              });
            }
          });
        });

        // --- Horizontal snapping (Y axis match) ---
        const yPointsDragged = [
          { type: 'top', val: newY },
          { type: 'middle', val: targetYMiddle },
          { type: 'bottom', val: targetYBottom },
        ];
        const yPointsOther = [
          { type: 'top', val: ny },
          { type: 'middle', val: nodeYMiddle },
          { type: 'bottom', val: nodeYBottom },
        ];

        yPointsDragged.forEach((pd) => {
          yPointsOther.forEach((po) => {
            const diff = Math.abs(pd.val - po.val);
            if (diff < minDiffY) {
              minDiffY = diff;
              if (pd.type === 'top') newY = po.val;
              else if (pd.type === 'middle') newY = po.val - draggedH / 2;
              else if (pd.type === 'bottom') newY = po.val - draggedH;

              const guideY = po.val;
              const minX = Math.min(newX, nx) - 20;
              const maxX = Math.max(newX + draggedW, nx + nw) + 20;

              activeGuides.push({
                id: `h-${node.id}-${pd.type}`,
                type: 'horizontal',
                y: guideY,
                x1: minX,
                x2: maxX,
              });
            }
          });
        });
      });

      // --- Equal Spacing Detection ---
      const sortedX = [...otherNodes].sort((a, b) => a.position.x - b.position.x);
      for (let i = 0; i < sortedX.length - 1; i++) {
        const leftNode = sortedX[i];
        const rightNode = sortedX[i + 1];
        const leftW = leftNode.measured?.width || leftNode.width || 200;
        const gap = rightNode.position.x - (leftNode.position.x + leftW);

        if (gap > 0) {
          const candidateX1 = leftNode.position.x - gap - draggedW;
          if (Math.abs(newX - candidateX1) < snapThreshold) {
            newX = candidateX1;
            activeGuides.push({
              id: `gap-x-left-${leftNode.id}`,
              type: 'horizontal',
              y: newY + draggedH / 2,
              x1: candidateX1,
              x2: rightNode.position.x,
              label: `${Math.round(gap)}px`,
            });
          }

          const candidateX2 = rightNode.position.x + (rightNode.measured?.width || 200) + gap;
          if (Math.abs(newX - candidateX2) < snapThreshold) {
            newX = candidateX2;
            activeGuides.push({
              id: `gap-x-right-${rightNode.id}`,
              type: 'horizontal',
              y: newY + draggedH / 2,
              x1: leftNode.position.x,
              x2: candidateX2 + draggedW,
              label: `${Math.round(gap)}px`,
            });
          }
        }
      }

      setGuides(activeGuides);
      return { x: newX, y: newY, guides: activeGuides };
    },
    [snapThreshold, enabled]
  );

  const clearGuides = useCallback(() => {
    setGuides([]);
  }, []);

  return { calculateSnap, guides, clearGuides };
}
