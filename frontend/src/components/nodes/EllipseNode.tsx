import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const EllipseNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#ec4899';
  const strokeWidth = style.strokeWidth ?? 2;
  const accentColor = style.color || '#ec4899';
  const isBorderless = !!style.borderless;
  const isTransparent = !!style.transparent;
  const isBold = !!style.bold;

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? ('none' as const) : ('auto' as const),
    background: accentColor,
    width: 6,
    height: 6,
    border: '1.5px solid var(--surface-1)',
  };

  return (
    <div
      className={`relative px-5 py-3.5 flex flex-col items-center justify-center h-full w-full rounded-full select-none transition-shadow duration-200 animate-zoom-in ${
        selected ? 'shadow-premium ring-1 ring-pink-500/40' : 'hover:shadow-xl cursor-pointer'
      }`}
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--node-bg)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${selected ? strokeColor : 'var(--border-default)'}`,
        color: 'var(--node-fg)',
        boxShadow: selected
          ? `0 0 16px 2px ${strokeColor}`
          : isPureRender
            ? 'none'
            : '0 8px 30px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.02)',
      }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="target-left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="source-left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="target-right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="source-right" style={handleStyle} />

      {/* Content */}
      <div className="flex flex-col items-center justify-center text-center max-w-[85%]">
        <div className="flex items-center justify-center gap-1.5 mb-0.5">
          {data.icon && (
            <div className="p-1 rounded-md bg-surface-3 border border-border-themed">
              <Icon name={data.icon as string} color={accentColor} size={14} />
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
          <div className="text-[10px] leading-tight whitespace-pre-wrap overflow-hidden font-mono text-text-secondary font-medium">
            {data.body}
          </div>
        )}

        {/* Annotations */}
        {data.annotations && data.annotations.length > 0 && (
          <div className="mt-1 flex flex-wrap justify-center gap-1 pointer-events-none z-10">
            {data.annotations.map((ann: any, idx: number) => (
              <div
                key={idx}
                className="text-[8px] px-1.5 py-0.5 rounded-md bg-surface-1/90 border shadow-sm font-semibold flex items-center gap-1 backdrop-blur-md"
                style={{
                  borderColor: `${strokeColor}40`,
                  color: 'var(--text-primary)',
                }}
              >
                <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: strokeColor }} />
                <span className="leading-tight">{ann.text}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default EllipseNode;
