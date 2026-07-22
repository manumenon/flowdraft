import React, { useState, useEffect, useMemo } from 'react';
import { useReactFlow } from '@xyflow/react';
import type { FlowSpec, ElementSpec } from '../types/spec';
import { Trash2, Settings, Plus, Sliders, ChevronLeft, Film, Search } from 'lucide-react';
import Icon from './nodes/Icon';
import { ExportPanel } from './ExportPanel';

interface PropertyEditorProps {
  spec: FlowSpec;
  selectedElementId: string | null;
  selectedEdge: { from: string; to: string; index: number } | null;
  onUpdateSpec: (updater: (prev: FlowSpec) => FlowSpec) => void;
  onClearSelection: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  token: string | null;
  activeDiagramId: string | null;
  onTriggerAuth: () => void;
  onLogout?: () => void;
  tourStep?: number | null;
}

const ICON_CATEGORIES = {
  'Infrastructure': ['Server', 'Database', 'HardDrive', 'Cloud', 'Network', 'Cpu', 'MemoryStick', 'Router', 'Wifi', 'Signal', 'Radio', 'Satellite'],
  'Development': ['Code', 'Terminal', 'GitBranch', 'GitMerge', 'GitPullRequest', 'Braces', 'FileCode', 'Bug', 'TestTube', 'Wrench', 'Hammer', 'Package'],
  'Security': ['Shield', 'ShieldCheck', 'Lock', 'Unlock', 'Key', 'Fingerprint', 'Eye', 'EyeOff', 'UserCheck', 'ShieldAlert'],
  'Data': ['Layers', 'Table', 'BarChart3', 'PieChart', 'TrendingUp', 'Activity', 'Binary', 'Hash', 'Filter', 'Search'],
  'Communication': ['MessageSquare', 'Mail', 'Send', 'Bell', 'Phone', 'Video', 'Megaphone', 'Rss', 'Share2', 'Link'],
  'General': ['Globe', 'Zap', 'Play', 'Settings2', 'RefreshCw', 'Clock', 'Calendar', 'Star', 'Heart', 'Flag', 'Bookmark', 'Download', 'Upload', 'ExternalLink', 'Box', 'Boxes', 'Container', 'Workflow'],
};

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
  { title: 'Queue Worker', type: 'card', icon: 'Cpu', color: '#a855f7' },
  { title: 'Database Cylinder', type: 'cylinder', icon: 'Database', color: '#2563eb' },
  { title: 'Cloud CDN', type: 'cloud', icon: 'Cloud', color: '#0891b2' },
  { title: 'Input Field / Trigger', type: 'input', icon: 'Terminal', color: '#10b981' },
  { title: 'Decision Node', type: 'diamond', icon: 'HelpCircle', color: '#ef4444' },
  { title: 'Panel / Group', type: 'panel', icon: 'Box', color: '#8b5cf6' },
  { title: 'Text Label', type: 'label', icon: 'Tag', color: '#64748b' },
  { title: 'Ellipse Oval', type: 'ellipse', icon: 'Circle', color: '#ec4899' },
];

export const PropertyEditor: React.FC<PropertyEditorProps> = ({
  spec,
  selectedElementId,
  selectedEdge,
  onUpdateSpec,
  onClearSelection,
  isCollapsed = false,
  onToggleCollapse,
  token,
  activeDiagramId,
  onTriggerAuth,
  onLogout,
  tourStep,
}) => {
  const { screenToFlowPosition, getNodes } = useReactFlow();
  const [confirmDeleteNode, setConfirmDeleteNode] = useState(false);
  const [confirmDeleteEdge, setConfirmDeleteEdge] = useState(false);
  const [activeTab, setActiveTab] = useState<'inspector' | 'spawn' | 'canvas' | 'export'>('spawn');
  const [iconSearch, setIconSearch] = useState('');

  const allIcons = useMemo(() => {
    return Object.values(ICON_CATEGORIES).flat();
  }, []);

  const filteredIcons = useMemo(() => {
    if (!iconSearch) return [];
    const query = iconSearch.toLowerCase();
    return allIcons.filter((ic) => ic.toLowerCase().includes(query));
  }, [iconSearch, allIcons]);

  // Auto-switch to inspector when an element gets selected
  useEffect(() => {
    if (selectedElementId || selectedEdge) {
      setActiveTab('inspector');
    }
  }, [selectedElementId, selectedEdge]);

  // Auto-switch tabs based on tour steps
  useEffect(() => {
    if (tourStep === 2) {
      setActiveTab('spawn');
    } else if (tourStep === 3) {
      setActiveTab('inspector');
    } else if (tourStep === 5) {
      setActiveTab('export');
    }
  }, [tourStep]);

  // Find selected node in flat elements
  const findElementRecursive = (elements: ElementSpec[], id: string): ElementSpec | null => {
    for (const el of elements) {
      if (el.id === id) return el;
      if (el.type === 'panel' && el.footer) {
        const footerId = el.footer.id || `${el.id}_footer`;
        if (footerId === id) {
          return {
            id: footerId,
            type: el.footer.type || 'card',
            title: el.footer.title || '',
            body: el.footer.body || '',
            icon: el.footer.icon,
            style: el.footer.style || {},
            _role: 'footer',
            parent: el.id,
          };
        }
      }
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

  const selectedConnectionIndex = useMemo(() => {
    if (!selectedEdge || !spec.connections) return -1;
    let matchIdx = spec.connections.findIndex(
      (c, idx) =>
        c.from === selectedEdge.from &&
        c.to === selectedEdge.to &&
        (selectedEdge.index !== undefined && selectedEdge.index >= 0 ? idx === selectedEdge.index : true)
    );
    if (matchIdx === -1) {
      matchIdx = spec.connections.findIndex(
        (c) => c.from === selectedEdge.from && c.to === selectedEdge.to
      );
    }
    return matchIdx;
  }, [selectedEdge, spec.connections]);

  const selectedConnection = selectedConnectionIndex >= 0 && spec.connections
    ? spec.connections[selectedConnectionIndex]
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
          if (el.type === 'panel' && el.footer) {
            const footerId = el.footer.id || `${el.id}_footer`;
            if (footerId === selectedElementId) {
              if (isStyle) {
                return {
                  ...el,
                  footer: {
                    ...el.footer,
                    style: {
                      ...(el.footer.style || {}),
                      [key]: value,
                    },
                  },
                };
              }
              return {
                ...el,
                footer: {
                  ...el.footer,
                  [key]: value,
                },
              };
            }
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
    if (!selectedEdge || selectedConnectionIndex < 0) return;

    onUpdateSpec((prev) => {
      const updatedConns = (prev.connections || []).map((conn, idx) => {
        if (idx === selectedConnectionIndex) {
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
            if (el.type === 'panel' && el.footer) {
              const footerId = el.footer.id || `${el.id}_footer`;
              if (footerId === selectedElementId) {
                const copy = { ...el };
                delete copy.footer;
                return copy;
              }
            }
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
    if (!selectedEdge || selectedConnectionIndex < 0) return;
    onUpdateSpec((prev) => {
      const cleanConns = (prev.connections || []).filter(
        (_, idx) => idx !== selectedConnectionIndex
      );
      return {
        ...prev,
        connections: cleanConns,
      };
    });
    onClearSelection();
    setConfirmDeleteEdge(false);
  };

  const updateCanvasProperty = (key: string, value: any) => {
    onUpdateSpec((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const updateCanvasConfig = (key: string, value: any) => {
    onUpdateSpec((prev) => ({
      ...prev,
      canvas: {
        ...(prev.canvas || { width: 1920, height: 1440 }),
        [key]: value,
      },
    }));
  };

  const updateTitleConfig = (key: string, value: any) => {
    onUpdateSpec((prev) => ({
      ...prev,
      title: {
        ...(prev.title || {}),
        [key]: value,
      },
    }));
  };

  const handleAddComponent = (template: typeof COMPONENT_TEMPLATES[0]) => {
    const slug = template.title.toLowerCase().replace(/\s+/g, '-');
    const newId = `${slug}-${Date.now().toString().slice(-4)}`;

    // 1. Calculate center flow coordinates
    const canvasElement = document.querySelector('.react-flow');
    const rect = canvasElement?.getBoundingClientRect() || {
      left: 0,
      top: 0,
      width: window.innerWidth,
      height: window.innerHeight,
    };
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const centerPos = screenToFlowPosition({ x: centerX, y: centerY });

    // 2. Avoid stacking directly on top of another node
    const isNear = (x1: number, y1: number, x2: number, y2: number) => {
      return Math.abs(x1 - x2) < 40 && Math.abs(y1 - y2) < 40;
    };

    const findVacantPosition = (currentPos: { x: number; y: number }): { x: number; y: number } => {
      let isOccupied = false;
      const rfNodes = getNodes();
      for (const node of rfNodes) {
        if (node.position && isNear(node.position.x, node.position.y, currentPos.x, currentPos.y)) {
          isOccupied = true;
          break;
        }
      }
      if (isOccupied) {
        return findVacantPosition({ x: currentPos.x + 50, y: currentPos.y + 50 });
      }
      return currentPos;
    };

    const finalPos = findVacantPosition(centerPos);
    
    const newElement: ElementSpec = {
      id: newId,
      type: template.type as any,
      title: template.title,
      icon: template.icon,
      x: finalPos.x,
      y: finalPos.y,
      style: {
        color: template.color,
        strokeColor: template.color,
        cornerRadius: 12,
        strokeWidth: 2,
      },
    };

    if (template.type === 'panel') {
      newElement.width = 320;
      newElement.height = 220;
      newElement.children = [];
    } else if (template.type === 'label') {
      newElement.style = {
        ...newElement.style,
        transparent: true,
        borderless: true,
      };
    } else if (template.type === 'input') {
      newElement.width = 220;
      newElement.height = 42;
      newElement.body = 'Active data node...';
    } else if (template.type === 'ellipse') {
      newElement.width = 160;
      newElement.height = 90;
      newElement.body = 'Active data node...';
    } else {
      newElement.body = 'Active data node...';
    }

    onUpdateSpec((prev) => ({
      ...prev,
      elements: [...prev.elements, newElement],
    }));
  };

  const handleTabShortcutClick = (tabId: 'spawn' | 'inspector' | 'canvas' | 'export') => {
    setActiveTab(tabId);
    if (isCollapsed && onToggleCollapse) {
      onToggleCollapse();
    }
  };

  if (isCollapsed) {
    return (
      <div className="w-full bg-surface-1 border-l border-border-themed flex flex-col items-center py-4 justify-between h-full flex-shrink-0 text-text-primary font-sans shadow-premium z-30 select-none">
        <div className="flex flex-col items-center gap-6 w-full">
          {/* Toggle sidebar button */}
          <button
            onClick={onToggleCollapse}
            className="p-2 bg-surface-2 hover:bg-surface-3 text-text-secondary hover:text-text-primary border border-border-themed rounded-lg transition focus-ring"
            title="Expand Properties Editor"
          >
            <ChevronLeft size={14} />
          </button>

          <div className="w-8 h-[1px] bg-border-themed" />

          {/* Shortcut icon for Spawn Components menu */}
          <button
            onClick={() => handleTabShortcutClick('spawn')}
            className={`p-2 border rounded-lg transition focus-ring ${
              activeTab === 'spawn'
                ? 'bg-accent-soft text-accent border-accent/20'
                : 'bg-surface-2 hover:bg-surface-3 text-text-secondary hover:text-text-primary border-border-themed'
            }`}
            title="Spawn Components"
          >
            <Plus size={14} />
          </button>

          {/* Shortcut icon for Properties Inspector */}
          <button
            onClick={() => handleTabShortcutClick('inspector')}
            className={`p-2 border rounded-lg transition focus-ring ${
              activeTab === 'inspector' || selectedElementId || selectedEdge
                ? 'bg-accent-soft text-accent border-accent/20'
                : 'bg-surface-2 hover:bg-surface-3 text-text-secondary hover:text-text-primary border-border-themed'
            }`}
            title="Inspect Properties"
          >
            <Sliders size={14} />
          </button>

          {/* Shortcut icon for Export Animator menu */}
          <button
            onClick={() => handleTabShortcutClick('export')}
            className={`p-2 border rounded-lg transition focus-ring ${
              activeTab === 'export'
                ? 'bg-accent-soft text-accent border-accent/20'
                : 'bg-surface-2 hover:bg-surface-3 text-text-secondary hover:text-text-primary border-border-themed'
            }`}
            title="Export Animator"
          >
            <Film size={14} />
          </button>
        </div>

        {/* Bottom canvas settings shortcut */}
        <button
          onClick={() => handleTabShortcutClick('canvas')}
          className={`p-2 border rounded-lg transition focus-ring ${
            activeTab === 'canvas'
              ? 'bg-accent-soft text-accent border-accent/20'
              : 'bg-surface-2 hover:bg-surface-3 text-text-secondary hover:text-text-primary border-border-themed'
          }`}
          title="Canvas Settings"
        >
          <Settings size={14} />
        </button>
      </div>
    );
  }

  const tabs = [
    { id: 'spawn', label: 'Components', icon: <Plus size={13} /> },
    { id: 'inspector', label: 'Properties', icon: <Sliders size={13} /> },
    { id: 'canvas', label: 'Canvas', icon: <Settings size={13} /> },
    { id: 'export', label: 'Export', icon: <Film size={13} /> },
  ] as const;

  return (
    <div className="w-full bg-surface-1 border-l border-border-themed flex flex-col h-full flex-shrink-0 text-text-primary font-sans shadow-premium select-none">
      {/* Tabs list */}
      <div className="flex border-b border-border-themed bg-surface-2/45 p-1 gap-1 flex-shrink-0">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex-grow flex items-center justify-center gap-1 py-2 rounded-lg text-[9px] font-extrabold uppercase tracking-wider transition focus-ring ${
              activeTab === t.id
                ? 'bg-surface-1 text-accent shadow-sm border border-border-themed/60'
                : 'text-text-muted hover:text-text-primary hover:bg-surface-2/60'
            }`}
          >
            {t.icon}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Tab body */}
      <div className="flex-grow overflow-y-auto custom-scrollbar p-5">
        {activeTab === 'spawn' && (
          <div className="flex flex-col gap-6 animate-fade-in">
            <div>
              <span className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-3">Spawn Component</span>
              <div className="flex flex-col gap-2">
                {COMPONENT_TEMPLATES.map((tmpl) => (
                  <button
                    key={tmpl.title}
                    onClick={() => handleAddComponent(tmpl)}
                    draggable={true}
                    onDragStart={(event) => {
                      event.dataTransfer.setData('application/reactflow-template', JSON.stringify(tmpl));
                      event.dataTransfer.effectAllowed = 'move';
                    }}
                    className="flex items-center gap-3 p-3 bg-surface-0 border border-border-themed hover:border-border-strong rounded-xl hover:bg-surface-2 transition text-left group focus-ring animate-fade-in cursor-grab active:cursor-grabbing"
                  >
                    <div
                      className="p-1.5 rounded-lg border flex items-center justify-center bg-accent-soft animate-fade-in"
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

        {activeTab === 'inspector' && (
          selectedNode ? (
            <div className="flex flex-col gap-6 animate-fade-in">
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
                <span className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Node ID</span>
                <span className="font-mono text-xs text-text-secondary bg-surface-0 px-3 py-2 rounded-lg border border-border-themed block select-all">
                  {selectedNode.id}
                </span>
              </div>

              {/* Title with character count */}
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label htmlFor="node-title-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider">Title</label>
                  <span className="text-[10px] text-text-muted font-mono">{(selectedNode.title || '').length}/40</span>
                </div>
                <input
                  id="node-title-input"
                  type="text"
                  maxLength={40}
                  value={selectedNode.title || ''}
                  onChange={(e) => updateNodeProperty('title', e.target.value)}
                  className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
                />
              </div>

              {/* Subtitle (Panel Nodes Only) with character count */}
              {selectedNode.type === 'panel' && (
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label htmlFor="node-subtitle-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider">Subtitle</label>
                    <span className="text-[10px] text-text-muted font-mono">{(selectedNode.subtitle || '').length}/50</span>
                  </div>
                  <input
                    id="node-subtitle-input"
                    type="text"
                    maxLength={50}
                    value={selectedNode.subtitle || ''}
                    onChange={(e) => updateNodeProperty('subtitle', e.target.value)}
                    className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
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
                    className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
                  />
                </div>
              )}

              {/* Sizing & Dimensions Sliders */}
              <div className="grid grid-cols-2 gap-3 border-t border-border-themed pt-3">
                <div>
                  <label className="block text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Width ({selectedNode.width || 180}px)</label>
                  <input
                    type="range"
                    min="100"
                    max="400"
                    step="10"
                    value={selectedNode.width || 180}
                    onChange={(e) => updateNodeProperty('width', parseInt(e.target.value))}
                    className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Height ({selectedNode.height || 120}px)</label>
                  <input
                    type="range"
                    min="60"
                    max="300"
                    step="10"
                    value={selectedNode.height || 120}
                    onChange={(e) => updateNodeProperty('height', parseInt(e.target.value))}
                    className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                  />
                </div>
              </div>

              {/* Corner Radius & Stroke Width Sliders */}
              <div className="grid grid-cols-2 gap-3 border-b border-border-themed pb-3">
                <div>
                  <label className="block text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Radius ({selectedNode.style?.cornerRadius ?? 12}px)</label>
                  <input
                    type="range"
                    min="0"
                    max="30"
                    step="2"
                    value={selectedNode.style?.cornerRadius ?? 12}
                    onChange={(e) => updateNodeProperty('cornerRadius', parseInt(e.target.value), true)}
                    className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Stroke ({selectedNode.style?.strokeWidth ?? 2}px)</label>
                  <input
                    type="range"
                    min="1"
                    max="8"
                    step="0.5"
                    value={selectedNode.style?.strokeWidth ?? 2}
                    onChange={(e) => updateNodeProperty('strokeWidth', parseFloat(e.target.value), true)}
                    className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                  />
                </div>
              </div>

              {/* Body Text with character count */}
              {selectedNode.type !== 'panel' && selectedNode.type !== 'label' && (
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label htmlFor="node-body-input" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider">Body Text</label>
                    <span className="text-[10px] text-text-muted font-mono">{(selectedNode.body || '').length}/200</span>
                  </div>
                  <textarea
                    id="node-body-input"
                    value={selectedNode.body || ''}
                    maxLength={200}
                    onChange={(e) => updateNodeProperty('body', e.target.value)}
                    className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent font-mono h-24 resize-none transition focus-ring"
                  />
                </div>
              )}

              <div>
                <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2.5">Accent Color</label>
                <div className="flex flex-wrap gap-2 bg-surface-0 p-2 rounded-lg border border-border-themed items-center">
                  {PRESET_COLORS.map((col) => (
                    <button
                      key={col.value}
                      aria-label={`Select ${col.name} accent color`}
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
                    />
                  ))}
                  {/* Custom color input picker */}
                  <div className="relative w-6 h-6 rounded-full border border-border-themed hover:border-border-strong hover:scale-110 transition flex items-center justify-center overflow-hidden cursor-pointer shadow-sm" title="Custom Accent Color">
                    <div className="w-full h-full rounded-full" style={{ backgroundColor: selectedNode.style?.color || '#3b82f6' }} />
                    <input
                      type="color"
                      value={selectedNode.style?.color || '#3b82f6'}
                      onChange={(e) => {
                        updateNodeProperty('color', e.target.value, true);
                        updateNodeProperty('strokeColor', e.target.value, true);
                      }}
                      className="absolute inset-0 w-[150%] h-[150%] -translate-x-[15%] -translate-y-[15%] cursor-pointer border-0 p-0 opacity-0"
                    />
                  </div>
                </div>
              </div>

              {/* Graphical Icon Selector */}
              {selectedNode.type !== 'panel' && selectedNode.type !== 'label' && (
                <div className="flex flex-col gap-2">
                  <span className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider">Node Icon</span>
                  
                  {/* Icon Search & Remove header */}
                  <div className="flex gap-2 items-center mb-1">
                    <button
                      onClick={() => updateNodeProperty('icon', null)}
                      className={`px-2.5 py-1.5 rounded-lg text-[10px] font-bold transition border focus-ring flex-shrink-0 ${
                        !selectedNode.icon
                          ? 'bg-accent-soft text-accent border-accent/20 shadow-sm'
                          : 'text-text-secondary bg-surface-2 border-transparent hover:bg-surface-3 hover:text-text-primary'
                      }`}
                    >
                      Remove Icon
                    </button>
                    
                    <div className="relative flex-grow">
                      <input
                        type="text"
                        placeholder="Search icons..."
                        value={iconSearch}
                        onChange={(e) => setIconSearch(e.target.value)}
                        className="w-full pl-7 pr-3 py-1 bg-surface-0 border border-border-themed rounded-lg text-[11px] text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
                      />
                      <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
                    </div>
                  </div>

                  {/* Icon Selector Grid list container */}
                  <div className="flex flex-col gap-3 bg-surface-0 border border-border-themed p-2 rounded-lg max-h-52 overflow-y-auto custom-scrollbar select-none">
                    {!iconSearch ? (
                      Object.entries(ICON_CATEGORIES).map(([categoryName, icons]) => (
                        <div key={categoryName} className="flex flex-col gap-1.5">
                          <span className="text-[9px] uppercase tracking-wider text-text-muted font-bold px-1">{categoryName}</span>
                          <div className="grid grid-cols-4 gap-2">
                            {icons.map((ic) => (
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
                        </div>
                      ))
                    ) : (
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[9px] uppercase tracking-wider text-text-muted font-bold px-1">Search Results</span>
                        <div className="grid grid-cols-4 gap-2">
                          {filteredIcons.map((ic) => (
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
                          {filteredIcons.length === 0 && (
                            <span className="col-span-4 text-center py-4 text-[10px] text-text-muted">No matching icons found</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Custom URL */}
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
                  className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
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
                  className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
                >
                  <option value="solid">Solid Path</option>
                  <option value="dashed">Dashed Path</option>
                  <option value="dotted">Dotted Path</option>
                </select>
              </div>

              {/* Connection color */}
              <div>
                <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2.5">Connection Line Color</label>
                <div className="flex flex-wrap gap-2 bg-surface-0 p-2 rounded-lg border border-border-themed items-center">
                  {PRESET_COLORS.map((col) => (
                    <button
                      key={col.value}
                      onClick={() => updateConnectionProperty('color', col.value)}
                      className={`w-6 h-6 rounded-full border transition flex items-center justify-center focus-ring ${
                        selectedConnection.color === col.value
                          ? 'border-accent dark:border-white scale-110 shadow-glow-blue'
                          : 'border-border-themed hover:border-border-strong hover:scale-105'
                      }`}
                      style={{ backgroundColor: col.value }}
                      title={col.name}
                      aria-label={`Line color ${col.name}`}
                    />
                  ))}
                  {/* Custom color input picker */}
                  <div className="relative w-6 h-6 rounded-full border border-border-themed hover:border-border-strong hover:scale-110 transition flex items-center justify-center overflow-hidden cursor-pointer shadow-sm" title="Custom Line Color">
                    <div className="w-full h-full rounded-full" style={{ backgroundColor: selectedConnection.color || '#3b82f6' }} />
                    <input
                      type="color"
                      value={selectedConnection.color || '#3b82f6'}
                      onChange={(e) => updateConnectionProperty('color', e.target.value)}
                      className="absolute inset-0 w-[150%] h-[150%] -translate-x-[15%] -translate-y-[15%] cursor-pointer border-0 p-0 opacity-0"
                    />
                  </div>
                </div>
              </div>

              {/* Animation Speed and Particle Count Sliders */}
              <div className="grid grid-cols-2 gap-3 border-t border-border-themed pt-3 mt-1">
                <div>
                  <label className="block text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Anim Speed ({(selectedConnection.animationSpeed ?? 1.0).toFixed(2)}x)</label>
                  <input
                    type="range"
                    min="0.25"
                    max="3.0"
                    step="0.25"
                    value={selectedConnection.animationSpeed ?? 1.0}
                    onChange={(e) => updateConnectionProperty('animationSpeed', parseFloat(e.target.value))}
                    className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Particles ({selectedConnection.particleCount ?? 3})</label>
                  <input
                    type="range"
                    min="0"
                    max="8"
                    step="1"
                    value={selectedConnection.particleCount ?? 3}
                    onChange={(e) => updateConnectionProperty('particleCount', parseInt(e.target.value))}
                    className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center text-text-muted animate-fade-in">
              <Sliders size={28} className="text-text-muted opacity-50 mb-3 animate-pulse" />
              <p className="text-xs">No component or connection selected.</p>
              <p className="text-[10px] text-text-muted mt-1 leading-relaxed px-4">
                Click any card node or line connector on the canvas to configure styling.
              </p>
            </div>
          )
        )}

        {activeTab === 'canvas' && (
          <div className="flex flex-col gap-6 animate-fade-in">
            <div className="pb-3 border-b border-border-themed">
              <span className="font-semibold text-[11px] uppercase tracking-wider text-text-muted">Canvas Parameters</span>
            </div>

            {/* Title Prefix */}
            <div>
              <label htmlFor="canvas-title-prefix" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Title Prefix</label>
              <input
                id="canvas-title-prefix"
                type="text"
                value={spec.title?.prefix || ''}
                onChange={(e) => updateTitleConfig('prefix', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
                placeholder="e.g. Architecture of the"
              />
            </div>

            {/* Title Highlight */}
            <div>
              <label htmlFor="canvas-title-highlight" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Title Highlight</label>
              <input
                id="canvas-title-highlight"
                type="text"
                value={spec.title?.highlight || ''}
                onChange={(e) => updateTitleConfig('highlight', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
                placeholder="e.g. Cognitive Memory Mesh"
              />
            </div>

            {/* Title Subtitle */}
            <div>
              <label htmlFor="canvas-title-subtitle" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Title Subtitle</label>
              <input
                id="canvas-title-subtitle"
                type="text"
                value={spec.title?.subtitle || ''}
                onChange={(e) => updateTitleConfig('subtitle', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
                placeholder="e.g. Multi-Agent State Synchronization"
              />
            </div>

            {/* Signature */}
            <div>
              <label htmlFor="canvas-signature" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Signature Logo</label>
              <input
                id="canvas-signature"
                type="text"
                value={spec.signature || ''}
                onChange={(e) => updateCanvasProperty('signature', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-mono font-bold"
                placeholder="e.g. @FlowDraft"
              />
            </div>

            {/* Width / Height dimensions */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="canvas-dim-width" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Canvas Width</label>
                <input
                  id="canvas-dim-width"
                  type="number"
                  min={500}
                  max={10000}
                  value={spec.canvas?.width ?? 1920}
                  onChange={(e) => updateCanvasConfig('width', parseInt(e.target.value) || 1920)}
                  className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-mono"
                />
              </div>
              <div>
                <label htmlFor="canvas-dim-height" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Canvas Height</label>
                <input
                  id="canvas-dim-height"
                  type="number"
                  min={500}
                  max={10000}
                  value={spec.canvas?.height ?? 1440}
                  onChange={(e) => updateCanvasConfig('height', parseInt(e.target.value) || 1440)}
                  className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-mono"
                />
              </div>
            </div>

            {/* FPS seek bar */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Frame Rate (FPS)</span>
                <span className="text-[11px] font-mono text-text-secondary font-bold">{spec.canvas?.fps ?? 30} FPS</span>
              </div>
              <input
                type="range"
                min="10"
                max="60"
                step="5"
                value={spec.canvas?.fps ?? 30}
                onChange={(e) => updateCanvasConfig('fps', parseInt(e.target.value))}
                className="w-full accent-indigo-600 bg-surface-3 h-1 rounded-lg focus-ring cursor-pointer"
              />
            </div>

            {/* Total frames */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Total Animation Frames</span>
                <span className="text-[11px] font-mono text-text-secondary font-bold">{spec.canvas?.frames ?? 90} frames</span>
              </div>
              <input
                type="range"
                min="30"
                max="300"
                step="10"
                value={spec.canvas?.frames ?? 90}
                onChange={(e) => updateCanvasConfig('frames', parseInt(e.target.value))}
                className="w-full accent-indigo-600 bg-surface-3 h-1 rounded-lg focus-ring cursor-pointer"
              />
            </div>

            {/* Theme Selector */}
            <div>
              <label htmlFor="canvas-theme-select" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Canvas Theme</label>
              <select
                id="canvas-theme-select"
                value={typeof spec.theme === 'string' ? spec.theme : 'dark'}
                onChange={(e) => onUpdateSpec((prev) => ({ ...prev, theme: e.target.value }))}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
              >
                <option value="dark">Sleek Obsidian (Dark)</option>
                <option value="light">Refined Slate (Light)</option>
                <option value="white">Minimalist Studio (White)</option>
              </select>
            </div>

            {/* Layout Direction Selector */}
            <div>
              <label htmlFor="canvas-layout-dir" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5 font-mono">Layout Flow Direction</label>
              <select
                id="canvas-layout-dir"
                value={spec.canvas?.layoutDirection || 'horizontal'}
                onChange={(e) => updateCanvasConfig('layoutDirection', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
              >
                <option value="vertical">Vertical Flow (Top to Bottom)</option>
                <option value="horizontal">Horizontal Flow (Left to Right)</option>
              </select>
            </div>

            {/* Layout Algorithm Selector */}
            <div>
              <label htmlFor="canvas-layout-alg" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5 font-mono">Layout Algorithm</label>
              <select
                id="canvas-layout-alg"
                value={spec.canvas?.layoutAlgorithm || 'layered'}
                onChange={(e) => updateCanvasConfig('layoutAlgorithm', e.target.value)}
                className="w-full px-3 py-2 bg-surface-0 border border-border-themed rounded-lg text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring font-medium"
              >
                <option value="layered">Layered (Hierarchical)</option>
                <option value="radial">Radial Layout</option>
                <option value="force">Force-Directed Layout</option>
              </select>
            </div>

            {/* Grid Pattern settings */}
            <div className="border-t border-border-themed pt-4 mt-1 flex flex-col gap-4">
              <span className="font-semibold text-[11px] uppercase tracking-wider text-text-muted">Grid Overlay Settings</span>
              
              {/* Pattern toggles */}
              <div>
                <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2">Grid Pattern</label>
                <div className="grid grid-cols-3 gap-1 bg-surface-2 p-0.5 rounded-lg border border-border-themed select-none">
                  {(['dots', 'lines', 'cross'] as const).map((variant) => (
                    <button
                      key={variant}
                      type="button"
                      onClick={() => updateCanvasConfig('gridVariant', variant)}
                      className={`py-1.5 rounded-md text-[10px] uppercase font-bold tracking-wider transition ${
                        (spec.canvas?.gridVariant || 'dots') === variant
                          ? 'bg-surface-1 text-accent shadow-sm'
                          : 'text-text-muted hover:text-text-primary'
                      }`}
                    >
                      {variant}
                    </button>
                  ))}
                </div>
              </div>

              {/* Grid Gap Spacing Slider */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Grid Spacing</span>
                  <span className="text-[11px] font-mono text-text-secondary font-bold">{spec.canvas?.gridGap ?? 20}px</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="60"
                  step="5"
                  value={spec.canvas?.gridGap ?? 20}
                  onChange={(e) => updateCanvasConfig('gridGap', parseInt(e.target.value))}
                  className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                />
              </div>

              {/* Grid Dot/Line Size Slider */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Grid Thickness</span>
                  <span className="text-[11px] font-mono text-text-secondary font-bold">{(spec.canvas?.gridSize ?? 1).toFixed(1)}px</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="4.0"
                  step="0.5"
                  value={spec.canvas?.gridSize ?? 1}
                  onChange={(e) => updateCanvasConfig('gridSize', parseFloat(e.target.value))}
                  className="w-full accent-accent bg-surface-2 h-1 rounded focus-ring cursor-pointer"
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'export' && (
          <div className="flex flex-col gap-6 animate-fade-in">
            <div className="pb-3 border-b border-border-themed">
              <span className="font-semibold text-[11px] uppercase tracking-wider text-text-muted font-mono flex items-center gap-1.5">
                <Film size={12} className="text-accent animate-pulse" /> Animated Video Renderer
              </span>
            </div>
            
            <ExportPanel
              token={token}
              spec={spec}
              activeDiagramId={activeDiagramId}
              onTriggerAuth={onTriggerAuth}
              onLogout={onLogout}
              isInline={true}
              tourStep={tourStep}
            />
          </div>
        )}
      </div>
    </div>
  );
};
