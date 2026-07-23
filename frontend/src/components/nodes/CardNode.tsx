import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const CardNode: React.FC<NodeProps> = (props) => {
  const { selected } = props;
  const data = props.data as any;
  const style = data.style || {};
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');

  const strokeColor = style.strokeColor || style.color || '#3b82f6';
  const strokeWidth = style.strokeWidth ?? 2;
  const cornerRadius = style.cornerRadius ?? 12;
  const accentColor = style.color || '#3b82f6';
  const isBorderless = !!style.borderless;
  const isTransparent = !!style.transparent;
  const isBold = !!style.bold;

  // Handles configuration
  const handleStyle = {
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: accentColor,
    width: 6,
    height: 6,
    border: '1.5px solid var(--surface-1)',
  };

  const status = data.status || data.state;
  let statusColor = null;
  if (status === 'healthy' || status === 'active') statusColor = '#10b981';
  else if (status === 'streaming' || status === 'syncing') statusColor = '#06b6d4';
  else if (status === 'warning' || status === 'busy') statusColor = '#f59e0b';
  else if (data.glowColor) statusColor = data.glowColor;

  const variant = data.variant || style.variant;
  const VARIANT_MAP: Record<string, { bg: string; border: string; accent: string }> = {
    coral: { bg: 'rgba(244, 63, 94, 0.14)', border: '#f43f5e', accent: '#fda4af' },
    peach: { bg: 'rgba(249, 115, 22, 0.14)', border: '#f97316', accent: '#fed7aa' },
    mint: { bg: 'rgba(16, 185, 129, 0.14)', border: '#10b981', accent: '#a7f3d0' },
    sky: { bg: 'rgba(14, 165, 233, 0.14)', border: '#0ea5e9', accent: '#bae6fd' },
    amber: { bg: 'rgba(245, 158, 11, 0.14)', border: '#f59e0b', accent: '#fde68a' },
    purple: { bg: 'rgba(168, 85, 247, 0.14)', border: '#a855f7', accent: '#e9d5ff' },
    emerald: { bg: 'rgba(5, 150, 105, 0.14)', border: '#059669', accent: '#6ee7b7' }
  };
  const variantStyle = variant ? VARIANT_MAP[variant] : null;

  const nodeBg = variantStyle ? variantStyle.bg : (isTransparent ? 'transparent' : 'var(--node-bg)');
  const nodeBorderColor = variantStyle ? variantStyle.border : (selected ? strokeColor : (statusColor || 'var(--border-default)'));
  const effectiveAccent = variantStyle ? variantStyle.accent : (statusColor || accentColor);

  return (
    <div
      className={`relative px-4 py-3.5 flex flex-col justify-between h-full w-full select-none transition-all duration-300 animate-zoom-in ${
        selected 
          ? 'shadow-premium ring-1 ring-indigo-500/40' 
          : 'hover:shadow-xl cursor-pointer'
      }`}
      style={{
        backgroundColor: nodeBg,
        border: isBorderless ? 'none' : `${strokeWidth}px solid ${nodeBorderColor}`,
        borderRadius: `${cornerRadius}px`,
        color: 'var(--node-fg)',
        boxShadow: statusColor || variantStyle
          ? `0 0 20px 2px ${(statusColor || variantStyle?.border)}33, 0 8px 30px rgba(0,0,0,0.04)`
          : selected
            ? `0 0 16px 2px ${strokeColor}`
            : isPureRender
              ? 'none'
              : '0 8px 30px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.02)',
      }}
    >
      {/* Top border colored accent strip */}
      {!isTransparent && (
        <div
          className="absolute top-0 left-0 right-0 h-[3.5px] rounded-t-lg"
          style={{ backgroundColor: effectiveAccent }}
        />
      )}

      {/* Handles for connections on all 4 ports */}
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />

      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <Handle type="target" position={Position.Left} id="target-left" style={handleStyle} />
      <Handle type="source" position={Position.Left} id="source-left" style={handleStyle} />

      <Handle type="target" position={Position.Right} id="target-right" style={handleStyle} />
      <Handle type="source" position={Position.Right} id="source-right" style={handleStyle} />

      {/* Node Content */}
      <div className="flex items-center justify-between gap-2 mb-1.5 mt-1">
        <div className="flex items-center gap-2">
          {data.icon && (
            <div className="p-1 rounded-md bg-surface-3 border border-border-themed">
              <Icon name={data.icon as string} color={statusColor || accentColor} size={15} />
            </div>
          )}
          <span
            className="text-xs font-bold tracking-wide whitespace-normal break-words"
            style={{
              color: statusColor || accentColor,
              fontWeight: isBold ? 'bold' : '700',
            }}
          >
            {data.title || ''}
          </span>
        </div>

        {/* Live Status Pulsing Dot */}
        {statusColor && (
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span
              className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
              style={{ backgroundColor: statusColor }}
            />
            <span
              className="relative inline-flex rounded-full h-2.5 w-2.5"
              style={{ backgroundColor: statusColor }}
            />
          </span>
        )}
      </div>

      {data.body && (
        <div className="text-[11px] leading-relaxed whitespace-pre-wrap overflow-hidden flex-grow mt-1 font-mono text-text-secondary font-medium">
          {data.body}
        </div>
      )}

      {/* Render Annotations if defined in spec */}
      {data.annotations && data.annotations.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5 pointer-events-none z-10">
          {data.annotations.map((ann: any, idx: number) => (
            <div
              key={idx}
              className="text-[10px] px-2 py-0.5 rounded-md bg-surface-1/90 border shadow-sm font-semibold flex items-center gap-1.5 backdrop-blur-md"
              style={{
                borderColor: `${strokeColor}40`,
                color: 'var(--text-primary)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: strokeColor }} />
              <span className="leading-tight">{ann.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CardNode;
