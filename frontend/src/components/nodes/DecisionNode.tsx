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

  const titleText = data.title || '';
  const bodyText = data.body || '';
  const totalLength = titleText.length + bodyText.length;

  let titleFontSize = '11px';
  let bodyFontSize = '10px';

  if (totalLength > 100) {
    titleFontSize = '9px';
    bodyFontSize = '8px';
  } else if (totalLength > 50) {
    titleFontSize = '10px';
    bodyFontSize = '9px';
  }

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
      className={`relative w-full h-full select-none transition-all duration-300 animate-zoom-in ${
        selected 
          ? 'scale-[1.03]' 
          : 'hover:scale-[1.05] cursor-pointer'
      }`}
      style={{
        filter: selected 
          ? `drop-shadow(0 0 8px ${accentColor})` 
          : 'drop-shadow(0 4px 6px rgba(0, 0, 0, 0.15))',
      }}
    >
      {/* SVG outline for Diamond */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <polygon
          points="50,2 98,50 50,98 2,50"
          fill={fill}
          stroke={selected ? strokeColor : strokeColor}
          strokeWidth={selected ? strokeWidth + 1.5 : strokeWidth}
          vectorEffect="non-scaling-stroke"
          className="transition-all duration-300"
        />
      </svg>

      {/* Handles at the vertices */}
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="target-left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="source-left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="target-right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="source-right" style={handleStyle} />

      {/* Centered text container */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-5 pointer-events-none">
        <span 
          className="font-extrabold leading-tight tracking-wider max-w-[70%] break-words" 
          style={{ color: accentColor, fontSize: titleFontSize }}
        >
          {data.title || ''}
        </span>
        {data.body && (
          <span 
            className="leading-normal opacity-70 whitespace-pre-wrap font-mono mt-1.5 max-w-[68%] text-text-secondary break-words"
            style={{ fontSize: bodyFontSize }}
          >
            {data.body}
          </span>
        )}
      </div>
    </div>
  );
};

export default DecisionNode;
