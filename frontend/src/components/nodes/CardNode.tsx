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
      className={`relative px-4 py-3.5 flex flex-col justify-between h-full w-full select-none transition-all duration-300 animate-zoom-in ${
        selected 
          ? 'scale-[1.02] shadow-premium' 
          : 'hover:scale-[1.03] hover:-translate-y-1 hover:shadow-xl cursor-pointer'
      }`}
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--node-bg)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${selected ? strokeColor : 'var(--border-default)'}`,
        borderRadius: `${cornerRadius}px`,
        color: 'var(--node-fg)',
        boxShadow: selected
          ? `0 0 0 3px ${strokeColor}55, 0 16px 36px -8px ${strokeColor}33, 0 8px 16px -8px ${strokeColor}33`
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
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="right" style={handleStyle} />

      {/* Node Content */}
      <div className="flex items-center gap-2 mb-1.5 mt-1">
        {data.icon && (
          <div className="p-1 rounded-md bg-surface-3 border border-border-themed">
            <Icon name={data.icon as string} color={accentColor} size={15} />
          </div>
        )}
        <span
          className="text-xs font-bold tracking-wide truncate"
          style={{
            color: accentColor,
            fontWeight: isBold ? 'bold' : '700',
          }}
        >
          {data.title || ''}
        </span>
      </div>

      {data.body && (
        <div className="text-[11px] leading-relaxed opacity-75 whitespace-pre-wrap overflow-hidden flex-grow mt-1 font-mono text-text-secondary">
          {data.body}
        </div>
      )}
    </div>
  );
};

export default CardNode;
