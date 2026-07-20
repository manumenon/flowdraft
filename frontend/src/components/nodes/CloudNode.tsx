import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const CloudNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#06b6d4';
  const strokeWidth = style.strokeWidth ?? 2;
  const accentColor = style.color || '#06b6d4';
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
      className={`relative flex flex-col items-center justify-center select-none transition-all duration-300 animate-zoom-in ${
        selected ? 'scale-[1.02]' : 'hover:scale-[1.03] cursor-pointer'
      }`}
      style={{
        width: '100%',
        height: '100%',
        minWidth: 120,
        minHeight: 80,
      }}
    >
      {/* Cloud Shape SVG */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none transition-all duration-300"
        preserveAspectRatio="none"
        viewBox="0 0 100 100"
        style={{
          filter: selected 
            ? `drop-shadow(0 0 8px ${strokeColor})` 
            : 'drop-shadow(0 4px 6px rgba(0, 0, 0, 0.15))',
        }}
      >
        <path
          d="M 25,65 
             A 20,20 0 0,1 25,35 
             A 22,22 0 0,1 60,25 
             A 20,20 0 0,1 85,45 
             A 15,15 0 0,1 80,70 
             Z"
          fill={isTransparent ? 'transparent' : 'var(--node-bg)'}
          stroke={isBorderless ? 'transparent' : (selected ? strokeColor : 'var(--border-default)')}
          strokeWidth={strokeWidth}
        />
      </svg>

      {/* Handles */}
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="target-left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="source-left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="target-right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="source-right" style={handleStyle} />

      {/* Text Content overlay */}
      <div className="z-10 flex flex-col items-center justify-center p-4 text-center mt-2 max-w-[70%]">
        {data.icon && <Icon name={data.icon as string} color={accentColor} size={16} className="mb-1" />}
        <span className="text-xs font-extrabold tracking-wide text-text-primary whitespace-normal break-words max-w-full">
          {data.title || ''}
        </span>
        {data.body && (
          <span className="text-[10px] opacity-75 font-mono text-text-secondary mt-0.5 whitespace-normal break-words max-w-full">
            {data.body}
          </span>
        )}
      </div>
    </div>
  );
};

export default CloudNode;
