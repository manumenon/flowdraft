import React from 'react';
import { Handle, Position, NodeResizer } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

export const PanelNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#22c86f';
  const strokeWidth = style.strokeWidth ?? 2;
  const cornerRadius = style.cornerRadius ?? 16;
  const accentColor = style.color || '#22c86f';
  const isBorderless = !!style.borderless;
  const isTransparent = !!style.transparent;

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.6,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: accentColor,
    width: 8,
    height: 8,
    border: '1px solid white',
  };

  return (
    <div
      className="relative h-full w-full select-none"
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--panel-bg, rgba(30, 30, 46, 0.15))',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${strokeColor}`,
        borderRadius: `${cornerRadius}px`,
        color: 'var(--node-fg, #cdd6f4)',
        boxShadow: isPureRender ? 'none' : 'inset 0 0 15px rgba(255, 255, 255, 0.02)',
      }}
    >
      {!isPureRender && (
        <NodeResizer
          minWidth={200}
          minHeight={150}
          isVisible={selected}
          lineStyle={{ borderColor: strokeColor, borderWidth: 1 }}
          handleStyle={{ backgroundColor: strokeColor, width: 8, height: 8, borderRadius: 2 }}
        />
      )}
      {/* Handles */}
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="right" style={handleStyle} />

      {/* Header Title & Subtitle / Badge */}
      <div className="absolute top-3 left-4 right-4 flex items-start justify-between pointer-events-none select-none">
        <div className="flex flex-col gap-0.5">
          <span className="text-[11px] font-bold tracking-widest uppercase" style={{ color: strokeColor }}>
            {data.title || ''}
          </span>
          {data.subtitle && (
            <span className="text-[9px] leading-tight font-medium opacity-65 italic text-slate-300">
              {data.subtitle}
            </span>
          )}
        </div>

        {data.badge && (
          <span
            className="text-[8px] px-2 py-0.5 font-bold uppercase tracking-widest rounded-full flex-shrink-0"
            style={{
              backgroundColor: `${strokeColor}15`,
              color: strokeColor,
              border: `1px solid ${strokeColor}30`,
            }}
          >
            {data.badge}
          </span>
        )}
      </div>
    </div>
  );
};

export default PanelNode;
