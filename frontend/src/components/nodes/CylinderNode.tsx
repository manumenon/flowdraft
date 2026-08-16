import React, { useLayoutEffect, useRef, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

// Shrinks a title/body span's font-size (never its box) just enough that its
// single widest word fits the available text column, so the browser's
// `overflow-wrap: break-word` fallback never has to chop a word mid-syllable
// ("Warehous" / "e") -- mirrors scripts/flowdraft/text.py's fit_text
// "emergency font scaling" (binary-search a size that fits, measured via a
// real text-measurement API) but is scoped to just the widest word rather
// than the whole string, since the goal here is only to avoid ugly mid-word
// breaks, not to keep the title on one line.
//
// Deliberately a pure text-rendering tweak: it never touches node.width/
// height/style.width/style.height or the box the wrapper <div> below
// occupies (that stays "100%/100%" of whatever React Flow measured), so it
// cannot perturb React Flow's measured-size bookkeeping the way changing
// computeNodeDimensions's output did (see layoutCore.ts's
// computeNodeDimensions doc comment for that history/regression).
//
// CSS `hyphens: auto` was tried first as a zero-JS alternative but doesn't
// actually break "Warehouse" at a syllable boundary in Chromium (verified
// empirically -- the property parses and `getComputedStyle` reports
// 'auto', but headless Chromium here still hard-splits the word), so this
// canvas-measured approach is used instead; it depends only on Canvas 2D
// text measurement, which Chromium supports reliably.
const TITLE_BASE_FONT_PX = 12; // text-xs
const TITLE_MIN_FONT_PX = 8;
const BODY_BASE_FONT_PX = 10; // text-[10px]
const BODY_MIN_FONT_PX = 7;

let measureCanvasCtx: CanvasRenderingContext2D | null | undefined;
function getMeasureCtx(): CanvasRenderingContext2D | null {
  if (measureCanvasCtx === undefined) {
    const canvas = document.createElement('canvas');
    measureCanvasCtx = canvas.getContext('2d');
  }
  return measureCanvasCtx;
}

/** Font size (px) that fits `text`'s single widest word into `availablePx`, clamped to [minPx, basePx]. */
function fitWidestWordFontSize(
  ctx: CanvasRenderingContext2D,
  text: string,
  fontFamily: string,
  fontWeight: string,
  availablePx: number,
  basePx: number,
  minPx: number
): number {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length || !(availablePx > 0)) return basePx;

  ctx.font = `${fontWeight} ${basePx}px ${fontFamily}`;
  let widest = 0;
  for (const w of words) {
    const width = ctx.measureText(w).width;
    if (width > widest) widest = width;
  }
  if (widest <= availablePx) return basePx;

  const scaled = Math.floor((basePx * availablePx) / widest);
  return Math.max(minPx, Math.min(basePx, scaled));
}

/**
 * Measures `text` against `spanRef`'s parent column width (its clientWidth
 * minus its own padding -- the actual constrained text column, since that
 * parent is an unconstrained-width flex child capped by `max-w-[80%]`, so
 * its rendered width reflects the real budget regardless of how the text
 * inside currently happens to wrap) and returns the font size to apply.
 * Re-measures whenever `text` changes; box/container size here is static
 * per layout run (cylinder dimensions are a fixed per-type default, see
 * specCompiler.ts), so no ResizeObserver is needed.
 */
function useShrinkToFitWidestWord(
  spanRef: React.RefObject<HTMLSpanElement | null>,
  text: string,
  basePx: number,
  minPx: number
): number {
  const [fontSize, setFontSize] = useState(basePx);

  useLayoutEffect(() => {
    const el = spanRef.current;
    const parent = el?.parentElement;
    const ctx = getMeasureCtx();
    if (!el || !parent || !ctx || !text) {
      setFontSize(basePx);
      return;
    }

    const parentStyle = window.getComputedStyle(parent);
    const paddingX = parseFloat(parentStyle.paddingLeft || '0') + parseFloat(parentStyle.paddingRight || '0');
    const availablePx = parent.clientWidth - paddingX;

    const spanStyle = window.getComputedStyle(el);
    const size = fitWidestWordFontSize(
      ctx,
      text,
      spanStyle.fontFamily,
      spanStyle.fontWeight,
      availablePx,
      basePx,
      minPx
    );
    setFontSize(size);
  }, [text, basePx, minPx]);

  return fontSize;
}

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
      className={`relative flex flex-col items-center justify-center select-none transition-all duration-200 animate-zoom-in ${
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
