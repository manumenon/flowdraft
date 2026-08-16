import React, { useRef } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { useShrinkToFitWidestWord } from '../../hooks/useShrinkToFitWidestWord';

// See useShrinkToFitWidestWord.ts for the full rationale. The title span's
// parent is the node's own fixed React-Flow-measured box (Handles are
// absolutely positioned and don't consume row space), so no sibling width
// needs to be reserved.
const TITLE_BASE_FONT_PX = 11; // text-[11px]
const TITLE_MIN_FONT_PX = 7;

export const LabelNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const titleText = String(data.title || '');
  const titleRef = useRef<HTMLSpanElement>(null);
  const titleFontSize = useShrinkToFitWidestWord(titleRef, titleText, TITLE_BASE_FONT_PX, TITLE_MIN_FONT_PX);

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: '#64748b',
    width: 6,
    height: 6,
    border: '1px solid var(--surface-1)',
  };

  return (
    <div className={`relative px-3 py-1.5 select-none w-full h-full flex items-center justify-center rounded-lg border border-dashed transition-all duration-300 ${isPureRender ? '' : 'animate-zoom-in'} ${
      selected 
        ? 'bg-surface-2/80 border-accent shadow-glow-blue scale-[1.02]' 
        : 'bg-surface-0/40 border-border-themed hover:border-border-strong hover:bg-surface-1/40 hover:scale-[1.03] cursor-pointer'
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

      <span
        ref={titleRef}
        className="font-bold font-mono text-center break-words max-w-full text-text-secondary tracking-wider"
        style={{ fontSize: titleFontSize }}
      >
        {titleText}
      </span>
    </div>
  );
};

export default LabelNode;
