import React, { useState } from 'react';
import type { FlowSpec, ElementSpec } from '../types/spec';
import { Trash2 } from 'lucide-react';
import Icon from './nodes/Icon';

interface PropertyEditorProps {
  spec: FlowSpec;
  selectedElementId: string | null;
  selectedEdge: { from: string; to: string; index: number } | null;
  onUpdateSpec: (updater: (prev: FlowSpec) => FlowSpec) => void;
  onClearSelection: () => void;
}

const COMMON_ICONS = [
  'Globe', 'Database', 'Server', 'Cpu', 'Cloud', 'Settings2', 'Code', 'MessageSquare',
  'Shield', 'Key', 'Layers', 'Terminal', 'Play', 'HardDrive', 'Network', 'Zap'
];

const PRESET_COLORS = [
  { name: 'Teal', value: '#14b8a6' },
  { name: 'Emerald', value: '#10b981' },
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Indigo', value: '#6366f1' },
  { name: 'Amber', value: '#f59e0b' },
  { name: 'Rose', value: '#f43f5e' },
  { name: 'Purple', value: '#a855f7' },
  { name: 'Slate', value: '#64748b' }
];

const COMPONENT_TEMPLATES = [
  { title: 'API Gateway', type: 'card', icon: 'Globe', color: '#3b82f6' },
  { title: 'Postgres DB', type: 'card', icon: 'Database', color: '#14b8a6' },
  { title: 'Redis Cache', type: 'card', icon: 'Zap', color: '#f59e0b' },
  { title: 'Object Storage', type: 'card', icon: 'HardDrive', color: '#f43f5e' },
  { title: 'Queue Worker', type: 'card', icon: 'Cpu', color: '#a855f7' }
];

export const PropertyEditor: React.FC<PropertyEditorProps> = ({
  spec,
  selectedElementId,
  selectedEdge,
  onUpdateSpec,
  onClearSelection,
}) => {
  const [confirmDeleteNode, setConfirmDeleteNode] = useState(false);
  const [confirmDeleteEdge, setConfirmDeleteEdge] = useState(false);

  // Find selected node in flat elements
  const findElementRecursive = (elements: ElementSpec[], id: string): ElementSpec | null => {
    for (const el of elements) {
      if (el.id === id) return el;
      if (el.children) {
        const found = findElementRecursive(el.children, id);
        if (found) return found;
      }
    }
    return null;
  };

  const selectedNode = selectedElementId
    ? findElementRecursive(spec.elements, selectedElementId)
    : null;

  const selectedConnection = selectedEdge && spec.connections
    ? spec.connections.find((c, idx) => c.from === selectedEdge.from && c.to === selectedEdge.to && idx === selectedEdge.index)
    : null;

  const updateNodeProperty = (key: keyof ElementSpec | string, value: any, isStyle = false) => {
    if (!selectedElementId) return;

    onUpdateSpec((prev) => {
      const updateRecursive = (elements: ElementSpec[]): ElementSpec[] => {
        return elements.map((el) => {
          if (el.id === selectedElementId) {
            if (isStyle) {
              return {
                ...el,
                style: {
                  ...(el.style || {}),
                  [key]: value,
                },
              };
            }
            return {
              ...el,
              [key]: value,
            };
          }
          if (el.children) {
            return {
              ...el,
              children: updateRecursive(el.children),
            };
          }
          return el;
        });
      };

      return {
        ...prev,
        elements: updateRecursive(prev.elements),
      };
    });
  };

  const updateConnectionProperty = (key: string, value: any) => {
    if (!selectedEdge) return;

    onUpdateSpec((prev) => {
      const updatedConns = (prev.connections || []).map((conn, idx) => {
        if (conn.from === selectedEdge.from && conn.to === selectedEdge.to && idx === selectedEdge.index) {
          return {
            ...conn,
            [key]: value,
          };
        }
        return conn;
      });
      return {
        ...prev,
        connections: updatedConns,
      };
    });
  };

  const deleteNode = () => {
    if (!selectedElementId) return;
    onUpdateSpec((prev) => {
      const removeRecursive = (elements: ElementSpec[]): ElementSpec[] => {
        return elements
          .filter((el) => el.id !== selectedElementId)
          .map((el) => {
            if (el.children) {
              return {
                ...el,
                children: removeRecursive(el.children),
              };
            }
            return el;
          });
      };

      const cleanConns = (prev.connections || []).filter(
        (conn) => conn.from !== selectedElementId && conn.to !== selectedElementId
      );

      return {
        ...prev,
        connections: cleanConns,
        elements: removeRecursive(prev.elements),
      };
    });
    onClearSelection();
    setConfirmDeleteNode(false);
  };

  const deleteConnection = () => {
    if (!selectedEdge) return;
    onUpdateSpec((prev) => {
      const cleanConns = (prev.connections || []).filter(
        (conn, idx) => !(conn.from === selectedEdge.from && conn.to === selectedEdge.to && idx === selectedEdge.index)
      );
      return {
        ...prev,
        connections: cleanConns,
      };
    });
    onClearSelection();
    setConfirmDeleteEdge(false);
  };

  const handleAddComponent = (template: typeof COMPONENT_TEMPLATES[0]) => {
    const slug = template.title.toLowerCase().replace(/\s+/g, '-');
    const newId = `${slug}-${Date.now().toString().slice(-4)}`;
    
    const newElement: ElementSpec = {
      id: newId,
      type: template.type as any,
      title: template.title,
      body: 'Active data node...',
      icon: template.icon,
      style: {
        color: template.color,
        strokeColor: template.color,
        cornerRadius: 12,
        strokeWidth: 2,
      },
    };

    onUpdateSpec((prev) => ({
      ...prev,
      elements: [...prev.elements, newElement],
    }));
  };

  return (
    <div className="w-80 bg-surface-1 border-l border-border-themed flex flex-col h-full flex-shrink-0 overflow-y-auto custom-scrollbar p-5 relative shadow-premium text-text-primary font-sans">
      {selectedNode ? (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between pb-3 border-b border-border-themed">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              <span className="font-semibold text-[11px] uppercase tracking-wider text-text-muted">Node Properties</span>
            </div>
            
            {!confirmDeleteNode ? (
              <button
                onClick={() => setConfirmDeleteNode(true)}
                className="p-1.5 bg-red-100 dark:bg-red-950/20 hover:bg-red-200 dark:hover:bg-red-950/50 text-red-600 dark:text-slate-500 dark:hover:text-red-400 border border-red-200 dark:border-red-900/30 rounded-lg transition focus-ring"
                title="Delete Component"
                aria-label="Delete Component"
              >
                <Trash2 size={14} />
              </button>
            ) : (
              <div className="flex items-center gap-1.5 animate-zoom-in">
                <button
                  onClick={deleteNode}
                  className="px-2 py-1 bg-red-600 hover:bg-red-500 text-[10px] font-bold uppercase rounded text-white"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setConfirmDeleteNode(false)}
                  className="px-2 py-1 bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-[10px] font-bold uppercase rounded text-slate-600 dark:text-slate-400"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* Node ID */}
          <div>
            <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Node ID</label>
            <span className="font-mono text-xs text-text-secondary bg-surface-0 px-3 py-2 rounded-lg border border-border-themed block select-all">
              {selectedNode.id}
            </span>
          </div>

          {/* Title */}
          <div>
            <label htmlFor="node-title-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Title</label>
            <input
              id="node-title-input"
              type="text"
              value={selectedNode.title || ''}
              onChange={(e) => updateNodeProperty('title', e.target.value)}
              className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring"
            />
          </div>

          {/* Subtitle (Panel Nodes Only) */}
          {selectedNode.type === 'panel' && (
            <div>
              <label htmlFor="node-subtitle-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Subtitle</label>
              <input
                id="node-subtitle-input"
                type="text"
                value={selectedNode.subtitle || ''}
                onChange={(e) => updateNodeProperty('subtitle', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring"
              />
            </div>
          )}

          {/* Badge indicator (Panel Nodes Only) */}
          {selectedNode.type === 'panel' && (
            <div>
              <label htmlFor="node-badge-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Badge Text</label>
              <input
                id="node-badge-input"
                type="text"
                value={selectedNode.badge || ''}
                onChange={(e) => updateNodeProperty('badge', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring"
              />
            </div>
          )}

          {/* Body */}
          {selectedNode.type !== 'panel' && selectedNode.type !== 'label' && (
            <div>
              <label htmlFor="node-body-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Body Text</label>
              <textarea
                id="node-body-input"
                value={selectedNode.body || ''}
                onChange={(e) => updateNodeProperty('body', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent font-mono h-24 resize-none transition focus-ring"
              />
            </div>
          )}

          <div>
            <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2.5">Accent Color</label>
            <div className="flex flex-wrap gap-2 bg-surface-0 p-2.5 rounded-lg border border-border-themed">
              {PRESET_COLORS.map((col) => (
                <button
                  key={col.value}
                  onClick={() => {
                    updateNodeProperty('color', col.value, true);
                    updateNodeProperty('strokeColor', col.value, true);
                  }}
                  className={`w-6 h-6 rounded-full border transition flex items-center justify-center focus-ring ${
                    selectedNode.style?.color === col.value
                      ? 'border-accent dark:border-white scale-110 shadow-glow-blue'
                      : 'border-border-themed hover:border-border-strong hover:scale-105'
                  }`}
                  style={{ backgroundColor: col.value }}
                  title={col.name}
                  aria-label={`Color ${col.name}`}
                />
              ))}
            </div>
          </div>

          {/* Graphical Icon Selector */}
          {selectedNode.type !== 'panel' && selectedNode.type !== 'label' && (
            <div className="flex flex-col gap-2">
              <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider">Node Icon</label>
              <div className="grid grid-cols-4 gap-2 bg-surface-0 border border-border-themed p-2 rounded-lg max-h-36 overflow-y-auto custom-scrollbar">
                <button
                  onClick={() => updateNodeProperty('icon', null)}
                  className={`p-1.5 rounded-lg flex items-center justify-center text-[10px] font-bold transition border focus-ring ${
                    !selectedNode.icon
                      ? 'bg-accent-soft text-accent border-accent/20'
                      : 'text-text-secondary border-transparent hover:bg-surface-2 hover:text-text-primary'
                  }`}
                >
                  None
                </button>
                {COMMON_ICONS.map((ic) => (
                  <button
                    key={ic}
                    onClick={() => updateNodeProperty('icon', ic)}
                    className={`p-1.5 rounded-lg flex items-center justify-center border transition focus-ring ${
                      selectedNode.icon?.toLowerCase() === ic.toLowerCase()
                        ? 'bg-accent-soft text-accent border-accent/20 shadow-sm'
                        : 'text-text-secondary border-transparent hover:bg-surface-2 hover:text-text-primary'
                    }`}
                    title={ic}
                    aria-label={`Icon ${ic}`}
                  >
                    <Icon name={ic} size={15} />
                  </button>
                ))}
              </div>
              <div className="mt-1">
                <label htmlFor="custom-icon-input" className="block text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1">Custom SVG / Image URL</label>
                <input
                  id="custom-icon-input"
                  type="text"
                  placeholder="Paste <svg>... or https://..."
                  value={selectedNode.icon || ''}
                  onChange={(e) => updateNodeProperty('icon', e.target.value)}
                  className="w-full px-3 py-1.5 bg-surface-0 border border-border-themed rounded-lg text-[11px] text-text-primary focus:outline-none focus:border-accent transition font-mono focus-ring"
                />
              </div>
            </div>
          )}

          {/* Stroke Width Slider */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label htmlFor="stroke-width-slider" className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Stroke Width</label>
              <span className="text-[11px] font-mono text-text-secondary">{selectedNode.style?.strokeWidth ?? 2}px</span>
            </div>
            <input
              id="stroke-width-slider"
              type="range"
              min="0"
              max="6"
              step="1"
              value={selectedNode.style?.strokeWidth ?? 2}
              onChange={(e) => updateNodeProperty('strokeWidth', parseInt(e.target.value), true)}
              className="w-full accent-indigo-600 bg-surface-3 h-1 rounded-lg focus-ring"
            />
          </div>

          {/* Corner Radius Slider */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label htmlFor="corner-radius-slider" className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Corner Radius</label>
              <span className="text-[11px] font-mono text-text-secondary">{selectedNode.style?.cornerRadius ?? 12}px</span>
            </div>
            <input
              id="corner-radius-slider"
              type="range"
              min="0"
              max="32"
              step="2"
              value={selectedNode.style?.cornerRadius ?? 12}
              onChange={(e) => updateNodeProperty('cornerRadius', parseInt(e.target.value), true)}
              className="w-full accent-indigo-600 bg-surface-3 h-1 rounded-lg focus-ring"
            />
          </div>

          {/* Style Configuration Toggles */}
          <div className="flex flex-col gap-2.5 pt-3.5 border-t border-border-themed">
            <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1">Styling Configuration</span>
            <label className="flex items-center gap-2.5 cursor-pointer text-xs text-text-secondary select-none">
              <input
                type="checkbox"
                checked={!!selectedNode.style?.transparent}
                onChange={(e) => updateNodeProperty('transparent', e.target.checked, true)}
                className="rounded accent-indigo-600 focus-ring"
              />
              <span>Transparent Background</span>
            </label>

            <label className="flex items-center gap-2.5 cursor-pointer text-xs text-text-secondary select-none">
              <input
                type="checkbox"
                checked={!!selectedNode.style?.borderless}
                onChange={(e) => updateNodeProperty('borderless', e.target.checked, true)}
                className="rounded accent-indigo-600 focus-ring"
              />
              <span>No Border Outline</span>
            </label>

            {selectedNode.type !== 'panel' && (
              <label className="flex items-center gap-2.5 cursor-pointer text-xs text-text-secondary select-none">
                <input
                  type="checkbox"
                  checked={!!selectedNode.style?.bold}
                  onChange={(e) => updateNodeProperty('bold', e.target.checked, true)}
                  className="rounded accent-indigo-600 focus-ring"
                />
                <span>Bold Header Text</span>
              </label>
            )}
          </div>
        </div>
      ) : selectedConnection ? (
        <div className="flex flex-col gap-6 animate-fade-in">
          <div className="flex items-center justify-between pb-3 border-b border-border-themed">
            <span className="font-semibold text-xs uppercase tracking-wider text-text-muted">Link Properties</span>
            
            {!confirmDeleteEdge ? (
              <button
                onClick={() => setConfirmDeleteEdge(true)}
                className="p-1.5 bg-red-100 hover:bg-red-200 text-red-600 border border-red-200 dark:border-red-900/30 rounded-lg transition focus-ring"
                title="Delete Connection"
                aria-label="Delete Connection"
              >
                <Trash2 size={14} />
              </button>
            ) : (
              <div className="flex items-center gap-1.5 animate-zoom-in">
                <button
                  onClick={deleteConnection}
                  className="px-2 py-1 bg-red-600 hover:bg-red-500 text-[10px] font-bold uppercase rounded text-white"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setConfirmDeleteEdge(false)}
                  className="px-2 py-1 bg-surface-3 hover:bg-surface-2 text-[10px] font-bold uppercase rounded text-text-secondary"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* Link Ports Info */}
          <div className="grid grid-cols-2 gap-3 p-3 bg-surface-0 border border-border-themed rounded-xl">
            <div>
              <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider block mb-0.5">Source</span>
              <span className="text-text-secondary font-mono truncate block mt-1 bg-surface-2 p-1 px-1.5 rounded">{selectedConnection.from}</span>
            </div>
            <div>
              <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider block mb-0.5">Target</span>
              <span className="text-text-secondary font-mono truncate block mt-1 bg-surface-2 p-1 px-1.5 rounded">{selectedConnection.to}</span>
            </div>
          </div>

          {/* Connection Label */}
          <div>
            <label htmlFor="connection-label-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Connection Label</label>
            <input
              id="connection-label-input"
              type="text"
              value={selectedConnection.label || ''}
              onChange={(e) => updateConnectionProperty('label', e.target.value)}
              className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring"
              placeholder="e.g. gRPC, HTTPS, SQL"
            />
          </div>

          {/* Link styling selection */}
          <div>
            <label htmlFor="connection-style-select" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Connection Line Style</label>
            <select
              id="connection-style-select"
              value={selectedConnection.style || 'solid'}
              onChange={(e) => updateConnectionProperty('style', e.target.value)}
              className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring"
            >
              <option value="solid">Solid Path</option>
              <option value="dashed">Dashed Path</option>
              <option value="dotted">Dotted Path</option>
            </select>
          </div>

          {/* Connection color */}
          <div>
            <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2.5">Connection Line Color</label>
            <div className="flex flex-wrap gap-2 bg-surface-0 p-2.5 rounded-lg border border-border-themed">
              {PRESET_COLORS.map((col) => (
                <button
                  key={col.value}
                  onClick={() => updateConnectionProperty('color', col.value)}
                  className={`w-6 h-6 rounded-full border transition focus-ring ${
                    selectedConnection.color === col.value
                      ? 'border-accent dark:border-white scale-110 shadow-glow-blue'
                      : 'border-border-themed hover:border-border-strong hover:scale-105'
                  }`}
                  style={{ backgroundColor: col.value }}
                  title={col.name}
                  aria-label={`Line color ${col.name}`}
                />
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-6 animate-fade-in">
          <div>
            <span className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-3">Spawn Component</span>
            <div className="flex flex-col gap-2">
              {COMPONENT_TEMPLATES.map((tmpl) => (
                <button
                  key={tmpl.title}
                  onClick={() => handleAddComponent(tmpl)}
                  className="flex items-center gap-3 p-3 bg-surface-0 border border-border-themed hover:border-border-strong rounded-xl hover:bg-surface-2 transition text-left group focus-ring animate-fade-in"
                >
                  <div
                    className="p-1.5 rounded-lg border flex items-center justify-center bg-accent-soft"
                    style={{
                      borderColor: `${tmpl.color}25`,
                      color: tmpl.color,
                    }}
                  >
                    <Icon name={tmpl.icon} size={15} />
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-bold text-text-primary truncate">{tmpl.title}</span>
                    <span className="text-[10px] text-text-muted font-mono mt-0.5 uppercase">Template Node</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="p-4 bg-accent-soft border border-accent/20 rounded-xl text-[11px] leading-relaxed text-text-secondary">
            Select any existing component card, title block, or connecting path on the layout canvas to modify properties.
          </div>
        </div>
      )}
    </div>
  );
};
