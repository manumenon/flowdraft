import React from 'react';
import { Panel } from '@xyflow/react';
import {
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignVerticalSpaceAround,
  ArrowLeftRight,
  ArrowUpDown,
} from 'lucide-react';

interface MultiSelectionToolbarProps {
  selectedNodes: any[];
  onAlign: (
    action:
      | 'left'
      | 'center'
      | 'right'
      | 'top'
      | 'middle'
      | 'bottom'
      | 'distribute-h'
      | 'distribute-v'
  ) => void;
}

export const MultiSelectionToolbar: React.FC<MultiSelectionToolbarProps> = ({
  selectedNodes,
  onAlign,
}) => {
  if (!selectedNodes || selectedNodes.length < 2) return null;

  return (
    <Panel position="top-center" className="z-30">
      <div className="flex items-center gap-1 px-3 py-1.5 bg-surface-1/90 border border-border-themed rounded-xl backdrop-blur-md shadow-lg animate-zoom-in">
        <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted mr-1.5">
          {selectedNodes.length} Selected
        </span>

        <div className="h-4 w-px bg-border-themed mx-1" />

        <button
          onClick={() => onAlign('left')}
          title="Align Left"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <AlignLeft size={16} />
        </button>
        <button
          onClick={() => onAlign('center')}
          title="Align Horizontal Center"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <AlignCenter size={16} />
        </button>
        <button
          onClick={() => onAlign('right')}
          title="Align Right"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <AlignRight size={16} />
        </button>

        <div className="h-4 w-px bg-border-themed mx-0.5" />

        <button
          onClick={() => onAlign('top')}
          title="Align Top"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="4" x2="20" y2="4" />
            <rect x="6" y="8" width="4" height="12" rx="1" />
            <rect x="14" y="8" width="4" height="8" rx="1" />
          </svg>
        </button>
        <button
          onClick={() => onAlign('middle')}
          title="Align Vertical Middle"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <AlignVerticalSpaceAround size={16} />
        </button>
        <button
          onClick={() => onAlign('bottom')}
          title="Align Bottom"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="20" x2="20" y2="20" />
            <rect x="6" y="4" width="4" height="12" rx="1" />
            <rect x="14" y="8" width="4" height="8" rx="1" />
          </svg>
        </button>

        <div className="h-4 w-px bg-border-themed mx-0.5" />

        <button
          onClick={() => onAlign('distribute-h')}
          title="Distribute Horizontally"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <ArrowLeftRight size={16} />
        </button>
        <button
          onClick={() => onAlign('distribute-v')}
          title="Distribute Vertically"
          className="p-1.5 text-text-secondary hover:text-accent hover:bg-accent-soft rounded-lg transition"
        >
          <ArrowUpDown size={16} />
        </button>
      </div>
    </Panel>
  );
};
