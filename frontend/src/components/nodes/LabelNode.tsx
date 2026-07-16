import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

export const LabelNode: React.FC<NodeProps> = (props) => {
  const data = props.data as any;
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.6,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: '#888',
    width: 6,
    height: 6,
  };

  return (
    <div className="relative px-2 py-1 select-none w-full h-full flex items-center justify-center">
      {/* Handles */}
      <Handle type="target" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="top" style={handleStyle} />
      <Handle type="target" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleStyle} />
      <Handle type="target" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="left" style={handleStyle} />
      <Handle type="target" position={Position.Right} id="right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="right" style={handleStyle} />

      <span className="text-xs font-mono text-center break-words max-w-full text-slate-300">
        {data.title || ''}
      </span>
    </div>
  );
};

export default LabelNode;
