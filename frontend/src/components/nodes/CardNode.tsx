import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const CardNode: React.FC<NodeProps> = (props) => {
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
    opacity: isPureRender ? 0 : 0.6,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: accentColor,
    width: 8,
    height: 8,
    border: '1px solid white',
  };

  return (
    <div
      className={`relative px-4 py-3 flex flex-col justify-between h-full w-full select-none`}
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--node-bg, #1e1e2e)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${strokeColor}`,
        borderRadius: `${cornerRadius}px`,
        color: 'var(--node-fg, #cdd6f4)',
        boxShadow: isPureRender ? 'none' : '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      }}
    >
      {/* Handles for connections on all 4 ports */}
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="right" style={handleStyle} />

      {/* Node Content */}
      <div className="flex items-center gap-2 mb-1.5">
        {data.icon && <Icon name={data.icon as string} color={accentColor} size={20} />}
        <span
          className="text-sm font-semibold tracking-wide truncate"
          style={{
            color: accentColor,
            fontWeight: isBold ? 'bold' : '600',
          }}
        >
          {data.title || ''}
        </span>
      </div>

      {data.body && (
        <div className="text-xs leading-relaxed opacity-85 whitespace-pre-wrap overflow-hidden flex-grow mt-1 font-mono">
          {data.body}
        </div>
      )}
    </div>
  );
};

export default CardNode;
