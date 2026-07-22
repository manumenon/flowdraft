import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const CardNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#3b82f6';
  const strokeWidth = style.strokeWidth ?? 2;
  const cornerRadius = style.cornerRadius ?? 12;
  const accentColor = style.color || '#3b82f6';
  const isBorderless = !!style.borderless;
  const isTransparent = !!style.transparent;
  const isBold = !!style.bold;

  // Handles configuration
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
      className={`relative px-4 py-3.5 flex flex-col justify-between h-full w-full select-none transition-shadow duration-200 animate-zoom-in ${
        selected 
          ? 'shadow-premium ring-1 ring-indigo-500/40' 
          : 'hover:shadow-xl cursor-pointer'
      }`}
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--node-bg)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${selected ? strokeColor : 'var(--border-default)'}`,
        borderRadius: `${cornerRadius}px`,
        color: 'var(--node-fg)',
        boxShadow: selected
          ? `0 0 16px 2px ${strokeColor}`
          : isPureRender
            ? 'none'
            : '0 8px 30px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.02)',
      }}
    >
      {/* 3.5px top border colored accent strip */}
      {!isTransparent && (
        <div
          className="absolute top-0 left-0 right-0 h-[3.5px] rounded-t-lg"
          style={{ backgroundColor: accentColor }}
        />
      )}

      {/* Handles for connections on all 4 ports */}
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="target-left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="source-left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="target-right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="source-right" style={handleStyle} />

      {/* Node Content */}
      <div className="flex items-center gap-2 mb-1.5 mt-1">
        {data.icon && (
          <div className="p-1 rounded-md bg-surface-3 border border-border-themed">
            <Icon name={data.icon as string} color={accentColor} size={15} />
          </div>
        )}
        <span
          className="text-xs font-bold tracking-wide whitespace-normal break-words"
          style={{
            color: accentColor,
            fontWeight: isBold ? 'bold' : '700',
          }}
        >
          {data.title || ''}
        </span>
      </div>

      {data.body && (
        <div className="text-[11px] leading-relaxed whitespace-pre-wrap overflow-hidden flex-grow mt-1 font-mono text-text-secondary font-medium">
          {data.body}
        </div>
      )}

      {/* Render Annotations if defined in spec */}
      {data.annotations && data.annotations.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5 pointer-events-none z-10">
          {data.annotations.map((ann: any, idx: number) => (
            <div
              key={idx}
              className="text-[10px] px-2 py-0.5 rounded-md bg-surface-1/90 border shadow-sm font-semibold flex items-center gap-1.5 backdrop-blur-md"
              style={{
                borderColor: `${strokeColor}40`,
                color: 'var(--text-primary)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: strokeColor }} />
              <span className="leading-tight">{ann.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CardNode;
