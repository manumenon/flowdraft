import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

export const LabelNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: '#64748b',
    width: 6,
    height: 6,
    border: '1px solid var(--surface-1)',
  };

  return (
    <div className={`relative px-3 py-1.5 select-none w-full h-full flex items-center justify-center rounded-lg border transition-all duration-300 ${
      selected ? 'bg-surface-2 border-accent shadow-glow-blue' : 'bg-surface-0 border-border-themed hover:border-border-strong'
    }`}>
      {/* Handles */}
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="target" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="target" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="target" position={Position.Right} id="right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="right" style={handleStyle} />

      <span className="text-[11px] font-bold font-mono text-center break-words max-w-full text-text-secondary tracking-wider">
        {data.title || ''}
      </span>
    </div>
  );
};

export default LabelNode;
