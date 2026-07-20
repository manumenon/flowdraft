import React, { useState, useEffect } from 'react';
import { Download, Film, Loader2, Play, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import type { FlowSpec } from '../types/spec';

interface ExportPanelProps {
  token: string | null;
  spec: FlowSpec;
  activeDiagramId: string | null;
  onTriggerAuth: () => void;
  isInline?: boolean;
  tourStep?: number | null;
}

interface ExportJobStatus {
  jobId: string;
  title: string;
  format: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  downloadUrl?: string | null;
  errorMessage?: string | null;
}

export const ExportPanel: React.FC<ExportPanelProps> = ({
  token,
  spec,
  activeDiagramId,
  onTriggerAuth,
  isInline = false,
  tourStep,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [format, setFormat] = useState<'mp4' | 'gif'>('mp4');
  const [submitting, setSubmitting] = useState(false);
  const [confirmClearHistory, setConfirmClearHistory] = useState(false);
  const [jobs, setJobs] = useState<ExportJobStatus[]>(() => {
    const saved = localStorage.getItem('flowdraft_export_jobs');
    return saved ? JSON.parse(saved) : [];
  });
  const [jobProgress, setJobProgress] = useState<Record<string, number>>({});

  const baseUrl = window.location.origin.includes(':3000')
    ? window.location.origin.replace(':3000', ':8000')
    : window.location.origin;

  const resolveDownloadUrl = (url: string | null) => {
    if (!url) return '';
    let resolved = url;
    if (resolved.includes('minio:9000')) {
      resolved = resolved.replace('minio:9000', 'localhost:9000');
    }
    if (resolved.startsWith('http://') || resolved.startsWith('https://')) {
      return resolved;
    }
    return baseUrl + resolved;
  };

  // Persist jobs list
  useEffect(() => {
    localStorage.setItem('flowdraft_export_jobs', JSON.stringify(jobs));
  }, [jobs]);

  // Handle simulated progress increments
  useEffect(() => {
    const active = jobs.some((j) => j.status === 'queued' || j.status === 'processing');
    if (!active) return;

    const timer = setInterval(() => {
      setJobProgress((prev) => {
        const next = { ...prev };
        jobs.forEach((job) => {
          if (job.status === 'queued') {
            next[job.jobId] = Math.min(25, (next[job.jobId] || 0) + 5);
          } else if (job.status === 'processing') {
            next[job.jobId] = Math.min(95, Math.max(30, (next[job.jobId] || 25) + 4));
          } else if (job.status === 'completed') {
            next[job.jobId] = 100;
          } else if (job.status === 'failed') {
            next[job.jobId] = 0;
          }
        });
        return next;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [jobs]);

  // Polling for active jobs
  useEffect(() => {
    const activeJobs = jobs.filter((j) => j.status === 'queued' || j.status === 'processing');
    if (activeJobs.length === 0 || !token) return;

    const timer = setInterval(async () => {
      const updatedJobs = [...jobs];
      let hasUpdates = false;

      for (let i = 0; i < updatedJobs.length; i++) {
        const job = updatedJobs[i];
        if (job.status === 'queued' || job.status === 'processing') {
          try {
            const res = await fetch(`${baseUrl}/api/export/${job.jobId}`, {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            });
            if (res.ok) {
              const data = await res.json();
              if (data.status !== job.status || data.download_url !== job.downloadUrl) {
                updatedJobs[i] = {
                  ...job,
                  status: data.status,
                  downloadUrl: data.download_url,
                  errorMessage: data.error_message,
                };
                hasUpdates = true;
              }
            }
          } catch (err) {
            console.error('Error polling status for job ' + job.jobId, err);
          }
        }
      }

      if (hasUpdates) {
        setJobs(updatedJobs);
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [jobs, token]);

  const handleStartExport = async () => {
    if (!token) {
      onTriggerAuth();
      return;
    }
    setSubmitting(true);
    try {
      const payload: any = {
        format,
        diagram_id: activeDiagramId || null,
      };

      // If diagram is unsaved or we want absolute accuracy, pass the spec override
      if (!activeDiagramId) {
        payload.spec_override = spec;
      }

      const res = await fetch(`${baseUrl}/api/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok && data.job_id) {
        const newJob: ExportJobStatus = {
          jobId: data.job_id,
          title: spec.title?.highlight || 'Architecture Flow',
          format,
          status: 'queued',
        };
        setJobs((prev) => [newJob, ...prev]);
        setIsOpen(true);
      } else {
        alert(data.detail || 'Failed to submit render job');
      }
    } catch (err) {
      console.error('Export error', err);
      alert('Error triggering animation export pipeline.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClearHistory = () => {
    if (confirmClearHistory) {
      setJobs([]);
      setConfirmClearHistory(false);
    } else {
      setConfirmClearHistory(true);
    }
  };

  const completedJobsCount = jobs.filter((j) => j.status === 'completed' && j.downloadUrl).length;

  if (isInline) {
    return (
      <div className="flex flex-col gap-4 text-text-primary">
        <div>
          <span className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2">Select Format</span>
          <div className="grid grid-cols-2 gap-2 bg-surface-3 border border-border-themed p-0.5 rounded-xl">
            <button
              onClick={() => setFormat('mp4')}
              className={`py-2 rounded-lg text-xs font-bold transition focus-ring ${
                format === 'mp4' ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              MP4 Video
            </button>
            <button
              onClick={() => setFormat('gif')}
              className={`py-2 rounded-lg text-xs font-bold transition focus-ring ${
                format === 'gif' ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              GIF Animation
            </button>
          </div>
        </div>

        <button
          onClick={handleStartExport}
          disabled={submitting}
          className="w-full py-2.5 bg-accent hover:opacity-90 text-white font-bold rounded-xl text-xs transition flex items-center justify-center gap-2 shadow-md focus-ring uppercase tracking-wider font-mono"
        >
          {submitting ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Submit Render Task
        </button>

        {/* Jobs Status List History logs */}
        <div className="flex flex-col gap-2 mt-2 min-h-0">
          <div className="flex items-center justify-between border-b border-border-themed pb-2 mb-1">
            <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Active Jobs Logs</span>
            {jobs.length > 0 && (
              <div>
                {confirmClearHistory ? (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={handleClearHistory}
                      className="px-1.5 py-0.5 bg-red-600 text-white rounded text-[10px] font-bold uppercase tracking-wider hover:bg-red-500"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setConfirmClearHistory(false)}
                      className="px-1.5 py-0.5 bg-surface-3 text-text-primary rounded text-[10px] font-bold uppercase tracking-wider hover:bg-surface-2"
                    >
                      No
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={handleClearHistory}
                    className="text-[11px] text-red-600 hover:text-red-500 font-bold uppercase font-mono"
                  >
                    Clear All
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2 pt-2 border-t border-border-themed max-h-[300px] overflow-y-auto custom-scrollbar">
            {jobs.length === 0 ? (
              <div className="text-center py-6 text-[11px] text-text-muted font-mono">
                No active/historical export jobs queued.
              </div>
            ) : (
              jobs.map((job) => (
                <div
                  key={job.jobId}
                  className="p-3 rounded-lg bg-surface-2 border border-border-themed flex items-center justify-between animate-fade-in"
                >
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-bold text-text-primary truncate leading-tight">
                      {job.title}
                    </span>
                    <span className="text-[10px] font-mono text-text-muted uppercase mt-0.5">
                      {job.format} format
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {job.status === 'queued' && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-surface-3 border border-border-themed rounded font-bold text-text-secondary">
                        Queued ({jobProgress[job.jobId] || 0}%)
                      </span>
                    )}
                    {job.status === 'processing' && (
                      <div className="flex items-center gap-1">
                        <Loader2 size={10} className="animate-spin text-accent" />
                        <span className="text-[10px] text-accent font-bold">Rendering ({jobProgress[job.jobId] || 30}%)</span>
                      </div>
                    )}
                    {job.status === 'completed' && job.downloadUrl && (
                      <a
                        href={resolveDownloadUrl(job.downloadUrl)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 bg-emerald-600/10 text-emerald-500 border border-emerald-500/20 rounded transition flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider focus-ring"
                        title="Download Animation Output"
                      >
                        <Download size={11} />
                      </a>
                    )}
                    {job.status === 'failed' && (
                      <span
                        className="p-1.5 bg-red-500/10 text-red-500 border border-red-500/20 rounded flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider"
                        title={job.errorMessage || 'Failed render pipeline'}
                      >
                        <AlertTriangle size={11} />
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute bottom-6 right-6 z-[30] flex flex-col items-end">
      {/* Drawer overlay Trigger Button */}
      <button
        id="tour-exporter"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`px-4 py-2.5 bg-accent hover:opacity-90 text-white font-bold rounded-xl shadow-lg transition flex items-center gap-2 focus-ring select-none animate-fade-in ${
          tourStep === 5 ? 'ring-4 ring-amber-500 scale-105 shadow-glow-amber' : ''
        }`}
        aria-label="Open Export Drawer"
      >
        <Film size={15} className={jobs.some((j) => j.status === 'processing') ? 'animate-spin' : ''} />
        <span className="text-xs uppercase tracking-wider">Export Animator</span>
        {completedJobsCount > 0 && (
          <span className="w-5 h-5 rounded-full bg-emerald-500 text-white text-[10px] flex items-center justify-center font-bold font-mono border border-white">
            {completedJobsCount}
          </span>
        )}
        {isOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>

      {/* Centered Modal Overlay */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-surface-0/60 backdrop-blur-sm z-[90] cursor-pointer"
            onClick={() => setIsOpen(false)}
          />
          {/* Modal Container */}
          <div className="fixed inset-0 flex items-center justify-center p-4 z-[100] pointer-events-none select-none animate-zoom-in">
            <div className="w-full max-w-sm bg-surface-1 border border-border-themed rounded-2xl shadow-2xl overflow-hidden backdrop-blur-md flex flex-col pointer-events-auto relative p-6 text-text-primary">
              <div className="flex items-center justify-between pb-3 border-b border-border-themed mb-4">
                <span className="font-bold flex items-center gap-2 text-xs uppercase tracking-wider text-text-primary">
                  <Film size={16} className="text-accent" /> Export Options
                </span>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 hover:bg-surface-3 text-text-muted hover:text-text-primary rounded-lg transition focus-ring"
                  aria-label="Close export panel"
                >
                  <ChevronDown size={18} />
                </button>
              </div>

              <div className="flex flex-col gap-4 overflow-y-auto max-h-[400px] pr-1 custom-scrollbar">
                {/* Format selector option buttons */}
                <div>
                  <span className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2">Select Format</span>
                  <div className="grid grid-cols-2 gap-2 bg-surface-3 border border-border-themed p-0.5 rounded-xl">
                    <button
                      onClick={() => setFormat('mp4')}
                      className={`py-2 rounded-lg text-xs font-bold transition focus-ring ${
                        format === 'mp4' ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      MP4 Video
                    </button>
                    <button
                      onClick={() => setFormat('gif')}
                      className={`py-2 rounded-lg text-xs font-bold transition focus-ring ${
                        format === 'gif' ? 'bg-surface-1 text-accent shadow-sm' : 'text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      GIF Animation
                    </button>
                  </div>
                </div>

                <button
                  onClick={handleStartExport}
                  disabled={submitting}
                  className="w-full py-2.5 bg-accent hover:opacity-90 text-white font-bold rounded-xl text-xs transition flex items-center justify-center gap-2 shadow-md focus-ring uppercase tracking-wider font-mono"
                >
                  {submitting ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Submit Render Task
                </button>

                {/* Jobs Status List History logs */}
                <div className="flex flex-col gap-2 mt-4">
                  <div className="flex items-center justify-between border-b border-border-themed pb-2 mb-1">
                    <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Active Jobs Logs</span>
                    {jobs.length > 0 && (
                      <div>
                        {confirmClearHistory ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={handleClearHistory}
                              className="px-1.5 py-0.5 bg-red-600 text-white rounded text-[10px] font-bold uppercase tracking-wider hover:bg-red-500"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setConfirmClearHistory(false)}
                              className="px-1.5 py-0.5 bg-surface-3 text-text-primary rounded text-[10px] font-bold uppercase tracking-wider hover:bg-surface-2"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={handleClearHistory}
                            className="text-[11px] text-red-600 hover:text-red-500 font-bold uppercase font-mono"
                          >
                            Clear All
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-2 pt-2 border-t border-border-themed max-h-48 overflow-y-auto custom-scrollbar">
                    {jobs.length === 0 ? (
                      <div className="text-center py-6 text-[11px] text-text-muted font-mono">
                        No active/historical export jobs queued.
                      </div>
                    ) : (
                      jobs.map((job) => (
                        <div
                          key={job.jobId}
                          className="p-3 rounded-lg bg-surface-2 border border-border-themed flex items-center justify-between animate-fade-in"
                        >
                          <div className="flex flex-col min-w-0">
                            <span className="text-xs font-bold text-text-primary truncate leading-tight">
                              {job.title}
                            </span>
                            <span className="text-[10px] font-mono text-text-muted uppercase mt-0.5">
                              {job.format} format
                            </span>
                          </div>

                          <div className="flex items-center gap-1.5">
                            {job.status === 'queued' && (
                              <span className="text-[10px] px-1.5 py-0.5 bg-surface-3 border border-border-themed rounded font-bold text-text-secondary">
                                Queued ({jobProgress[job.jobId] || 0}%)
                              </span>
                            )}
                            {job.status === 'processing' && (
                              <div className="flex items-center gap-1">
                                <Loader2 size={10} className="animate-spin text-accent" />
                                <span className="text-[10px] text-accent font-bold">Rendering ({jobProgress[job.jobId] || 30}%)</span>
                              </div>
                            )}
                            {job.status === 'completed' && job.downloadUrl && (
                              <a
                                href={resolveDownloadUrl(job.downloadUrl)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-1.5 bg-emerald-600/10 text-emerald-500 border border-emerald-500/20 rounded transition flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider focus-ring"
                                title="Download Animation Output"
                              >
                                <Download size={11} />
                              </a>
                            )}
                            {job.status === 'failed' && (
                              <span
                                className="p-1.5 bg-red-500/10 text-red-500 border border-red-500/20 rounded flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider"
                                title={job.errorMessage || 'Failed render pipeline'}
                              >
                                <AlertTriangle size={11} />
                              </span>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ExportPanel;
