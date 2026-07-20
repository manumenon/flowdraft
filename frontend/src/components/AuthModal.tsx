import React, { useState } from 'react';
import { Mail, Lock, Loader2, X } from 'lucide-react';

interface AuthModalProps {
  onClose: () => void;
  onSuccess: (token: string, email: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ onClose, onSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const baseUrl = window.location.origin === 'http://localhost:3000' || window.location.origin === 'http://127.0.0.1:3000' 
      ? 'http://localhost:8000' 
      : window.location.origin;

    try {
      if (isLogin) {
        // OAuth2 Password Request Flow
        const params = new URLSearchParams();
        params.append('username', email);
        params.append('password', password);

        const res = await fetch(`${baseUrl}/api/auth/token`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: params,
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || 'Login failed');
        }

        onSuccess(data.access_token, email);
      } else {
        // Signup
        const res = await fetch(`${baseUrl}/api/auth/signup`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email, password }),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || 'Signup failed');
        }

        // Auto login after signup
        const params = new URLSearchParams();
        params.append('username', email);
        params.append('password', password);

        const tokenRes = await fetch(`${baseUrl}/api/auth/token`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: params,
        });

        const tokenData = await tokenRes.json();
        if (!tokenRes.ok) {
          throw new Error(tokenData.detail || 'Auto-login failed');
        }

        onSuccess(tokenData.access_token, email);
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface-1/90 backdrop-blur-md border border-border-themed rounded-2xl shadow-2xl overflow-hidden flex flex-col relative animate-zoom-in">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 text-text-muted hover:text-text-primary rounded-lg hover:bg-surface-2 transition focus-ring"
          aria-label="Close auth dialog"
        >
          <X size={18} />
        </button>

        <div className="p-8">
          {/* Branded Icon Header */}
          <div className="flex items-center gap-2 mb-3">
            <div className="w-6 h-6 rounded-lg flex items-center justify-center font-bold text-xs text-white shadow-glow-blue select-none" style={{ backgroundColor: 'var(--accent)' }}>
              FD
            </div>
            <span className="text-[10px] text-text-muted uppercase tracking-widest font-bold font-mono">FlowDraft Sync</span>
          </div>

          <h2 className="text-xl font-extrabold tracking-wide text-text-primary uppercase mb-1">
            {isLogin ? 'Sign In' : 'Register'}
          </h2>
          <p className="text-xs text-text-secondary mb-6">
            {isLogin ? 'Welcome back. Access your diagrams.' : 'Create credentials to start saving configurations.'}
          </p>

          {/* Premium Pill Segment Tab Switcher */}
          <div className="flex bg-surface-3 border border-border-themed p-0.5 rounded-xl mb-6">
            <button
              onClick={() => setIsLogin(true)}
              className={`flex-grow py-1.5 rounded-lg text-xs font-bold transition focus-ring ${
                isLogin ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setIsLogin(false)}
              className={`flex-grow py-1.5 rounded-lg text-xs font-bold transition focus-ring ${
                !isLogin ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="auth-email" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Email</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-text-muted">
                  <Mail size={15} />
                </span>
                <input
                  id="auth-email"
                  type="email"
                  required
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 bg-surface-0 border border-border-themed rounded-xl text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring"
                />
              </div>
            </div>

            <div>
              <label htmlFor="auth-password" className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Password</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-text-muted">
                  <Lock size={15} />
                </span>
                <input
                  id="auth-password"
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 bg-surface-0 border border-border-themed rounded-xl text-xs text-text-primary focus:outline-none focus:border-accent transition focus-ring"
                />
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-500/10 text-red-500 border border-red-500/20 rounded-xl text-xs">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-accent hover:opacity-90 disabled:opacity-50 text-white font-bold rounded-xl text-xs transition flex items-center justify-center gap-2 shadow-lg uppercase tracking-wider font-mono focus-ring"
            >
              {loading ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  Please Wait...
                </>
              ) : (
                isLogin ? 'Access Space' : 'Deploy User'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
