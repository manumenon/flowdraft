import { useCallback } from 'react';

export function useMultiSelectionAlignment() {
  const alignNodes = useCallback(
    (
      action:
        | 'left'
        | 'center'
        | 'right'
        | 'top'
        | 'middle'
        | 'bottom'
        | 'distribute-h'
        | 'distribute-v',
      selectedNodes: any[],
      setNodes: React.Dispatch<React.SetStateAction<any[]>>,
      onNodeDragStop?: (id: string, x: number, y: number, allNodes?: any[], skipHistory?: boolean) => void
    ) => {
      if (!selectedNodes || selectedNodes.length < 2) return;

      const nodesWithBounds = selectedNodes.map((node) => {
        const w = node.measured?.width || node.width || (node.style?.width as number) || 200;
        const h = node.measured?.height || node.height || (node.style?.height as number) || 80;
        return {
          id: node.id,
          x: node.position.x,
          y: node.position.y,
          w,
          h,
        };
      });

      const minX = Math.min(...nodesWithBounds.map((n) => n.x));
      const maxX = Math.max(...nodesWithBounds.map((n) => n.x + n.w));
      const minY = Math.min(...nodesWithBounds.map((n) => n.y));
      const maxY = Math.max(...nodesWithBounds.map((n) => n.y + n.h));

      const newPositions = new Map<string, { x: number; y: number }>();

      switch (action) {
        case 'left':
          nodesWithBounds.forEach((n) => newPositions.set(n.id, { x: minX, y: n.y }));
          break;
        case 'center':
          nodesWithBounds.forEach((n) => {
            const centerX = minX + (maxX - minX - n.w) / 2;
            newPositions.set(n.id, { x: centerX, y: n.y });
          });
          break;
        case 'right':
          nodesWithBounds.forEach((n) => newPositions.set(n.id, { x: maxX - n.w, y: n.y }));
          break;
        case 'top':
          nodesWithBounds.forEach((n) => newPositions.set(n.id, { x: n.x, y: minY }));
          break;
        case 'middle':
          nodesWithBounds.forEach((n) => {
            const middleY = minY + (maxY - minY - n.h) / 2;
            newPositions.set(n.id, { x: n.x, y: middleY });
          });
          break;
        case 'bottom':
          nodesWithBounds.forEach((n) => newPositions.set(n.id, { x: n.x, y: maxY - n.h }));
          break;
        case 'distribute-h': {
          const sorted = [...nodesWithBounds].sort((a, b) => a.x - b.x);
          const totalNodesW = sorted.reduce((sum, n) => sum + n.w, 0);
          const totalSpan = maxX - minX;
          const totalGap = totalSpan - totalNodesW;
          const gap = sorted.length > 1 ? totalGap / (sorted.length - 1) : 0;

          let currX = minX;
          sorted.forEach((n) => {
            newPositions.set(n.id, { x: currX, y: n.y });
            currX += n.w + gap;
          });
          break;
        }
        case 'distribute-v': {
          const sorted = [...nodesWithBounds].sort((a, b) => a.y - b.y);
          const totalNodesH = sorted.reduce((sum, n) => sum + n.h, 0);
          const totalSpan = maxY - minY;
          const totalGap = totalSpan - totalNodesH;
          const gap = sorted.length > 1 ? totalGap / (sorted.length - 1) : 0;

          let currY = minY;
          sorted.forEach((n) => {
            newPositions.set(n.id, { x: n.x, y: currY });
            currY += n.h + gap;
          });
          break;
        }
      }

      setNodes((currentNodes) => {
        const updated = currentNodes.map((node) => {
          const pos = newPositions.get(node.id);
          if (pos) {
            return {
              ...node,
              position: { x: pos.x, y: pos.y },
            };
          }
          return node;
        });

        // Notify drag stop for all moved nodes to sync state cleanly
        newPositions.forEach((pos, id) => {
          onNodeDragStop?.(id, pos.x, pos.y, updated, true);
        });

        return updated;
      });
    },
    []
  );

  return { alignNodes };
}
