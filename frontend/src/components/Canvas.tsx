import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
   ReactFlow,
   useNodesState,
   useEdgesState,
   Background,
   Controls,
   Panel,
   MiniMap,
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
import { Play, RotateCcw, AppWindow } from 'lucide-react';
import { gsap } from 'gsap';

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
  onNodeSelect?: (id: string | null) => void;
  onEdgeSelect?: (from: string, to: string, index: number) => void;
  onNodeDragStop?: (id: string, x: number, y: number, allNodes?: any[]) => void;
  onConnect?: (from: string, to: string, exitPort: string, entryPort: string) => void;
  snapToGrid?: boolean;
  onToggleSnap?: () => void;
}

export const Canvas: React.FC<CanvasProps> = ({
  spec,
  theme,
  isPureRender = false,
  onNodeSelect,
  onEdgeSelect,
  onNodeDragStop,
  onConnect,
  snapToGrid = false,
  onToggleSnap,
}) => {
  const { runLayout, isLayoutRunning, isWorkerReady } = useFlowLayout();

  const compiled = useMemo(() => {
    return compileSpec(spec, theme);
  }, [spec, theme]);

  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  const [, setCanvasSize] = useState({ width: 1920, height: 1440 });

  // Timeline Player States
  const [isPlaying, setIsPlaying] = useState(true);
  const [progress, setProgress] = useState(0);
  const [speed, setSpeed] = useState(1);

  // Sync seek bar with GSAP global timeline ticker
  useEffect(() => {
    if (isPureRender) return;
    let active = true;
    const updateProgress = () => {
      if (!active) return;
      const p = gsap.globalTimeline.progress() || 0;
      setProgress(p * 100);
      requestAnimationFrame(updateProgress);
    };
    requestAnimationFrame(updateProgress);
    return () => {
      active = false;
    };
  }, [isPureRender]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setProgress(val);
    gsap.globalTimeline.progress(val / 100);
  };

  const togglePlay = () => {
    if (isPlaying) {
      gsap.globalTimeline.pause();
    } else {
      gsap.globalTimeline.play();
    }
    setIsPlaying(!isPlaying);
  };

  const handleRewind = () => {
    gsap.globalTimeline.time(0);
    setProgress(0);
  };

  const handleSpeedChange = (val: number) => {
    setSpeed(val);
    gsap.globalTimeline.timeScale(val);
  };

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
  } as React.CSSProperties;

  return (
    <div style={containerStyle} className="relative w-full h-full select-none overflow-hidden font-sans">
      {/* Glow Filter Definitions */}
      <svg style={{ position: 'absolute', width: 0, height: 0 }}>
        <defs>
          <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
      </svg>

      {/* Empty State Overlay */}
      {compiled.rfNodes.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-10 select-none pointer-events-none">
          <div className="max-w-md bg-surface-1/90 border border-border-themed rounded-2xl p-8 backdrop-blur-md shadow-lg pointer-events-auto animate-zoom-in">
            <AppWindow className="mx-auto text-accent w-12 h-12 mb-4 animate-pulse" />
            <h3 className="text-sm font-bold text-text-primary uppercase tracking-widest mb-2">Empty Spec Canvas</h3>
            <p className="text-xs text-text-secondary leading-relaxed mb-4">
              There are no component blocks present in this specification layout yet.
            </p>
            <div className="text-[10px] text-accent font-bold uppercase tracking-wider bg-accent-soft py-1.5 px-3 rounded-lg border border-accent/20 inline-block">
              Use the "Spawn Component" templates in the properties editor panel on the right.
            </div>
          </div>
        </div>
      )}

      {/* Frosted Glass Title Block */}
      {compiled.title && (
        <div className="absolute top-6 left-1/2 transform -translate-x-1/2 text-center z-20 pointer-events-none select-none">
          <div className="px-6 py-3 bg-surface-1/90 backdrop-blur-md border border-border-themed rounded-xl shadow-sm dark:shadow-premium">
            <h1 className="text-lg md:text-xl font-bold tracking-wider mb-0.5 flex items-center justify-center gap-2">
              {compiled.title.prefix && (
                <span className="text-text-muted font-medium">{compiled.title.prefix}</span>
              )}
              {compiled.title.highlight && (
                <span style={{ color: themeColors.core_stroke || themeColors.green }}>
                  {compiled.title.highlight}
                </span>
              )}
            </h1>
            {compiled.title.subtitle && (
              <p className="text-[10px] md:text-xs font-semibold tracking-widest text-text-muted font-mono uppercase">
                {compiled.title.subtitle}
              </p>
            )}
          </div>
        </div>
      )}
      {/* Signature Tag */}
      {compiled.signature && (
        <div
          className="absolute bottom-6 left-6 text-[10px] font-bold tracking-widest uppercase z-20 pointer-events-none select-none font-mono"
          style={{ color: themeColors.muted }}
        >
          // {compiled.signature}
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={isPureRender ? undefined : onNodesChange}
        onEdgesChange={isPureRender ? undefined : onEdgesChange}
        onNodeClick={isPureRender ? undefined : (_, node) => {
          onNodeSelect?.(node.id);
          onEdgeSelect?.('', '', -1);
        }}
        onEdgeClick={isPureRender ? undefined : (_, edge) => {
          onNodeSelect?.(null);
          const parts = edge.id.split('-');
          const idx = parseInt(parts[parts.length - 1]);
          onEdgeSelect?.(edge.source, edge.target, isNaN(idx) ? 0 : idx);
        }}
        onPaneClick={isPureRender ? undefined : () => {
          onNodeSelect?.(null);
          onEdgeSelect?.('', '', -1);
        }}
        onNodeDragStop={isPureRender ? undefined : (_, node) => {
          if (node.position) {
            onNodeDragStop?.(node.id, node.position.x, node.position.y, nodes);
          }
        }}
        onConnect={isPureRender ? undefined : (conn) => {
          if (conn.source && conn.target) {
            onConnect?.(
              conn.source,
              conn.target,
              conn.sourceHandle || 'bottom',
              conn.targetHandle || 'top'
            );
          }
        }}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        nodesDraggable={!isPureRender}
        nodesConnectable={!isPureRender}
        elementsSelectable={!isPureRender}
        minZoom={0.1}
        maxZoom={4}
      >
        {!isPureRender && <Background color={theme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'} gap={20} size={1} />}
        {!isPureRender && <Controls showInteractive={false} />}
        {!isPureRender && (
          <MiniMap
            className="!bg-surface-1/90 border border-border-themed rounded-xl"
            nodeColor={() => (theme === 'dark' ? '#171b30' : '#f1f3f5')}
            maskColor={theme === 'dark' ? 'rgba(10, 13, 26, 0.6)' : 'rgba(255, 255, 255, 0.6)'}
          />
        )}

        {!isPureRender && (
          <Panel position="top-right" className="bg-surface-1/90 border border-border-themed p-1.5 rounded-xl shadow-xl flex gap-1.5 z-50 backdrop-blur-md">
            <button
              onClick={onToggleSnap}
              className={`flex items-center gap-1 px-3 py-1.5 text-[10px] uppercase font-bold tracking-wider rounded-lg border transition focus-ring ${
                snapToGrid
                  ? 'bg-amber-600 text-white border-amber-600 hover:bg-amber-500 shadow-sm'
                  : 'bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-700'
              }`}
              title="Toggle Grid Snapping"
            >
              Snap: {snapToGrid ? 'ON' : 'OFF'}
            </button>
            <div className="w-[1px] bg-slate-200 dark:bg-slate-800 self-stretch my-0.5" />
            <button
              data-layout-btn
              onClick={executeLayout}
              disabled={isLayoutRunning}
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-[10px] uppercase font-bold tracking-wider rounded-lg transition focus-ring"
            >
              <Play size={12} className={isLayoutRunning ? 'animate-spin' : ''} />
              {isLayoutRunning ? 'Running...' : 'Auto Layout'}
            </button>
            <div className="w-[1px] bg-slate-200 dark:bg-slate-800 self-stretch my-0.5" />
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
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-[10px] uppercase font-bold tracking-wider rounded-lg border border-slate-200 dark:border-slate-700 transition focus-ring"
            >
              <RotateCcw size={12} />
              Reset Nodes
            </button>
          </Panel>
        )}

        {!isPureRender && (
          <Panel position="bottom-center" className="bg-surface-1/90 border border-border-themed p-3 rounded-xl shadow-2xl flex flex-col gap-2.5 z-50 backdrop-blur-md w-[400px] select-none mb-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-mono tracking-widest font-extrabold text-text-muted flex items-center gap-1">
                <Play className="text-accent animate-pulse" size={10} /> Live Timeline Player
              </span>
              <div className="flex items-center gap-1 bg-surface-3/50 px-1.5 py-0.5 rounded border border-border-themed font-mono text-[9px] font-bold text-text-secondary">
                <span>FPS: {spec.canvas?.fps || 30}</span>
                <span className="mx-1">•</span>
                <span>Time: {Math.round(progress * ((spec.canvas?.frames || 90) / (spec.canvas?.fps || 30)) / 100)}s</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="range"
                min="0"
                max="100"
                step="0.5"
                value={progress}
                onChange={handleSliderChange}
                className="flex-grow accent-indigo-600 bg-surface-3 h-1.5 rounded-lg focus-ring cursor-pointer"
              />
            </div>

            <div className="flex items-center justify-between mt-1">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={handleRewind}
                  className="p-1.5 hover:bg-surface-2 text-text-secondary hover:text-text-primary rounded-lg border border-border-themed transition focus-ring"
                  title="Rewind Timeline"
                >
                  <RotateCcw size={13} />
                </button>
                <button
                  onClick={togglePlay}
                  className="px-3.5 py-1.5 bg-accent hover:opacity-90 text-white text-[10px] uppercase font-mono tracking-wider font-bold rounded-lg flex items-center gap-1 transition focus-ring"
                >
                  {isPlaying ? 'Pause' : 'Play'}
                </button>
              </div>

              <div className="flex items-center bg-surface-2 p-0.5 rounded-lg border border-border-themed">
                {[0.5, 1, 2].map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSpeedChange(s)}
                    className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono transition ${
                      speed === s ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-muted hover:text-text-primary'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>
          </Panel>
        )}
      </ReactFlow>
    </div>
  );
};

export default Canvas;
