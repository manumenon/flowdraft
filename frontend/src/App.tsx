import { useState, useEffect } from 'react';
import { Canvas } from './components/Canvas';
import { defaultSpec } from './assets/defaultSpec';
import { useClockHook } from './hooks/useClockHook';
import type { FlowSpec } from './types/spec';
import { FileJson, Sun, Moon, Sparkles, Check, AlertCircle } from 'lucide-react';

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

  // 1. Determine initial spec
  const [spec, setSpec] = useState<FlowSpec>(() => {
    const querySpec = parseSpecFromQuery();
    return querySpec || defaultSpec;
  });

  // 2. Determine initial theme
  const [theme, setTheme] = useState<string>(() => {
    const params = new URLSearchParams(window.location.search);
    const queryTheme = params.get('theme');
    if (queryTheme) return queryTheme;
    
    if (spec.theme && typeof spec.theme === 'string') {
      return spec.theme;
    }
    return 'dark';
  });

  const [jsonInput, setJsonInput] = useState(() => JSON.stringify(spec, null, 2));
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Watch for theme in spec if it changes
  useEffect(() => {
    if (spec.theme && typeof spec.theme === 'string') {
      setTheme(spec.theme);
    }
  }, [spec]);

  const handleApplySpec = () => {
    try {
      const parsed = JSON.parse(jsonInput);
      if (!parsed.elements || !Array.isArray(parsed.elements)) {
        throw new Error("Invalid Spec: 'elements' must be a valid list.");
      }
      setSpec(parsed);
      setValidationError(null);
      setIsSidebarOpen(false);
    } catch (err: any) {
      setValidationError(err.message || 'Invalid JSON format');
    }
  };

  // Pure Render Mode (Viewer only, no grid, no handles, no controls)
  if (isRenderBox) {
    const bgColor = theme === 'dark' ? '#000000' : '#ffffff';
    return (
      <div className="w-screen h-screen overflow-hidden relative" style={{ backgroundColor: bgColor }}>
        <Canvas spec={spec} theme={theme} isPureRender={true} />
      </div>
    );
  }

  // Editor Mode
  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar for JSON Input */}
      {isSidebarOpen && (
        <div className="w-96 bg-slate-900 border-r border-slate-800 flex flex-col z-50 flex-shrink-0 animate-in slide-in-from-left duration-200">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <span className="font-bold flex items-center gap-2 text-sm uppercase tracking-wider text-slate-300">
              <FileJson size={18} className="text-blue-400" /> Import Spec JSON
            </span>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="text-xs px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded transition"
            >
              Close
            </button>
          </div>

          <div className="p-4 flex-grow flex flex-col gap-3 min-h-0">
            <textarea
              value={jsonInput}
              onChange={(e) => setJsonInput(e.target.value)}
              placeholder="Paste spec JSON here..."
              className="w-full flex-grow p-3 bg-slate-950 border border-slate-800 rounded font-mono text-xs text-emerald-400 focus:outline-none focus:border-slate-600 resize-none min-h-0"
            />
            {validationError && (
              <div className="p-3 bg-red-950/40 border border-red-800/80 rounded flex gap-2 items-start text-xs text-red-300">
                <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                <span>{validationError}</span>
              </div>
            )}
          </div>

          <div className="p-4 border-t border-slate-800">
            <button
              onClick={handleApplySpec}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 font-semibold rounded text-sm transition flex items-center justify-center gap-1.5"
            >
              <Check size={16} /> Apply Spec
            </button>
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex-grow flex flex-col min-w-0 h-full relative">
        {/* Navbar */}
        <header className="h-14 bg-slate-900 border-b border-slate-800 px-6 flex items-center justify-between z-40 flex-shrink-0">
          <div className="flex items-center gap-3">
            <Sparkles className="text-blue-500 animate-pulse w-5 h-5" />
            <div>
              <span className="font-bold tracking-wide text-sm text-slate-100 uppercase">FlowDraft</span>
              <span className="text-[10px] bg-slate-800 border border-slate-700 text-slate-400 px-1.5 py-0.5 rounded ml-2">Editor</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Theme Selector */}
            <div className="flex items-center bg-slate-950 border border-slate-800 rounded p-0.5">
              <button
                onClick={() => setTheme('dark')}
                className={`p-1.5 rounded transition ${theme === 'dark' ? 'bg-slate-800 text-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
                title="Dark Theme"
              >
                <Moon size={14} />
              </button>
              <button
                onClick={() => setTheme('light')}
                className={`p-1.5 rounded transition ${theme === 'light' ? 'bg-slate-800 text-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
                title="Light Theme"
              >
                <Sun size={14} />
              </button>
              <button
                onClick={() => setTheme('white')}
                className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded transition ${theme === 'white' ? 'bg-slate-800 text-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
                title="White Theme"
              >
                White
              </button>
            </div>

            <button
              onClick={() => setIsSidebarOpen(true)}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded border border-slate-700 transition flex items-center gap-1.5"
            >
              <FileJson size={14} />
              Import Spec
            </button>
          </div>
        </header>

        {/* Workspace Canvas */}
        <div className="flex-grow min-h-0 w-full relative">
          <Canvas spec={spec} theme={theme} isPureRender={false} />
        </div>
      </div>
    </div>
  );
}

export default App;
