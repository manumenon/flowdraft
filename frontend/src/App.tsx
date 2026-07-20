import { useState, useEffect } from 'react';
import { Canvas } from './components/Canvas';
import { defaultSpec } from './assets/defaultSpec';
import { useClockHook } from './hooks/useClockHook';
import { useUndoRedo } from './hooks/useUndoRedo';
import type { FlowSpec, ElementSpec } from './types/spec';
import { FileJson, Sun, Moon, Check, AlertCircle, HelpCircle, X, PanelLeftClose, PanelLeft, PanelRightClose, PanelRight, Command } from 'lucide-react';
import { AuthModal } from './components/AuthModal';
import { ProjectSidebar } from './components/ProjectSidebar';
import { PropertyEditor } from './components/PropertyEditor';
import { Toast } from './components/Toast';
import type { ToastMessage } from './components/Toast';
import { CommandPalette } from './components/CommandPalette';

function parseSpecFromQuery(): FlowSpec | null {
  const params = new URLSearchParams(window.location.search);
  const specStr = params.get('spec');
  if (!specStr) return null;
  try {
    const decoded = atob(specStr);
    return JSON.parse(decoded);
  } catch {
    try {
      return JSON.parse(decodeURIComponent(specStr));
    } catch (err) {
      console.error('Failed to parse spec from query parameter', err);
      return null;
    }
  }
}

function App() {
  const pathname = window.location.pathname;
  const isRenderBox = pathname.startsWith('/render-box');

  // Activate clock hook in render-box mode for Playwright automation
  useClockHook(isRenderBox);

  // 1. Determine initial spec & history
  const [spec] = useState<FlowSpec>(() => {
    const querySpec = parseSpecFromQuery();
    return querySpec || defaultSpec;
  });

  const { state: currentSpec, setState: setSpecState, undo, redo, resetHistory } = useUndoRedo(spec);

  // 2. Determine initial theme
  const [theme, setTheme] = useState<string>(() => {
    const params = new URLSearchParams(window.location.search);
    const queryTheme = params.get('theme');
    if (queryTheme) return queryTheme;
    
    if (currentSpec.theme && typeof currentSpec.theme === 'string') {
      return currentSpec.theme;
    }
    return 'dark';
  });

  const [jsonInput, setJsonInput] = useState(() => JSON.stringify(currentSpec, null, 2));
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // State for Authentication and Sidebars
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('flowdraft_token'));
  const [currentUser, setCurrentUser] = useState<string | null>(() => localStorage.getItem('flowdraft_user_email'));
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<{ from: string; to: string; index: number } | null>(null);
  const [activeDiagramId, setActiveDiagramId] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  const [leftSidebarCollapsed, setLeftSidebarCollapsed] = useState(false);
  const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(false);  // Premium Toast System
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const showToast = (type: ToastMessage['type'], title: string, message: string) => {
    setToasts((prev) => [...prev, { id: `${Date.now()}-${Math.random()}`, type, title, message }]);
  };
  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Premium Command Palette trigger
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [snapToGrid, setSnapToGrid] = useState(false);
  
  // Premium Onboarding Tour state
  const [tourStep, setTourStep] = useState<number | null>(() => {
    const isFirstTime = !localStorage.getItem('flowdraft_onboarded_v2');
    return isFirstTime ? 1 : null;
  });

  const [isLoadingSpec, setIsLoadingSpec] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return !!params.get('job_id');
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const jobId = params.get('job_id');
    if (!jobId) return;

    const fetchSpec = async () => {
      try {
        const backendBaseUrl = window.location.origin.includes(':3000')
          ? window.location.origin.replace(':3000', ':8000')
          : window.location.origin;

        const res = await fetch(`${backendBaseUrl}/api/v1/export/${jobId}/spec`);
        if (res.ok) {
          const data = await res.json();
          resetHistory(data);
          setJsonInput(JSON.stringify(data, null, 2));
        } else {
          console.error('Failed to load spec for job_id: ' + jobId);
        }
      } catch (err) {
        console.error('Error fetching job spec', err);
      } finally {
        setIsLoadingSpec(false);
      }
    };

    fetchSpec();
  }, [resetHistory]);

  // Keep jsonInput updated when spec changes
  useEffect(() => {
    setJsonInput(JSON.stringify(currentSpec, null, 2));
  }, [currentSpec]);

  // Watch for theme in spec if it changes
  useEffect(() => {
    if (currentSpec.theme && typeof currentSpec.theme === 'string') {
      setTheme(currentSpec.theme);
    }
  }, [currentSpec]);

  // Auto-collapse sidebars under 1280px viewport width
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1280) {
        setLeftSidebarCollapsed(true);
        setRightSidebarCollapsed(true);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Auto-expand sidebars during interactive onboarding tour steps
  useEffect(() => {
    if (tourStep === 1) {
      setLeftSidebarCollapsed(false);
    } else if (tourStep === 2 || tourStep === 3) {
      setRightSidebarCollapsed(false);
    }
  }, [tourStep]);

  // Keyboard shortcut listener for Ctrl+K, Undo/Redo, Delete/Backspace, Escape, and Arrow nudging
  useEffect(() => {
    const handleGlobalShortcuts = (e: KeyboardEvent) => {
      // 1. Ctrl+K (Command Palette)
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setShowCommandPalette((prev) => !prev);
        return;
      }

      // Ignore shortcuts if focusing an input/textarea
      const activeEl = document.activeElement;
      const isInput = activeEl && (
        activeEl.tagName === 'INPUT' || 
        activeEl.tagName === 'TEXTAREA' || 
        activeEl.getAttribute('contenteditable') === 'true'
      );
      if (isInput) return;

      // 2. Undo/Redo
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        if (e.shiftKey) {
          redo();
          showToast('info', 'Redo', 'Redid last action');
        } else {
          undo();
          showToast('info', 'Undo', 'Undid last action');
        }
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
        e.preventDefault();
        redo();
        showToast('info', 'Redo', 'Redid last action');
        return;
      }

      // 3. Escape key (Deselect)
      if (e.key === 'Escape') {
        setSelectedElementId(null);
        setSelectedEdge(null);
        return;
      }

      // 4. Delete / Backspace key
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedElementId) {
          e.preventDefault();
          setSpecState((prev) => {
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
          setSelectedElementId(null);
          showToast('info', 'Component Removed', 'Deleted selected component card.');
        } else if (selectedEdge) {
          e.preventDefault();
          setSpecState((prev) => {
            const cleanConns = (prev.connections || []).filter(
              (conn, idx) => !(conn.from === selectedEdge.from && conn.to === selectedEdge.to && idx === selectedEdge.index)
            );
            return {
              ...prev,
              connections: cleanConns,
            };
          });
          setSelectedEdge(null);
          showToast('info', 'Connection Removed', 'Deleted selected connection line.');
        }
        return;
      }

      // 5. Arrow Key Nudging
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key) && selectedElementId) {
        e.preventDefault();
        const step = e.shiftKey ? 40 : 10;
        let dx = 0;
        let dy = 0;
        if (e.key === 'ArrowUp') dy = -step;
        if (e.key === 'ArrowDown') dy = step;
        if (e.key === 'ArrowLeft') dx = -step;
        if (e.key === 'ArrowRight') dx = step;

        setSpecState((prev) => {
          const updateRecursive = (elements: ElementSpec[]): ElementSpec[] => {
            return elements.map((el) => {
              if (el.id === selectedElementId) {
                return {
                  ...el,
                  x: (el.x || 0) + dx,
                  y: (el.y || 0) + dy,
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
      }
    };
    window.addEventListener('keydown', handleGlobalShortcuts);
    return () => window.removeEventListener('keydown', handleGlobalShortcuts);
  }, [selectedElementId, selectedEdge, undo, redo, setSpecState]);

  const handleApplySpec = () => {
    try {
      const parsed = JSON.parse(jsonInput);
      if (!parsed.elements || !Array.isArray(parsed.elements)) {
        throw new Error("Invalid Spec: 'elements' must be a valid list.");
      }
      setSpecState(parsed);
      setValidationError(null);
      setIsSidebarOpen(false);
      showToast('success', 'Spec Loaded', 'Diagram specification applied successfully!');
    } catch (err: any) {
      setValidationError(err.message || 'Invalid JSON format');
      showToast('error', 'Spec Parsing Failed', err.message || 'Check syntax or JSON structure.');
    }
  };

  const handleAuthSuccess = (newToken: string, email: string) => {
    setToken(newToken);
    setCurrentUser(email);
    localStorage.setItem('flowdraft_token', newToken);
    localStorage.setItem('flowdraft_user_email', email);
    setShowAuthModal(false);
    showToast('success', 'Sign In Success', `Welcome back, ${email}!`);
  };

  // Sync theme with HTML root class for tailwind/light mode consistency
  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove('dark', 'white-theme');
    if (theme === 'white') {
      root.classList.add('white-theme');
      root.style.colorScheme = 'light';
    } else if (theme === 'light') {
      root.style.colorScheme = 'light';
    } else {
      root.classList.add('dark');
      root.style.colorScheme = 'dark';
    }
  }, [theme]);

  const handleLogout = () => {
    setToken(null);
    setCurrentUser(null);
    setActiveDiagramId(null);
    localStorage.removeItem('flowdraft_token');
    localStorage.removeItem('flowdraft_user_email');
    showToast('info', 'Signed Out', 'You have been signed out of Guest Space.');
  };

  const handleSelectDiagramSpec = (loadedSpec: FlowSpec, loadedTheme: string, id?: string) => {
    resetHistory(loadedSpec);
    setTheme(loadedTheme);
    if (id) {
      setActiveDiagramId(id);
    } else {
      setActiveDiagramId(null);
    }
    setSelectedElementId(null);
    setSelectedEdge(null);
    showToast('success', 'Diagram Opened', `Successfully opened diagram spec.`);
  };

  const handleNodeDragStop = (id: string, x: number, y: number, allNodes?: any[]) => {
    const snapValue = 20;
    const finalX = snapToGrid ? Math.round(x / snapValue) * snapValue : x;
    const finalY = snapToGrid ? Math.round(y / snapValue) * snapValue : y;

    setSpecState((prev) => {
      const updateRecursive = (elements: ElementSpec[]): ElementSpec[] => {
        return elements.map((el) => {
          let newX = el.x;
          let newY = el.y;
          let newWidth = el.width;
          let newHeight = el.height;

          if (el.id === id) {
            newX = finalX;
            newY = finalY;
          } else if (allNodes) {
            const match = allNodes.find((n) => n.id === el.id);
            if (match) {
              newX = snapToGrid ? Math.round(match.position.x / snapValue) * snapValue : match.position.x;
              newY = snapToGrid ? Math.round(match.position.y / snapValue) * snapValue : match.position.y;
              if (match.width) newWidth = match.width;
              if (match.height) newHeight = match.height;
            }
          }

          if (el.id === id && allNodes) {
            const match = allNodes.find((n) => n.id === el.id);
            if (match) {
              if (match.width) newWidth = match.width;
              if (match.height) newHeight = match.height;
            }
          }

          if (el.children) {
            return {
              ...el,
              x: newX,
              y: newY,
              width: newWidth,
              height: newHeight,
              children: updateRecursive(el.children),
            };
          }

          return {
            ...el,
            x: newX,
            y: newY,
            width: newWidth,
            height: newHeight,
          };
        });
      };

      const newCanvas = {
        ...(prev.canvas || { width: 1920, height: 1440 }),
        mode: 'absolute' as const,
      };

      return {
        ...prev,
        canvas: newCanvas,
        elements: updateRecursive(prev.elements),
      };
    });
  };

  const handleConnect = (from: string, to: string, exitPort: string, entryPort: string) => {
    setSpecState((prev) => {
      const newConnection = {
        from,
        to,
        exitPort: exitPort as any,
        entryPort: entryPort as any,
        style: 'solid' as const,
      };
      return {
        ...prev,
        connections: [...(prev.connections || []), newConnection],
      };
    });
    showToast('success', 'Connection Drawn', `Linked ${from} to ${to}`);
  };

  const handleDropTemplate = (template: any, x: number, y: number) => {
    const slug = template.title.toLowerCase().replace(/\s+/g, '-');
    const newId = `${slug}-${Date.now().toString().slice(-4)}`;

    const newElement: ElementSpec = {
      id: newId,
      type: template.type as any,
      title: template.title,
      body: 'Active data node...',
      icon: template.icon,
      x,
      y,
      style: {
        color: template.color,
        strokeColor: template.color,
        cornerRadius: 12,
        strokeWidth: 2,
      },
    };

    setSpecState((prev) => ({
      ...prev,
      elements: [...prev.elements, newElement],
    }));
    showToast('success', 'Component Added', `Dropped ${template.title} on canvas`);
  };

  const handleClearSelection = () => {
    setSelectedElementId(null);
    setSelectedEdge(null);
  };

  // Commands available in Ctrl+K Palette
  const commandPaletteActions = [
    {
      id: 'auto-layout',
      title: 'Auto Layout Elements',
      category: 'Canvas Operations',
      shortcut: 'Auto',
      icon: <Check size={14} />,
      action: () => {
        const layoutBtn = document.querySelector('[data-layout-btn]') as HTMLButtonElement;
        if (layoutBtn) layoutBtn.click();
        else showToast('info', 'Auto Layout', 'Calculated layout bounds.');
      }
    },
    {
      id: 'theme-dark',
      title: 'Switch to Dark Theme',
      category: 'UI Theme',
      shortcut: 'Dark',
      icon: <Moon size={14} />,
      action: () => setTheme('dark')
    },
    {
      id: 'theme-light',
      title: 'Switch to Light Theme',
      category: 'UI Theme',
      shortcut: 'Light',
      icon: <Sun size={14} />,
      action: () => setTheme('light')
    },
    {
      id: 'toggle-left',
      title: 'Toggle Left Sidebar Explorer',
      category: 'Workspace Shell',
      icon: <PanelLeft size={14} />,
      action: () => setLeftSidebarCollapsed((prev) => !prev)
    },
    {
      id: 'toggle-right',
      title: 'Toggle Right Property Panel',
      category: 'Workspace Shell',
      icon: <PanelRight size={14} />,
      action: () => setRightSidebarCollapsed((prev) => !prev)
    },
    {
      id: 'help-manual',
      title: 'Open Help Manual Modal',
      category: 'Documentation',
      icon: <HelpCircle size={14} />,
      action: () => setShowHelp(true)
    }
  ];

  // Pure Render Mode (Viewer only, no grid, no handles, no controls)
  if (isRenderBox) {
    if (isLoadingSpec) {
      const bgColor = theme === 'dark' ? '#0f172a' : '#ffffff';
      const textColor = theme === 'dark' ? '#94a3b8' : '#475569';
      return (
        <div className="w-screen h-screen overflow-hidden flex items-center justify-center font-sans text-xs" style={{ backgroundColor: bgColor, color: textColor }}>
          Loading diagram spec...
        </div>
      );
    }
    const bgColor = theme === 'dark' ? '#0f172a' : '#ffffff';
    return (
      <div className="w-screen h-screen overflow-hidden relative" style={{ backgroundColor: bgColor }}>
        <Canvas spec={currentSpec} theme={theme} isPureRender={true} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen w-screen bg-surface-0 text-text-primary overflow-hidden font-sans">
      {/* Docked Header */}
      <header className="h-14 bg-surface-1 border-b border-border-themed px-4 flex items-center justify-between z-40 shadow-sm flex-shrink-0">
        <div className="flex items-center gap-3">
          {/* Sidebar toggle buttons */}
          <button
            onClick={() => setLeftSidebarCollapsed((prev) => !prev)}
            className={`p-1.5 hover:bg-surface-2 text-text-muted hover:text-text-primary rounded-lg transition focus-ring ${
              !leftSidebarCollapsed ? 'bg-surface-2 text-accent' : ''
            }`}
            title={leftSidebarCollapsed ? "Open Explorer" : "Collapse Explorer"}
            aria-label={leftSidebarCollapsed ? "Open Explorer" : "Collapse Explorer"}
          >
            {leftSidebarCollapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
          </button>

          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg flex items-center justify-center font-extrabold text-xs text-white shadow-glow-blue select-none" style={{ backgroundColor: 'var(--accent)' }}>
              FD
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold tracking-wide text-xs text-text-primary uppercase">FlowDraft</span>
              <span className="text-[10px] bg-surface-3 border border-border-themed text-text-secondary px-1.5 py-0.5 rounded-md uppercase font-mono font-medium">
                Editor
              </span>
            </div>
          </div>

          {/* Context Breadcrumbs */}
          <div className="hidden md:flex items-center gap-1.5 text-[11px] text-text-muted font-medium ml-4">
            <span>diagrams</span>
            <span>/</span>
            <span className="text-text-secondary truncate max-w-[120px] font-mono">{activeDiagramId || 'unsaved-sandbox'}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Command Palette Indicator */}
          <button
            onClick={() => setShowCommandPalette(true)}
            className="hidden lg:flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary bg-surface-2 border border-border-themed px-2.5 py-1.5 rounded-lg transition focus-ring"
            aria-label="Open Command Palette"
          >
            <Command size={11} />
            <span>Search Actions</span>
            <span className="text-[10px] text-text-muted bg-surface-3 border border-border-themed px-1 py-0.5 rounded font-mono">Ctrl+K</span>
          </button>

          {/* Pill-shaped segmented theme controller */}
          <div className="flex items-center bg-surface-3 border border-border-themed rounded-lg p-0.5 relative">
            <button
              onClick={() => setTheme('dark')}
              className={`p-1.5 rounded-md transition text-xs flex items-center gap-1 ${theme === 'dark' ? 'bg-surface-1 text-accent font-semibold shadow-sm' : 'text-text-muted hover:text-text-primary'}`}
              title="Dark Theme"
              aria-label="Switch to Dark Theme"
            >
              <Moon size={13} />
            </button>
            <button
              onClick={() => setTheme('light')}
              className={`p-1.5 rounded-md transition text-xs flex items-center gap-1 ${theme === 'light' ? 'bg-surface-1 text-accent font-semibold shadow-sm' : 'text-text-muted hover:text-text-primary'}`}
              title="Light Theme"
              aria-label="Switch to Light Theme"
            >
              <Sun size={13} />
            </button>
            <button
              onClick={() => setTheme('white')}
              className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase transition ${theme === 'white' ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-muted hover:text-text-primary'}`}
              title="White Contrast Theme"
              aria-label="Switch to White Contrast Theme"
            >
              White
            </button>
          </div>

          {/* Help Manual Button */}
          <button
            onClick={() => setShowHelp(true)}
            className="p-1.5 hover:bg-surface-2 text-text-muted hover:text-text-primary rounded-lg transition focus-ring"
            title="Help Workspace Manual"
            aria-label="Help Workspace Manual"
          >
            <HelpCircle size={16} />
          </button>

          <button
            onClick={() => setIsSidebarOpen(true)}
            className="px-3 py-1.5 bg-surface-2 hover:bg-surface-3 text-text-primary text-xs font-semibold rounded-lg border border-border-themed transition flex items-center gap-1.5 focus-ring"
          >
            <FileJson size={13} />
            Import Spec
          </button>

          <button
            onClick={() => setRightSidebarCollapsed((prev) => !prev)}
            className={`p-1.5 hover:bg-surface-2 text-text-muted hover:text-text-primary rounded-lg transition focus-ring ${
              !rightSidebarCollapsed ? 'bg-surface-2 text-accent' : ''
            }`}
            title={rightSidebarCollapsed ? "Open Properties" : "Collapse Properties"}
            aria-label={rightSidebarCollapsed ? "Open Properties" : "Collapse Properties"}
          >
            {rightSidebarCollapsed ? <PanelRight size={16} /> : <PanelRightClose size={16} />}
          </button>
        </div>
      </header>

      {/* Main Workspace container */}
      <div className="flex flex-1 w-full min-h-0 relative z-10 overflow-hidden">
        {/* Docked Left Sidebar */}
        <div
          id="tour-explorer"
          className={`h-full flex flex-col flex-shrink-0 z-30 transition-all duration-300 relative overflow-hidden ${
            leftSidebarCollapsed ? 'w-14' : 'w-80'
          } ${
            tourStep === 1 ? 'ring-4 ring-indigo-500 shadow-glow-indigo z-40' : ''
          }`}
        >
          <ProjectSidebar
            token={token}
            currentUser={currentUser}
            spec={currentSpec}
            theme={theme}
            onSelectSpec={handleSelectDiagramSpec}
            onTriggerAuth={() => setShowAuthModal(true)}
            onLogout={handleLogout}
            activeDiagramId={activeDiagramId}
            onSaveComplete={() => {
              showToast('success', 'Work Saved', 'Diagram changes written to database successfully.');
            }}
            isCollapsed={leftSidebarCollapsed}
            onToggleCollapse={() => setLeftSidebarCollapsed(!leftSidebarCollapsed)}
            onShowToast={showToast}
          />
        </div>

        {/* Workspace Canvas (Full Bleed Background in the center flex area) */}
        <div className="flex-grow h-full min-w-0 relative z-10">
          <Canvas
            spec={currentSpec}
            theme={theme}
            isPureRender={false}
            onNodeSelect={setSelectedElementId}
            onEdgeSelect={(from, to, index) => {
              if (from === '' && to === '' && index === -1) {
                setSelectedEdge(null);
              } else {
                setSelectedEdge({ from, to, index });
              }
            }}
            onNodeDragStop={handleNodeDragStop}
            onConnect={handleConnect}
            onDropTemplate={handleDropTemplate}
            snapToGrid={snapToGrid}
            onToggleSnap={() => setSnapToGrid(!snapToGrid)}
            tourStep={tourStep}
          />
        </div>

        {/* Docked Right Sidebar */}
        <div
          id="tour-properties"
          className={`h-full flex flex-col flex-shrink-0 z-30 transition-all duration-300 relative overflow-hidden ${
            rightSidebarCollapsed ? 'w-14' : 'w-80'
          } ${
            (tourStep === 2 || tourStep === 3) ? 'ring-4 ring-indigo-500 shadow-glow-indigo z-40' : ''
          }`}
        >
          <PropertyEditor
            spec={currentSpec}
            selectedElementId={selectedElementId}
            selectedEdge={selectedEdge}
            onUpdateSpec={(updater) => setSpecState((prev) => updater(prev))}
            onClearSelection={handleClearSelection}
            isCollapsed={rightSidebarCollapsed}
            onToggleCollapse={() => setRightSidebarCollapsed(!rightSidebarCollapsed)}
            token={token}
            activeDiagramId={activeDiagramId}
            onTriggerAuth={() => setShowAuthModal(true)}
            tourStep={tourStep}
          />
        </div>
      </div>

      {/* Floating JSON Import Overlay Sidebar */}
      {isSidebarOpen && (
        <>
          {/* Backdrop Overlay */}
          <div
            className="fixed inset-0 bg-surface-0/60 backdrop-blur-sm z-[45] cursor-pointer animate-fade-in"
            onClick={() => setIsSidebarOpen(false)}
          />
          {/* Sidebar Panel */}
          <div className="fixed left-4 top-[76px] bottom-4 w-96 bg-surface-1/95 border border-border-themed rounded-2xl flex flex-col z-50 animate-slide-in-left shadow-2xl backdrop-blur-md">
            <div className="p-4 border-b border-border-themed flex items-center justify-between">
              <span className="font-semibold flex items-center gap-2 text-[11px] uppercase tracking-wider text-text-muted">
                <FileJson size={18} className="text-accent" /> Import Spec JSON
              </span>
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="text-xs px-2.5 py-1 bg-surface-2 hover:bg-surface-3 rounded transition text-text-secondary focus-ring"
              >
                Close
              </button>
            </div>

            <div className="p-4 flex-grow flex flex-col gap-3 min-h-0">
              <textarea
                value={jsonInput}
                onChange={(e) => setJsonInput(e.target.value)}
                placeholder="Paste spec JSON here..."
                className="w-full flex-grow p-3 bg-surface-0 border border-border-themed rounded font-mono text-xs text-emerald-600 dark:text-emerald-400 focus:outline-none focus:border-border-strong resize-none min-h-0 focus-ring"
              />
              {validationError && (
                <div className="p-3 bg-red-50/40 dark:bg-red-950/40 border border-red-200 dark:border-red-800/80 rounded flex gap-2 items-start text-xs text-red-600 dark:text-red-300">
                  <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                  <span>{validationError}</span>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-border-themed">
              <button
                onClick={handleApplySpec}
                className="w-full py-2 bg-accent hover:opacity-90 font-semibold rounded text-sm transition flex items-center justify-center gap-1.5 text-white shadow-md focus-ring"
              >
                <Check size={16} /> Apply Spec
              </button>
            </div>
          </div>
        </>
      )}

      {/* Authentication Modal */}
      {showAuthModal && (
        <AuthModal
          onClose={() => setShowAuthModal(false)}
          onSuccess={handleAuthSuccess}
        />
      )}

      {/* Command Palette search dialog */}
      {showCommandPalette && (
        <CommandPalette
          onClose={() => setShowCommandPalette(false)}
          actions={commandPaletteActions}
        />
      )}

      {/* Toast notifications */}
      <Toast toasts={toasts} onDismiss={dismissToast} />

      {/* User Workspace Manual Modal */}
      {showHelp && (
        <div className="fixed inset-0 bg-surface-0/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-md bg-surface-1 border border-border-themed rounded-xl shadow-2xl overflow-hidden backdrop-blur-md flex flex-col relative animate-zoom-in p-6">
            <button
              onClick={() => setShowHelp(false)}
              className="absolute top-4 right-4 p-1 text-text-muted hover:text-text-primary rounded-lg hover:bg-surface-2 transition focus-ring"
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>
            <h2 className="text-base font-bold uppercase tracking-wider text-text-primary mb-4 flex items-center gap-2">
              <HelpCircle className="text-accent" size={18} /> FlowDraft Workspace Manual
            </h2>
            <div className="space-y-4 text-xs text-text-secondary overflow-y-auto max-h-96 pr-1 custom-scrollbar">
              <div>
                <h3 className="font-bold text-text-primary mb-0.5">1. Creating Components</h3>
                <p>Use the <strong>Spawn Component</strong> templates panel in the right properties editor sidebar (visible when no node is selected) to spawn templates onto the viewport canvas.</p>
              </div>
              <div>
                <h3 className="font-bold text-text-primary mb-0.5">2. Repositioning Nodes</h3>
                <p>Drag component nodes to manually re-arrange layout structures. ReactFlow automatically toggles coordinates to absolute positioning mode.</p>
              </div>
              <div>
                <h3 className="font-bold text-text-primary mb-0.5">3. Drawing Connections</h3>
                <p>Hover over edge limits to display interactive dot ports. Click and drag lines out from ports to hook up elements.</p>
              </div>
              <div>
                <h3 className="font-bold text-text-primary mb-0.5">4. Modifying Elements</h3>
                <p>Click nodes or connecting lines to open dedicated panels in the Property Editor sidebar to adjust colors, ports, labels, or remove components.</p>
              </div>
              <div>
                <h3 className="font-bold text-text-primary mb-0.5">5. Database Savings & Video Render</h3>
                <p>Save diagrams inside the left Diagram Explorer sidebar. Submit render tasks via the bottom-right Export Animator widget overlay to query download links.</p>
              </div>
            </div>
            
            <button
              onClick={() => {
                setShowHelp(false);
                setTourStep(1);
              }}
              className="mt-4 w-full py-2 bg-accent-soft hover:bg-accent-soft/80 text-accent font-bold rounded-lg text-xs transition focus-ring border border-accent/20"
            >
              Start Interactive Tour
            </button>

            <button
              onClick={() => setShowHelp(false)}
              className="mt-2 w-full py-2 bg-accent hover:opacity-90 font-semibold rounded-lg text-xs text-white transition focus-ring"
            >
              Got it
            </button>
          </div>
        </div>
      )}

      {/* Interactive Tour Overlay */}
      {tourStep !== null && (
        <div 
          className={`z-[99] w-full max-w-sm px-4 select-none animate-zoom-in transition-all duration-300 ${
            tourStep === 1 
              ? 'fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 md:max-w-md' 
              : tourStep === 2
                ? 'fixed right-[350px] top-[180px]'
                : tourStep === 3
                  ? 'fixed right-[350px] top-[300px]'
                  : tourStep === 4
                    ? 'fixed bottom-[180px] left-1/2 transform -translate-x-1/2'
                    : 'fixed bottom-[100px] right-[100px]'
          }`}
        >
          <div className="glass-panel p-5 rounded-2xl shadow-premium border border-accent/25 bg-surface-1/95 text-text-primary flex flex-col gap-4 relative">
            {/* Tour Pointer Arrow */}
            {tourStep === 2 && (
              <div className="absolute right-[-8px] top-1/2 -translate-y-1/2 border-t-8 border-b-8 border-l-8 border-transparent border-l-surface-1" />
            )}
            {tourStep === 3 && (
              <div className="absolute right-[-8px] top-[24px] border-t-8 border-b-8 border-l-8 border-transparent border-l-surface-1" />
            )}
            {tourStep === 4 && (
              <div className="absolute bottom-[-8px] left-1/2 -translate-x-1/2 border-l-8 border-r-8 border-t-8 border-transparent border-t-surface-1" />
            )}
            {tourStep === 5 && (
              <div className="absolute bottom-[-8px] right-[116px] border-l-8 border-r-8 border-t-8 border-transparent border-t-surface-1" />
            )}

            {/* Header / Close */}
            <div className="flex items-center justify-between pb-2 border-b border-border-themed">
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-accent font-mono">
                FlowDraft Tour ({tourStep}/5)
              </span>
              <button
                onClick={() => {
                  setTourStep(null);
                  localStorage.setItem('flowdraft_onboarded_v2', 'true');
                }}
                className="p-1 hover:bg-surface-3 rounded text-text-muted hover:text-text-primary transition"
                title="Skip Tour"
              >
                <X size={14} />
              </button>
            </div>

            {/* Tour step details */}
            <div className="flex flex-col gap-1">
              <h4 className="text-sm font-extrabold text-text-primary">
                {tourStep === 1 && "🚀 Welcome to FlowDraft!"}
                {tourStep === 2 && "📦 Spawn Library Components"}
                {tourStep === 3 && "🎨 Inspect & Style Nodes"}
                {tourStep === 4 && "⏱️ Timeline & Layout Engine"}
                {tourStep === 5 && "🎥 Render & Download Video"}
              </h4>
              <p className="text-[11px] leading-relaxed text-text-secondary">
                {tourStep === 1 && "Your professional toolkit for crafting gorgeous architecture diagrams with real-time dynamic timeline animations. Let's take a quick 1-minute walk through the interface."}
                {tourStep === 2 && "Spawn template components by clicking them in the right-hand panel, or drag-and-drop cards directly onto the canvas to place them exactly where you need them."}
                {tourStep === 3 && "Click on any node, label, or path connector in the layout canvas to edit properties, tweak colors, adjust outline weights, corner radius, and text details."}
                {tourStep === 4 && "Control and playback the diagram state timeline using the bottom controller. Toggle the layout mode, edit titles, and watch nodes animate dynamically."}
                {tourStep === 5 && "Under the Export tab, submit render jobs to compile high-quality MP4 video outputs or animated GIF assets in the background, ready for download."}
              </p>
            </div>

            {/* Step indicator dots & buttons */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((step) => (
                  <span
                    key={step}
                    className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                      tourStep === step ? 'w-4 bg-accent' : 'bg-border-strong'
                    }`}
                  />
                ))}
              </div>

              <div className="flex items-center gap-2">
                {tourStep > 1 && (
                  <button
                    onClick={() => setTourStep(tourStep - 1)}
                    className="px-2.5 py-1 text-[11px] font-bold text-text-secondary hover:text-text-primary transition"
                  >
                    Back
                  </button>
                )}
                <button
                  onClick={() => {
                    if (tourStep === 5) {
                      setTourStep(null);
                      localStorage.setItem('flowdraft_onboarded_v2', 'true');
                      showToast('info', 'Tour Finished', 'You are ready to create diagram animations!');
                    } else {
                      setTourStep(tourStep + 1);
                    }
                  }}
                  className="px-3 py-1.5 bg-accent hover:opacity-90 text-[11px] font-bold text-white rounded-lg transition"
                >
                  {tourStep === 5 ? 'Done' : 'Next'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

