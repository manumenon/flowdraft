import React, { useState, useEffect, useRef } from 'react';
import { Search, Command } from 'lucide-react';

interface ActionItem {
  id: string;
  title: string;
  category: string;
  shortcut?: string;
  icon: React.ReactNode;
  action: () => void;
}

interface CommandPaletteProps {
  onClose: () => void;
  actions: ActionItem[];
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ onClose, actions }) => {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const filtered = actions.filter((item) =>
    item.title.toLowerCase().includes(search.toLowerCase()) ||
    item.category.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [search]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (filtered.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % filtered.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action();
        onClose();
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-[999] flex items-start justify-center pt-[15vh] p-4">
      <div
        ref={containerRef}
        className="w-full max-w-lg bg-surface-1/90 backdrop-blur-md border border-border-themed rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[380px] animate-zoom-in"
      >
         <div className="flex items-center gap-2.5 px-4 border-b border-border-themed h-12">
          <Search className="text-text-muted w-4 h-4" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command or search action..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-grow bg-transparent text-sm text-text-primary placeholder-text-muted focus:outline-none"
          />
          <div className="flex items-center gap-1 text-[10px] text-text-muted bg-surface-3 px-2 py-1 rounded-md border border-border-themed font-mono">
            <Command size={10} />
            <span>K</span>
          </div>
        </div>

        <div className="flex-grow overflow-y-auto custom-scrollbar p-2">
          {filtered.length === 0 ? (
            <div className="text-center py-8 text-xs text-text-muted">
              No actions found matching "{search}"
            </div>
          ) : (
            filtered.map((item, idx) => (
              <div
                key={item.id}
                onClick={() => {
                  item.action();
                  onClose();
                }}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition ${
                  idx === selectedIndex
                    ? 'bg-accent-soft text-accent border border-accent/20'
                    : 'text-text-secondary hover:bg-surface-2 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={idx === selectedIndex ? 'text-accent' : 'text-text-muted'}>
                    {item.icon}
                  </span>
                  <div className="flex flex-col">
                    <span className="text-xs font-bold">{item.title}</span>
                    <span className="text-[10px] uppercase tracking-wider text-text-muted font-mono mt-0.5">{item.category}</span>
                  </div>
                </div>
                {item.shortcut && (
                  <span className="text-[10px] text-text-muted font-mono bg-surface-3 px-1.5 py-0.5 rounded border border-border-themed">
                    {item.shortcut}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
export default CommandPalette;
