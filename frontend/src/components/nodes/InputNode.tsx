import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const InputNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
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
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: accentColor,
    width: 6,
    height: 6,
    border: '1.5px solid var(--surface-1)',
  };

  return (
    <div
      className={`relative px-4 py-2.5 flex items-center justify-start h-full w-full select-none gap-2 transition-shadow duration-200 animate-zoom-in ${
        selected 
          ? 'shadow-premium ring-1 ring-amber-500/40' 
          : 'hover:shadow-lg cursor-pointer'
      }`}
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--node-bg)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${selected ? strokeColor : 'var(--border-default)'}`,
        borderRadius: `${cornerRadius ?? 24}px`,
        color: 'var(--node-fg)',
        boxShadow: selected
          ? `0 0 16px 2px ${strokeColor}`
          : isPureRender
            ? 'none'
            : '0 6px 20px rgba(0, 0, 0, 0.03)',
      }}
    >
      {/* 3px left color accent strip */}
      {!isTransparent && (
        <div
          className="absolute left-0 top-0 bottom-0 w-[3.5px] rounded-l-full"
          style={{ backgroundColor: accentColor }}
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

      {data.icon && <Icon name={data.icon as string} color={accentColor} size={15} className="flex-shrink-0 ml-1" />}
      <span className="text-xs font-semibold tracking-wide whitespace-normal break-words flex-grow text-text-primary">
        {data.title || ''}
      </span>

      {/* Render Annotations if defined in spec */}
      {data.annotations && data.annotations.length > 0 && (
        <div className="flex flex-wrap gap-1 pointer-events-none z-10 ml-auto">
          {data.annotations.map((ann: any, idx: number) => (
            <div
              key={idx}
              className="text-[9px] px-1.5 py-0.5 rounded bg-surface-1/90 border shadow-sm font-semibold flex items-center gap-1 backdrop-blur-md"
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
  );
};

export default InputNode;
