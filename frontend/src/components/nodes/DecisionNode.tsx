import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

export const DecisionNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#ef4444';
  const strokeWidth = style.strokeWidth ?? 2.5;
  const accentColor = style.color || '#ef4444';
  const fill = style.transparent ? 'transparent' : 'var(--node-bg)';

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: accentColor,
    width: 6,
    height: 6,
    border: '1.5px solid var(--surface-1)',
  };

  return (
    <div className={`relative w-full h-full select-none transition-all duration-300 ${selected ? 'scale-[1.01]' : ''}`}>
      {/* SVG outline for Diamond */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <polygon
          points="50,2 98,50 50,98 2,50"
          fill={fill}
          stroke={selected ? 'var(--accent)' : strokeColor}
          strokeWidth={selected ? strokeWidth + 1 : strokeWidth}
          vectorEffect="non-scaling-stroke"
          className="transition-all duration-300"
        />
      </svg>

      {/* Handles at the vertices */}
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="right" style={handleStyle} />

      {/* Centered text container */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-4 pointer-events-none">
        <span className="text-[10px] font-extrabold leading-tight tracking-wider" style={{ color: accentColor }}>
          {data.title || ''}
        </span>
        {data.body && (
          <span className="text-[10px] leading-normal opacity-70 whitespace-pre-wrap font-mono mt-1 max-w-[80%] text-text-secondary">
            {data.body}
          </span>
        )}
      </div>
    </div>
  );
};

export default DecisionNode;
