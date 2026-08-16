import React, { useRef } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';
import { useShrinkToFitWidestWord } from '../../hooks/useShrinkToFitWidestWord';

// See useShrinkToFitWidestWord.ts for the full rationale. Unlike
// CylinderNode/CloudNode, EllipseNode's optional icon sits beside the title
// in the same row (not stacked above it), so the icon's live rendered
// width is reserved out of the row's measured width before fitting --
// otherwise the icon's share of the row would be counted as budget the
// title text doesn't actually have.
const TITLE_BASE_FONT_PX = 12; // text-xs
const TITLE_MIN_FONT_PX = 8;

export const EllipseNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#ec4899';
  const strokeWidth = style.strokeWidth ?? 2;
  const accentColor = style.color || '#ec4899';
  const isBorderless = !!style.borderless;
  const isTransparent = !!style.transparent;
  const isBold = !!style.bold;

  const titleText = String(data.title || '');
  const titleRef = useRef<HTMLSpanElement>(null);
  const iconRef = useRef<HTMLDivElement>(null);
  const titleFontSize = useShrinkToFitWidestWord(titleRef, titleText, TITLE_BASE_FONT_PX, TITLE_MIN_FONT_PX, {
    reservedRefs: [iconRef],
  });

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? ('none' as const) : ('auto' as const),
    background: accentColor,
    width: 6,
    height: 6,
    border: '1.5px solid var(--surface-1)',
  };

  return (
    <div
      className={`relative px-5 py-3.5 flex flex-col items-center justify-center h-full w-full rounded-full select-none transition-shadow duration-200 ${isPureRender ? '' : 'animate-zoom-in'} ${
        selected ? 'shadow-premium ring-1 ring-pink-500/40' : 'hover:shadow-xl cursor-pointer'
      }`}
      style={{
        backgroundColor: isTransparent ? 'transparent' : 'var(--node-bg)',
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${selected ? strokeColor : 'var(--border-default)'}`,
        color: 'var(--node-fg)',
        boxShadow: selected
          ? `0 0 16px 2px ${strokeColor}`
          : isPureRender
            ? 'none'
            : '0 8px 30px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.02)',
      }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="target-left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="source-left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="target-right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="source-right" style={handleStyle} />

      {/* Content */}
      <div className="flex flex-col items-center justify-center text-center max-w-[85%]">
        {/* min-w-0 on the row and the span: without it, this flex item's
            automatic minimum size is its content's min-content, and
            `break-words` (unlike `overflow-wrap: anywhere`) does not count
            toward reducing that per the flex sizing spec, so the row
            couldn't actually be squeezed below the title's natural
            (unbroken) width -- see CardNode.tsx's identical comment for
            the live-rendering-confirmed version of this failure mode. */}
        <div className="flex items-center justify-center gap-1.5 mb-0.5 min-w-0">
          {data.icon && (
            <div ref={iconRef} className="p-1 rounded-md bg-surface-3 border border-border-themed flex-shrink-0">
              <Icon name={data.icon as string} color={accentColor} size={14} />
            </div>
          )}
          <span
            ref={titleRef}
            className="font-bold tracking-wide whitespace-normal break-words min-w-0"
            style={{
              color: accentColor,
              fontWeight: isBold ? 'bold' : '700',
              fontSize: titleFontSize,
            }}
          >
            {titleText}
          </span>
        </div>

        {data.body && (
          <div className="text-[10px] leading-tight whitespace-pre-wrap overflow-hidden font-mono text-text-secondary font-medium">
            {data.body}
          </div>
        )}

        {/* Annotations */}
        {data.annotations && data.annotations.length > 0 && (
          <div className="mt-1 flex flex-wrap justify-center gap-1 pointer-events-none z-10">
            {data.annotations.map((ann: any, idx: number) => (
              <div
                key={idx}
                className="text-[8px] px-1.5 py-0.5 rounded-md bg-surface-1/90 border shadow-sm font-semibold flex items-center gap-1 backdrop-blur-md"
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

export default EllipseNode;
