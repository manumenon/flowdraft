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

  if (totalLength > 120) {
    titleFontSize = '8px';
    bodyFontSize = '7.5px';
  } else if (totalLength > 80) {
    titleFontSize = '9px';
    bodyFontSize = '8px';
  } else if (totalLength > 40) {
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
      className="relative w-full h-full select-none transition-all duration-200 animate-zoom-in cursor-pointer"
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

      {/* Centered text container with inner diamond geometry padding */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-[26%] py-[22%] pointer-events-none overflow-hidden">
        <span 
          className="font-extrabold leading-tight tracking-wider w-full break-words line-clamp-2" 
          style={{ color: accentColor, fontSize: titleFontSize }}
        >
          {data.title || ''}
        </span>
        {data.body && (
          <span 
            className="leading-tight whitespace-pre-wrap font-mono mt-1 w-full text-text-secondary font-medium break-words opacity-90 line-clamp-3"
            style={{ fontSize: bodyFontSize }}
          >
            {data.body}
          </span>
        )}
        {/* Render Annotations if defined in spec */}
        {data.annotations && data.annotations.length > 0 && (
          <div className="flex flex-wrap justify-center gap-1 mt-1 pointer-events-none z-10">
            {data.annotations.map((ann: any, idx: number) => (
              <div
                key={idx}
                className="text-[8px] px-1.5 py-0.5 rounded bg-surface-1/90 border shadow-sm font-semibold flex items-center gap-1 backdrop-blur-md"
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
    </div>
  );
};

export default DecisionNode;
