import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const Toast: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

const ToastItem: React.FC<{ toast: ToastMessage; onDismiss: (id: string) => void }> = ({ toast, onDismiss }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const icons = {
    success: <CheckCircle className="text-emerald-400 w-5 h-5 flex-shrink-0" />,
    error: <AlertCircle className="text-rose-400 w-5 h-5 flex-shrink-0" />,
    info: <Info className="text-blue-400 w-5 h-5 flex-shrink-0" />,
    warning: <AlertTriangle className="text-amber-400 w-5 h-5 flex-shrink-0" />,
  };

  const borders = {
    success: 'border-emerald-500/20 bg-surface-1/95 shadow-emerald-950/10',
    error: 'border-rose-500/20 bg-surface-1/95 shadow-rose-950/10',
    info: 'border-blue-500/20 bg-surface-1/95 shadow-blue-950/10',
    warning: 'border-amber-500/20 bg-surface-1/95 shadow-amber-950/10',
  };

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border backdrop-blur-md shadow-lg animate-zoom-in ${borders[toast.type]}`}
      role="alert"
    >
      {icons[toast.type]}
      <div className="flex-grow min-w-0">
        <h4 className="text-xs font-bold text-text-primary tracking-wide uppercase">{toast.title}</h4>
        <p className="text-xs text-text-secondary mt-1 leading-relaxed">{toast.message}</p>
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-text-muted hover:text-text-primary p-0.5 rounded-lg transition"
      >
        <X size={14} />
      </button>
    </div>
  );
};
