import React from 'react';
import type { AlignmentGuide } from '../hooks/useAlignmentGuides';

interface AlignmentGuidesOverlayProps {
  guides: AlignmentGuide[];
}

export const AlignmentGuidesOverlay: React.FC<AlignmentGuidesOverlayProps> = ({ guides }) => {
  if (!guides || guides.length === 0) return null;

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 9999,
      }}
    >
      <defs>
        <filter id="guide-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {guides.map((g) => {
        if (g.type === 'vertical' && g.x !== undefined) {
          const y1 = g.y1 ?? 0;
          const y2 = g.y2 ?? 2000;
          return (
            <g key={g.id}>
              <line
                x1={g.x}
                y1={y1}
                x2={g.x}
                y2={y2}
                stroke="#6366f1"
                strokeWidth="1.5"
                strokeDasharray="4 4"
                filter="url(#guide-glow)"
              />
              {g.label && (
                <g transform={`translate(${g.x + 8}, ${(y1 + y2) / 2})`}>
                  <rect x="0" y="-10" width="46" height="20" rx="4" fill="#6366f1" opacity="0.9" />
                  <text x="23" y="4" textAnchor="middle" fill="#ffffff" fontSize="11" fontWeight="600">
                    {g.label}
                  </text>
                </g>
              )}
            </g>
          );
        } else if (g.type === 'horizontal' && g.y !== undefined) {
          const x1 = g.x1 ?? 0;
          const x2 = g.x2 ?? 2000;
          return (
            <g key={g.id}>
              <line
                x1={x1}
                y1={g.y}
                x2={x2}
                y2={g.y}
                stroke="#6366f1"
                strokeWidth="1.5"
                strokeDasharray="4 4"
                filter="url(#guide-glow)"
              />
              {g.label && (
                <g transform={`translate(${(x1 + x2) / 2}, ${g.y - 12})`}>
                  <rect x="-23" y="-10" width="46" height="20" rx="4" fill="#6366f1" opacity="0.9" />
                  <text x="0" y="4" textAnchor="middle" fill="#ffffff" fontSize="11" fontWeight="600">
                    {g.label}
                  </text>
                </g>
              )}
            </g>
          );
        }
        return null;
      })}
    </svg>
  );
};
