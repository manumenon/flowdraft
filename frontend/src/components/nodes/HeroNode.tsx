import React from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import Icon from './Icon';

export const HeroNode: React.FC<NodeProps> = (props) => {
  const data = props.data as any;
  const isPureRender = data.isPureRender || window.location.pathname.includes('/render-box');
  const title = data.title || 'Summary & Key Objectives';
  const subtitle = data.body || data.subtitle || '';
  const bullets: string[] = data.bullets || [];

  const handleStyle = {
    opacity: isPureRender ? 0 : 0.8,
    pointerEvents: isPureRender ? 'none' as const : 'auto' as const,
    background: '#6366f1',
    width: 6,
    height: 6,
    border: '1.5px solid var(--surface-1)',
  };

  return (
    <div
      className="relative px-6 py-4 rounded-xl border border-indigo-500/40 bg-gradient-to-r from-blue-950/40 via-indigo-950/30 to-purple-950/40 backdrop-blur-md shadow-2xl w-full h-full text-slate-100 flex flex-col justify-between"
      style={{
        boxShadow: '0 0 25px rgba(99, 102, 241, 0.15), 0 10px 40px rgba(0,0,0,0.4)',
      }}
    >
      <Handle type="target" position={Position.Top} id="target-top" style={handleStyle} />
      <Handle type="source" position={Position.Top} id="source-top" style={handleStyle} />
      <Handle type="target" position={Position.Bottom} id="target-bottom" style={handleStyle} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" style={handleStyle} />

      <div className="flex items-center gap-3 border-b border-indigo-500/20 pb-3 mb-3">
        <div className="p-2 rounded-lg bg-indigo-500/20 border border-indigo-400/30 text-indigo-400">
          <Icon name="package" size={20} color="#818cf8" />
        </div>
        <div>
          <h3 className="text-base font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-300 via-indigo-200 to-purple-300">
            {title}
          </h3>
          {subtitle && (
            <p className="text-xs text-slate-400 font-medium">{subtitle}</p>
          )}
        </div>
      </div>

      {bullets.length > 0 && (
        <ul className="space-y-2 text-xs text-slate-200">
          {bullets.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2.5">
              <span className="mt-1 text-indigo-400 font-bold">•</span>
              <span className="leading-relaxed text-slate-300">{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
