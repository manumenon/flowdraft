import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  Background,
  Controls,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type { FlowSpec } from '../types/spec';
import { compileSpec, THEMES } from '../utils/specCompiler';
import { useFlowLayout } from '../hooks/useFlowLayout';

import RoutedEdge from './edges/RoutedEdge';
import CardNode from './nodes/CardNode';
import InputNode from './nodes/InputNode';
import DecisionNode from './nodes/DecisionNode';
import PanelNode from './nodes/PanelNode';
import LabelNode from './nodes/LabelNode';
import { Play, RotateCcw } from 'lucide-react';

const nodeTypes = {
  card: CardNode,
  input: InputNode,
  diamond: DecisionNode,
  panel: PanelNode,
  group: PanelNode,
  label: LabelNode,
};

const edgeTypes = {
  routed: RoutedEdge,
};

interface CanvasProps {
  spec: FlowSpec;
  theme: string;
  isPureRender?: boolean;
}

export const Canvas: React.FC<CanvasProps> = ({ spec, theme, isPureRender = false }) => {
  const { runLayout, isLayoutRunning, isWorkerReady } = useFlowLayout();

  const compiled = useMemo(() => {
    return compileSpec(spec, theme);
  }, [spec, theme]);

  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  const [, setCanvasSize] = useState({ width: 1920, height: 1440 });

  // Update nodes and edges when compiled changes
  useEffect(() => {
    const rfNodesWithFlags = compiled.rfNodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        isPureRender,
      },
    }));
    setNodes(rfNodesWithFlags);
    setEdges(compiled.rfEdges);
    setCanvasSize({
      width: compiled.canvas.width || 1920,
      height: compiled.canvas.height || 1440,
    });
  }, [compiled, isPureRender, setNodes, setEdges]);

  // Execute Layout
  const executeLayout = useCallback(async () => {
    if (!compiled.flatElements || compiled.flatElements.length === 0) {
      return;
    }
    try {
      const { positionedNodes, canvasWidth, canvasHeight } = await runLayout(
        compiled.flatElements,
        spec.connections || [],
        spec.title
      );

      setNodes((currentNodes) =>
        currentNodes.map((node) => {
          const match = positionedNodes.find((pn) => pn.id === node.id);
          if (match) {
            return {
              ...node,
              position: { x: match.x, y: match.y },
              width: match.width,
              height: match.height,
              style: {
                ...node.style,
                width: match.width,
                height: match.height,
              },
            };
          }
          return node;
        })
      );

      setCanvasSize({ width: canvasWidth, height: canvasHeight });
      (window as any).__LAYOUT_COMPLETE__ = true;
    } catch (err) {
      console.error('Failed to calculate layout:', err);
      setNodes((currentNodes) => {
        const childrenMap = new Map<string, any[]>();
        currentNodes.forEach((node) => {
          if (node.parentId) {
            const list = childrenMap.get(node.parentId) || [];
            list.push(node);
            childrenMap.set(node.parentId, list);
          }
        });

        const fallbackPositions = new Map<string, { x: number; y: number; w?: number; h?: number }>();

        currentNodes.forEach((node) => {
          if (node.type === 'panel' || node.type === 'group') {
            const panelChildren = childrenMap.get(node.id) || [];
            if (panelChildren.length > 0) {
              const cols = Math.ceil(Math.sqrt(panelChildren.length));
              const childGap = 20;
              const topPad = 60;
              const sidePad = 20;
              
              let maxChildW = 0;
              let maxChildH = 0;
              panelChildren.forEach((child) => {
                const w = child.style?.width || child.width || 200;
                const h = child.style?.height || child.height || 80;
                if (Number(w) > maxChildW) maxChildW = Number(w);
                if (Number(h) > maxChildH) maxChildH = Number(h);
              });

              panelChildren.forEach((child, index) => {
                const colIdx = index % cols;
                const rowIdx = Math.floor(index / cols);
                const rx = sidePad + colIdx * (maxChildW + childGap);
                const ry = topPad + rowIdx * (maxChildH + childGap);
                fallbackPositions.set(child.id, { x: rx, y: ry });
              });

              const totalRows = Math.ceil(panelChildren.length / cols);
              const panelW = sidePad * 2 + cols * maxChildW + (cols - 1) * childGap;
              const panelH = topPad + sidePad + totalRows * maxChildH + (totalRows - 1) * childGap;
              fallbackPositions.set(node.id, { x: 0, y: 0, w: panelW, h: panelH });
            } else {
              fallbackPositions.set(node.id, { x: 0, y: 0, w: 300, h: 200 });
            }
          }
        });

        const topLevelNodes = currentNodes.filter((node) => !node.parentId);
        const gridCols = Math.ceil(Math.sqrt(topLevelNodes.length)) || 1;
        const mainGapX = 80;
        const mainGapY = 80;

        const colWidths: number[] = [];
        const rowHeights: number[] = [];

        topLevelNodes.forEach((node, index) => {
          const colIdx = index % gridCols;
          const rowIdx = Math.floor(index / gridCols);
          
          const posInfo = fallbackPositions.get(node.id);
          const w = posInfo?.w || node.style?.width || node.width || 200;
          const h = posInfo?.h || node.style?.height || node.height || 80;

          colWidths[colIdx] = Math.max(colWidths[colIdx] || 0, Number(w));
          rowHeights[rowIdx] = Math.max(rowHeights[rowIdx] || 0, Number(h));
        });

        const colOffsets: number[] = [50];
        for (let i = 0; i < colWidths.length; i++) {
          colOffsets[i + 1] = colOffsets[i] + colWidths[i] + mainGapX;
        }
        const rowOffsets: number[] = [200];
        for (let i = 0; i < rowHeights.length; i++) {
          rowOffsets[i + 1] = rowOffsets[i] + rowHeights[i] + mainGapY;
        }

        topLevelNodes.forEach((node, index) => {
          const colIdx = index % gridCols;
          const rowIdx = Math.floor(index / gridCols);
          const x = colOffsets[colIdx];
          const y = rowOffsets[rowIdx];
          
          const existing = fallbackPositions.get(node.id);
          fallbackPositions.set(node.id, {
            x,
            y,
            w: existing?.w,
            h: existing?.h
          });
        });

        return currentNodes.map((node) => {
          const posInfo = fallbackPositions.get(node.id);
          if (posInfo) {
            const w = posInfo.w || node.style?.width || node.width;
            const h = posInfo.h || node.style?.height || node.height;
            return {
              ...node,
              position: { x: posInfo.x, y: posInfo.y },
              width: w,
              height: h,
              style: {
                ...node.style,
                width: w,
                height: h,
              },
            };
          }
          return node;
        });
      });
      setCanvasSize({ width: 1920, height: 1440 });
      (window as any).__LAYOUT_COMPLETE__ = true;
    }
  }, [compiled.flatElements, spec.connections, spec.title, runLayout, setNodes, setCanvasSize]);

  // Run layout on mount if canvas mode is not absolute and has no fixed nodes
  useEffect(() => {
    const hasFixedNodes = compiled.flatElements.some((el) => el.x !== undefined && el.y !== undefined);
    const canvasMode = compiled.canvas.mode;

    if (canvasMode !== 'absolute' && !hasFixedNodes) {
      if (isWorkerReady) {
        executeLayout();
      }
    } else {
      (window as any).__LAYOUT_COMPLETE__ = true;
    }
  }, [compiled.flatElements, compiled.canvas.mode, executeLayout, isWorkerReady]);

  const themeColors = THEMES[theme] || THEMES.dark;

  const containerStyle = {
    backgroundColor: themeColors.bg,
    width: '100%',
    height: '100%',
    '--node-bg': theme === 'dark' ? '#181825' : '#ffffff',
    '--node-fg': theme === 'dark' ? '#cdd6f4' : '#1e1e2e',
    '--panel-bg': theme === 'dark' ? 'rgba(24, 24, 37, 0.25)' : 'rgba(220, 252, 231, 0.15)',
  } as React.CSSProperties;

  return (
    <div style={containerStyle} className="relative w-full h-full select-none overflow-hidden">
      {/* Title Block */}
      {compiled.title && (
        <div className="absolute top-8 left-1/2 transform -translate-x-1/2 text-center z-20 pointer-events-none select-none">
          <h1 className="text-xl md:text-2xl font-bold tracking-wider mb-1 flex items-center justify-center gap-2">
            {compiled.title.prefix && (
              <span className="text-slate-400 font-medium">{compiled.title.prefix}</span>
            )}
            {compiled.title.highlight && (
              <span style={{ color: themeColors.core_stroke || themeColors.green }}>
                {compiled.title.highlight}
              </span>
            )}
          </h1>
          {compiled.title.subtitle && (
            <p className="text-xs md:text-sm font-medium tracking-wide text-slate-500 font-mono">
              {compiled.title.subtitle}
            </p>
          )}
        </div>
      )}

      {/* Signature */}
      {compiled.signature && (
        <div
          className="absolute bottom-6 right-6 text-xs font-bold tracking-widest uppercase z-20 pointer-events-none select-none"
          style={{ color: themeColors.muted }}
        >
          {compiled.signature}
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={isPureRender ? undefined : onNodesChange}
        onEdgesChange={isPureRender ? undefined : onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        nodesDraggable={!isPureRender}
        nodesConnectable={false}
        elementsSelectable={!isPureRender}
        minZoom={0.1}
        maxZoom={4}
      >
        {!isPureRender && <Background color={theme === 'dark' ? '#333' : '#ddd'} gap={20} size={1} />}
        {!isPureRender && <Controls showInteractive={false} />}

        {!isPureRender && (
          <Panel position="top-right" className="bg-slate-900/90 border border-slate-700/85 p-2 rounded-lg shadow-xl flex gap-2 z-50">
            <button
              onClick={executeLayout}
              disabled={isLayoutRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-xs font-semibold rounded transition"
            >
              <Play size={14} className={isLayoutRunning ? 'animate-spin' : ''} />
              {isLayoutRunning ? 'Running...' : 'Auto Layout'}
            </button>
            <button
              onClick={() => {
                const rfNodesWithFlags = compiled.rfNodes.map((node) => ({
                  ...node,
                  data: {
                    ...node.data,
                    isPureRender,
                  },
                }));
                setNodes(rfNodesWithFlags);
                setEdges(compiled.rfEdges);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded border border-slate-600 transition"
            >
              <RotateCcw size={14} />
              Reset Nodes
            </button>
          </Panel>
        )}
      </ReactFlow>
    </div>
  );
};

export default Canvas;
