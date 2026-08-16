import React, { useRef } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';
import { useShrinkToFitWidestWord } from '../../hooks/useShrinkToFitWidestWord';

// See useShrinkToFitWidestWord.ts for the full rationale (canvas-measured
// widest-word shrink to avoid the browser's `overflow-wrap: break-word`
// fallback chopping a word mid-syllable, e.g. "Warehous" / "e"). This was
// the original, live-verified implementation of that fix; the hook itself
// now lives in the shared file so CardNode, CloudNode, EllipseNode,
// InputNode, LabelNode, and PanelNode can reuse it.
const TITLE_BASE_FONT_PX = 12; // text-xs
const TITLE_MIN_FONT_PX = 8;
const BODY_BASE_FONT_PX = 10; // text-[10px]
const BODY_MIN_FONT_PX = 7;

export const CylinderNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#3b82f6';
  const strokeWidth = style.strokeWidth ?? 2;
  const accentColor = style.color || '#3b82f6';
  const isBorderless = !!style.borderless;
  const isTransparent = !!style.transparent;

  const titleText = String(data.title || '');
  const bodyText = String(data.body || '');
  const titleRef = useRef<HTMLSpanElement>(null);
  const bodyRef = useRef<HTMLSpanElement>(null);
  const titleFontSize = useShrinkToFitWidestWord(titleRef, titleText, TITLE_BASE_FONT_PX, TITLE_MIN_FONT_PX);
  const bodyFontSize = useShrinkToFitWidestWord(bodyRef, bodyText, BODY_BASE_FONT_PX, BODY_MIN_FONT_PX);

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
      className={`relative flex flex-col items-center justify-center select-none transition-all duration-200 ${isPureRender ? '' : 'animate-zoom-in'} ${
        selected ? 'ring-1 ring-indigo-500/40 rounded-lg' : 'cursor-pointer'
      }`}
      style={{
        width: '100%',
        height: '100%',
        minWidth: 100,
        minHeight: 80,
      }}
    >
      {/* Cylinder Background SVG */}
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
        {/* Main Body */}
        <path
          d="M 5,20 L 5,80 A 45,15 0 0,0 95,80 L 95,20 Z"
          fill={isTransparent ? 'transparent' : 'var(--node-bg)'}
          stroke={isBorderless ? 'transparent' : (selected ? strokeColor : 'var(--border-default)')}
          strokeWidth={strokeWidth}
        />
        {/* Top Lid */}
        <ellipse
          cx="50"
          cy="20"
          rx="45"
          ry="15"
          fill={isTransparent ? 'transparent' : 'var(--surface-2)'}
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
      <div className="z-10 flex flex-col items-center justify-center p-4 text-center mt-3 max-w-[80%]">
        {data.icon && <Icon name={data.icon as string} color={accentColor} size={16} className="mb-1" />}
        <span
          ref={titleRef}
          className="font-extrabold tracking-wide text-text-primary whitespace-normal break-words max-w-full"
          style={{ fontSize: titleFontSize }}
        >
          {titleText}
        </span>
        {bodyText && (
          <span
            ref={bodyRef}
            className="font-mono text-text-secondary font-medium mt-0.5 whitespace-normal break-words max-w-full"
            style={{ fontSize: bodyFontSize }}
          >
            {bodyText}
          </span>
        )}
      </div>
    </div>
  );
};

export default CylinderNode;
