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
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: accentColor,
    width: 6,
    height: 6,
    border: '1.5px solid var(--surface-1)',
  };

  return (
    <div
      className={`relative h-full w-full select-none transition-all duration-300 animate-zoom-in ${
        selected ? 'scale-[1.002] shadow-premium' : ''
      } ${isTransparent ? '' : 'animated-panel-gradient'}`}
      style={{
        backdropFilter: isTransparent ? 'none' : 'blur(12px)',
        WebkitBackdropFilter: isTransparent ? 'none' : 'blur(12px)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${selected ? strokeColor : 'var(--border-default)'}`,
        borderRadius: `${cornerRadius}px`,
        color: 'var(--node-fg)',
        boxShadow: selected
          ? `0 0 16px 2px ${strokeColor}`
          : isPureRender
            ? 'none'
            : 'inset 0 0 40px rgba(255, 255, 255, 0.015), 0 4px 20px rgba(0, 0, 0, 0.02)',
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
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="target-left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="source-left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="target-right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="source-right" style={handleStyle} />

      {/* Premium Header Title & Subtitle Badge */}
      <div className="absolute top-4 left-4 right-4 flex items-start justify-between pointer-events-none select-none">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: strokeColor }}>
            {data.title || ''}
          </span>
          {data.subtitle && (
            <span className="text-[10px] leading-tight font-medium opacity-60 italic text-text-secondary">
              {data.subtitle}
            </span>
          )}
        </div>

        {data.badge && (
          <span
            className="text-[10px] px-2 py-0.5 font-bold uppercase tracking-widest rounded-full flex-shrink-0"
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
