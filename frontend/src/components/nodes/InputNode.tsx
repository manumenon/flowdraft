import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const InputNode: React.FC<NodeProps> = (props) => {
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#f59e0b';
  const strokeWidth = style.strokeWidth ?? 2;
  const cornerRadius = style.cornerRadius ?? 8;
  const accentColor = style.color || '#f59e0b';
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
      className={`relative px-3 py-2 flex items-center justify-start h-full w-full select-none gap-2`}
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--node-bg, #1e1e2e)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${strokeColor}`,
        borderRadius: `${cornerRadius}px`,
        color: 'var(--node-fg, #cdd6f4)',
        boxShadow: isPureRender ? 'none' : '0 2px 4px rgba(0, 0, 0, 0.1)',
      }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="right" style={handleStyle} />

      {data.icon && <Icon name={data.icon as string} color={accentColor} size={18} className="flex-shrink-0" />}
      <span className="text-xs font-medium tracking-wide truncate flex-grow" style={{ color: accentColor }}>
        {data.title || ''}
      </span>
    </div>
  );
};

export default InputNode;
