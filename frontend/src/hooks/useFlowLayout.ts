import { useState, useEffect, useRef, useCallback } from 'react';
import type { ElementSpec, ConnectionSpec } from '../types/spec';
import LayoutWorkerImport from '../workers/layout.worker?worker';

const LayoutWorker = (LayoutWorkerImport as any).default || LayoutWorkerImport;

export interface PositionedNodeInfo {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  parent: string | null;
}

export interface PositionedEdgeInfo {
  id: string;
  points: [number, number][];
}

export function useFlowLayout() {
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const [isWorkerReady, setIsWorkerReady] = useState(false);
  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    try {
      workerRef.current = new (LayoutWorker as any)();
    } catch (err) {
      workerRef.current = (LayoutWorker as any)();
    }

    const handleReady = (event: MessageEvent) => {
      if (event.data && event.data.type === 'ready') {
        setIsWorkerReady(true);
        workerRef.current?.removeEventListener('message', handleReady);
      }
    };

    if (workerRef.current) {
      workerRef.current.addEventListener('message', handleReady);
    }

    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, []);

  const runLayout = useCallback((
    elements: ElementSpec[],
    connections: ConnectionSpec[],
    title: any,
    layoutDirection?: 'vertical' | 'horizontal',
    layoutAlgorithm?: string
  ): Promise<{ positionedNodes: PositionedNodeInfo[]; positionedEdges: PositionedEdgeInfo[]; canvasWidth: number; canvasHeight: number }> => {
    return new Promise((resolve, reject) => {
      if (!workerRef.current) {
        reject(new Error('Layout worker not initialized'));
        return;
      }

      setIsLayoutRunning(true);

      const handleMessage = (event: MessageEvent) => {
        if (event.data && typeof event.data.success === 'boolean') {
          const { success, graph, error } = event.data;
          workerRef.current?.removeEventListener('message', handleMessage);
          setIsLayoutRunning(false);

          if (success && graph) {
             const positionedNodes: PositionedNodeInfo[] = [];
             const positionedEdges: PositionedEdgeInfo[] = [];

             const collectNodes = (elkNode: any, parentId: string | null = null) => {
               if (elkNode.id !== 'root') {
                 positionedNodes.push({
                   id: elkNode.id,
                   x: elkNode.x,
                   y: elkNode.y,
                   width: elkNode.width,
                   height: elkNode.height,
                   parent: parentId,
                 });
               }
               if (elkNode.children) {
                 elkNode.children.forEach((child: any) => {
                   collectNodes(child, elkNode.id === 'root' ? null : elkNode.id);
                 });
               }
             };

             const collectEdges = (elkNode: any, absX: number, absY: number) => {
               const nodeAbsX = absX + (elkNode.x || 0);
               const nodeAbsY = absY + (elkNode.y || 0);

               if (elkNode.edges) {
                 elkNode.edges.forEach((edge: any) => {
                   const points: [number, number][] = [];
                   if (edge.sections) {
                     edge.sections.forEach((sec: any) => {
                       points.push([sec.startPoint.x + nodeAbsX, sec.startPoint.y + nodeAbsY]);
                       if (sec.bendPoints) {
                         sec.bendPoints.forEach((bp: any) => {
                           points.push([bp.x + nodeAbsX, bp.y + nodeAbsY]);
                         });
                       }
                       points.push([sec.endPoint.x + nodeAbsX, sec.endPoint.y + nodeAbsY]);
                     });
                   }
                   positionedEdges.push({
                     id: edge.id,
                     points,
                   });
                 });
               }

               if (elkNode.children) {
                 elkNode.children.forEach((child: any) => {
                   const parentX = elkNode.id === 'root' ? 0 : nodeAbsX;
                   const parentY = elkNode.id === 'root' ? 0 : nodeAbsY;
                   collectEdges(child, parentX, parentY);
                 });
               }
             };

             collectNodes(graph, null);
             collectEdges(graph, 0, 0);

             resolve({
               positionedNodes,
               positionedEdges,
               canvasWidth: graph.width || 1920,
               canvasHeight: graph.height || 1440,
             });
          } else {
            reject(new Error(error || 'Layout computation failed'));
          }
        }
      };

      workerRef.current.addEventListener('message', handleMessage);
      workerRef.current.postMessage({ elements, connections, title, layoutDirection, layoutAlgorithm });
    });
  }, []);

  return { runLayout, isLayoutRunning, isWorkerReady };
}
