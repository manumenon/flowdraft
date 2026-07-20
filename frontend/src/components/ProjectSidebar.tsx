import React, { useState, useEffect } from 'react';
import { Plus, Save, Trash2, LogOut, Key, Loader2, FileCode, Compass } from 'lucide-react';
import type { FlowSpec } from '../types/spec';

interface ProjectSidebarProps {
  token: string | null;
  currentUser: string | null;
  spec: FlowSpec;
  theme: string;
  onSelectSpec: (spec: FlowSpec, theme: string, id?: string) => void;
  onTriggerAuth: () => void;
  onLogout: () => void;
  activeDiagramId: string | null;
  onSaveComplete: (id: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  onShowToast?: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
}

interface Diagram {
  id: string;
  title: string;
  description?: string;
  spec: any;
  theme: string;
}

export const ProjectSidebar: React.FC<ProjectSidebarProps> = ({
  token,
  currentUser,
  spec,
  theme,
  onSelectSpec,
  onTriggerAuth,
  onLogout,
  activeDiagramId,
  onSaveComplete,
  isCollapsed = false,
  onToggleCollapse,
  onShowToast,
}) => {
  const [diagrams, setDiagrams] = useState<Diagram[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [titleInput, setTitleInput] = useState('New Diagram');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const baseUrl = window.location.origin.includes(':3000')
    ? window.location.origin.replace(':3000', ':8000')
    : window.location.origin;

  const fetchDiagrams = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${baseUrl}/api/diagrams`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setDiagrams(data);
      } else {
        onShowToast?.('error', 'Fetch Blueprints Failed', 'API gateway returned error status: ' + res.status);
      }
    } catch (err) {
      console.error('Failed to fetch diagrams', err);
      onShowToast?.('warning', 'Database Unreachable', 'Backend service is offline. Using local sandbox.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchDiagrams();
    } else {
      setDiagrams([]);
    }
  }, [token]);

  const handleCreateDiagram = async () => {
    if (!token) {
      onTriggerAuth();
      return;
    }
    setSaving(true);
    try {
      const emptySpec: FlowSpec = {
        title: { prefix: 'NEW', highlight: titleInput, subtitle: 'Interactive Flowchart' },
        canvas: { mode: 'dynamic', width: 1200, height: 800 },
        elements: [
          { id: 'node_1', type: 'card', title: 'Start Node', body: 'Initialize structure' }
        ],
        connections: [],
        theme: theme,
      };

      const res = await fetch(`${baseUrl}/api/diagrams`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: titleInput,
          description: 'Created via FlowDraft Interface',
          spec: emptySpec,
          theme: theme,
        }),
      });

      if (res.ok) {
        const newDiag = await res.json();
        setDiagrams((prev) => [newDiag, ...prev]);
        onSelectSpec(newDiag.spec, newDiag.theme, newDiag.id);
        setTitleInput('New Diagram');
        onShowToast?.('success', 'Blueprint Created', 'Saved new spec to database.');
      } else {
        onShowToast?.('error', 'Creation Failed', 'Server rejected blueprint creation.');
      }
    } catch (err) {
      console.error('Error creating diagram', err);
      onShowToast?.('error', 'Creation Error', 'Unable to create diagram. Backend offline.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDiagram = async () => {
    if (!token) {
      onTriggerAuth();
      return;
    }
    if (!activeDiagramId) return;
    setSaving(true);
    try {
      const currentDiag = diagrams.find((d) => d.id === activeDiagramId);
      const updatedTitle = spec.title?.highlight || currentDiag?.title || 'Saved Diagram';

      const res = await fetch(`${baseUrl}/api/diagrams/${activeDiagramId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: updatedTitle,
          spec: spec,
          theme: theme,
        }),
      });

      if (res.ok) {
        const updated = await res.json();
        setDiagrams((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
        onSaveComplete(updated.id);
      } else {
        onShowToast?.('error', 'Save Failed', 'Server rejected saving changes.');
      }
    } catch (err) {
      console.error('Error saving diagram', err);
      onShowToast?.('error', 'Save Error', 'Connection failed. Could not write to database.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteDiagram = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;
    if (deleteConfirmId !== id) {
      setDeleteConfirmId(id);
      return;
    }
    try {
      const res = await fetch(`${baseUrl}/api/diagrams/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        setDiagrams((prev) => prev.filter((d) => d.id !== id));
        setDeleteConfirmId(null);
        onShowToast?.('info', 'Blueprint Deleted', 'Removed diagram blueprint successfully.');
        if (activeDiagramId === id) {
          onSelectSpec({
            title: { prefix: 'SYSTEM', highlight: 'FlowDraft', subtitle: 'Architecture Animator' },
            canvas: { mode: 'dynamic', width: 1200, height: 800 },
            elements: [],
            connections: [],
            theme: 'dark',
          }, 'dark');
        }
      } else {
        onShowToast?.('error', 'Delete Failed', 'Server rejected blueprint deletion.');
      }
    } catch (err) {
      console.error('Error deleting diagram', err);
      onShowToast?.('error', 'Deletion Error', 'Failed to communicate with database server.');
    }
  };

  const handleExportLocalJSON = () => {
    try {
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(spec, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `${spec.title?.highlight || 'flowdraft_diagram'}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      onShowToast?.('success', 'Export Complete', 'Downloaded diagram spec JSON file.');
    } catch (err) {
      console.error('Failed to export local JSON', err);
      onShowToast?.('error', 'Export Failed', 'Could not compile layout JSON.');
    }
  };

  const handleImportLocalJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (parsed.elements && Array.isArray(parsed.elements)) {
          onSelectSpec(parsed, parsed.theme || 'dark');
          onShowToast?.('success', 'Import Complete', 'Loaded diagram spec from local file.');
        } else {
          onShowToast?.('error', 'Invalid Format', 'Spec JSON is missing required elements array.');
        }
      } catch (err) {
        onShowToast?.('error', 'Import Failed', 'Invalid JSON syntax.');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const userInitials = currentUser ? currentUser.slice(0, 2).toUpperCase() : 'GS';

  if (isCollapsed) {
    return (
      <div className="w-full bg-surface-1 border-r border-border-themed flex flex-col items-center py-4 justify-between h-full flex-shrink-0 text-text-primary font-sans shadow-premium z-30">
        <div className="flex flex-col items-center gap-6 w-full">
          {/* Logo FD button to trigger toggle */}
          <button
            onClick={onToggleCollapse}
            className="w-8 h-8 rounded-lg flex items-center justify-center font-extrabold text-[11px] text-white shadow-glow-blue select-none bg-accent hover:opacity-90 transition focus-ring"
            title="Expand Sidebar Explorer"
          >
            FD
          </button>
          
          {/* User profile initials */}
          <div
            onClick={currentUser ? onLogout : onTriggerAuth}
            className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white shadow-glow-blue cursor-pointer select-none bg-accent hover:opacity-95 flex-shrink-0"
            title={currentUser ? `Sign Out (${currentUser})` : 'Sign In'}
          >
            {userInitials}
          </div>

          <div className="w-8 h-[1px] bg-border-themed" />

          {/* Create Empty Diagram Shortcut Button */}
          {token && (
            <button
              onClick={handleCreateDiagram}
              disabled={saving}
              className="p-2 bg-surface-2 hover:bg-surface-3 text-text-secondary hover:text-text-primary border border-border-themed rounded-lg transition focus-ring"
              title="Add New Spec Diagram"
            >
              <Plus size={14} />
            </button>
          )}

          {/* Compass view saved list toggle */}
          <button
            onClick={onToggleCollapse}
            className="p-2 bg-surface-2 hover:bg-surface-3 text-text-secondary hover:text-text-primary border border-border-themed rounded-lg transition focus-ring"
            title="Show Saved Blueprints list"
          >
            <Compass size={14} className={loading ? "animate-spin text-accent" : ""} />
          </button>
        </div>

        {/* Bottom signin state */}
        <div className="flex flex-col items-center">
          {currentUser ? (
            <button
              onClick={onLogout}
              className="p-2 text-text-muted hover:text-red-500 hover:bg-red-500/10 border border-border-themed hover:border-red-500/20 rounded-lg transition focus-ring"
              title="Sign Out"
            >
              <LogOut size={14} />
            </button>
          ) : (
            <button
              onClick={onTriggerAuth}
              className="p-2 bg-accent-soft hover:bg-accent text-accent hover:text-white border border-accent/20 rounded-lg transition focus-ring"
              title="Sign In"
            >
              <Key size={14} />
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-surface-1 border-r border-border-themed flex flex-col h-full flex-shrink-0 text-text-primary font-sans shadow-premium">
      {/* User Header Section */}
      <div className="p-4 border-b border-border-themed flex items-center justify-between bg-surface-2/55">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-glow-blue select-none animate-fade-in" style={{ backgroundColor: 'var(--accent)' }}>
            {userInitials}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-[11px] text-text-muted uppercase tracking-widest font-semibold font-mono">Workspace Status</span>
            <span className="text-xs font-bold text-text-primary truncate leading-tight">
              {currentUser ? currentUser : 'Guest Sandbox'}
            </span>
          </div>
        </div>

        {currentUser ? (
          <button
            onClick={onLogout}
            className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-2 border border-border-themed rounded-lg transition focus-ring"
            title="Sign Out"
            aria-label="Sign Out"
          >
            <LogOut size={14} />
          </button>
        ) : (
          <button
            onClick={onTriggerAuth}
            className="px-2.5 py-1.5 bg-accent hover:opacity-90 text-xs font-bold rounded-lg text-white flex items-center gap-1 transition shadow-lg focus-ring"
          >
            <Key size={11} /> SIGN IN
          </button>
        )}
      </div>

      {/* Action / Diagram Control Box */}
      {token && (
        <div className="p-4 border-b border-border-themed flex flex-col gap-3 bg-surface-2/20">
          <div className="relative">
            <input
              id="new-diagram-title-input"
              name="new-diagram-title-input"
              type="text"
              placeholder="New diagram title..."
              value={titleInput}
              onChange={(e) => setTitleInput(e.target.value)}
              className="w-full px-3 py-2 bg-surface-0 border border-border-themed focus:border-accent rounded-lg text-xs text-text-primary focus:outline-none transition font-medium focus-ring"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCreateDiagram}
              disabled={saving}
              className="flex-grow py-2 bg-accent hover:opacity-90 disabled:bg-accent/50 text-[10px] uppercase tracking-wider font-bold rounded-lg flex items-center justify-center gap-1.5 transition text-white focus-ring"
            >
              <Plus size={13} /> Add Spec
            </button>
            {activeDiagramId && (
              <button
                onClick={handleSaveDiagram}
                disabled={saving}
                className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-[10px] uppercase tracking-wider font-bold rounded-lg flex items-center justify-center gap-1.5 transition text-white focus-ring"
                title="Save Current Work"
              >
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save
              </button>
            )}
          </div>
        </div>
      )}

      {/* Saved Spec Explorer List */}
      <div className="flex-grow overflow-y-auto p-4 flex flex-col gap-3 custom-scrollbar">
        <div className="flex items-center justify-between px-1.5">
          <span className="text-[11px] text-text-muted uppercase tracking-widest font-semibold font-mono">Diagram Specifications</span>
          {diagrams.length > 0 && (
            <span className="text-[10px] bg-surface-3 border border-border-themed px-1.5 py-0.5 rounded font-bold text-text-secondary font-mono">
              {diagrams.length} total
            </span>
          )}
        </div>

        {loading ? (
          <div className="flex flex-col gap-2 py-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-[52px] rounded-xl border border-border-themed bg-surface-2/40 animate-pulse-slow" />
            ))}
          </div>
        ) : diagrams.length === 0 ? (
          <div className="text-center py-10 text-xs text-text-muted border border-dashed border-border-themed rounded-xl bg-surface-2/20 px-4 leading-relaxed flex flex-col items-center gap-2">
            <Compass className="text-text-muted w-8 h-8 animate-pulse" />
            <span>No saved architecture configurations. {token ? "Create a blueprint to get started." : "Login to store blueprints."}</span>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {diagrams.map((diag) => {
              const elementCount = diag.spec?.elements?.length || 0;
              const isSelected = activeDiagramId === diag.id;
              const isConfirming = deleteConfirmId === diag.id;
              
              return (
                <div
                  key={diag.id}
                  onClick={() => onSelectSpec(diag.spec, diag.theme, diag.id)}
                  className={`p-3 rounded-xl border transition cursor-pointer flex items-center justify-between group relative overflow-hidden ${
                    isSelected
                      ? 'bg-accent/10 border-accent/30 text-accent'
                      : 'bg-surface-1 border-border-themed hover:bg-surface-2 hover:border-border-strong text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {/* Accent bar indicating active item */}
                  {isSelected && (
                    <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-accent shadow-glow-blue" />
                  )}

                  <div className="flex items-center gap-2.5 min-w-0">
                    <FileCode size={15} className={isSelected ? 'text-accent animate-pulse' : 'text-text-muted'} />
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-bold truncate leading-snug">{diag.title}</span>
                      <div className="flex items-center gap-1.5 mt-0.5 text-[11px] text-text-muted font-mono">
                        <span className="uppercase">{diag.theme} theme</span>
                        <span>•</span>
                        <span>{elementCount} nodes</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    {isConfirming ? (
                      <div className="flex items-center gap-1 z-10">
                        <button
                          onClick={(e) => handleDeleteDiagram(diag.id, e)}
                          className="px-1.5 py-0.5 bg-red-600 text-white rounded text-[10px] font-bold uppercase tracking-wider hover:bg-red-500"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirmId(null);
                          }}
                          className="px-1.5 py-0.5 bg-surface-3 text-text-primary rounded text-[10px] font-bold uppercase tracking-wider hover:bg-surface-2"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={(e) => handleDeleteDiagram(diag.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 bg-surface-2 hover:bg-red-600/15 text-text-muted hover:text-red-500 dark:hover:text-red-400 rounded-md border border-border-themed hover:border-red-500/35 transition focus-ring"
                        title="Delete Specification Blueprint"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Local Files Import/Export fallback tool container */}
      <div className="p-4 border-t border-border-themed bg-surface-2/20 flex flex-col gap-2 flex-shrink-0">
        <span className="text-[10px] font-extrabold tracking-widest text-text-muted uppercase font-mono">Local File Backup</span>
        <div className="flex gap-2">
          <button
            onClick={handleExportLocalJSON}
            className="flex-grow py-1.5 bg-surface-2 hover:bg-surface-3 border border-border-themed hover:border-border-strong text-[10px] uppercase font-bold tracking-wider rounded-lg flex items-center justify-center gap-1 text-text-secondary hover:text-text-primary focus-ring transition duration-200"
            title="Download diagram as .json file locally"
          >
            Export Spec
          </button>
          
          <label className="flex-grow py-1.5 bg-surface-2 hover:bg-surface-3 border border-border-themed hover:border-border-strong text-[10px] uppercase font-bold tracking-wider rounded-lg flex items-center justify-center gap-1 text-text-secondary hover:text-text-primary cursor-pointer text-center select-none focus-ring transition duration-200">
            Import Spec
            <input
              id="import-spec-file"
              name="import-spec-file"
              type="file"
              accept=".json"
              onChange={handleImportLocalJSON}
              className="hidden"
            />
          </label>
        </div>
      </div>
    </div>
  );
};

