"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import { Loader2, AlertTriangle } from "lucide-react";

import type { GenerationResultData } from "./ResultPanel";

interface JobProgressData {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  stage: string;
  progress: number;
  message: string;
  current?: { done: number; total: number };
  warnings: string[];
  result?: GenerationResultData;
  error?: { code?: string; message?: string; details?: Record<string, unknown> };
}

interface ProgressPanelProps {
  jobId: string;
  onComplete: (result: GenerationResultData) => void;
  onError: (error: { code?: string; message?: string }) => void;
  onCancel: () => void;
}

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued for processing",
  analyzing: "Analyzing template structure & invariants",
  planning_outline: "Synthesizing document outline",
  writing_sections: "Writing content sections",
  fetching_images: "Resolving and verifying visual assets",
  assembling: "Applying template inheritance",
  validating: "Validating zero-drift structural integrity",
  done: "Generation completed",
  failed: "Generation failed",
  cancelled: "Generation cancelled",
};

export function ProgressPanel({ jobId, onComplete, onError, onCancel }: ProgressPanelProps) {
  const [job, setJob] = useState<JobProgressData | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const completedRef = useRef(false);

  const pollJob = useCallback(async () => {
    if (completedRef.current) return;
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) {
        if (res.status === 404) {
          onError({ message: "Job not found on server." });
          completedRef.current = true;
          return;
        }
        return;
      }
      const data: JobProgressData = await res.json();
      setJob(data);

      if (data.status === "succeeded" && data.result) {
        completedRef.current = true;
        onComplete(data.result);
      } else if (data.status === "failed") {
        completedRef.current = true;
        onError(data.error || { message: data.message || "Generation failed" });
      } else if (data.status === "cancelled") {
        completedRef.current = true;
        onCancel();
      }
    } catch {
      // transient network error, retry on next poll tick
    }
  }, [jobId, onComplete, onError, onCancel]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void pollJob();
    }, 0);

    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        void pollJob();
      }
    }, 1000);

    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [pollJob]);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
      onCancel();
    } catch {
      setIsCancelling(false);
    }
  };

  const progressPercent = Math.round((job?.progress ?? 0) * 100);
  const stageName = job?.stage ? (STAGE_LABELS[job.stage] || job.stage) : "Processing";

  return (
    <div className="w-full rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 backdrop-blur-xl space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 text-indigo-400 animate-spin" />
          <div>
            <h3 className="text-sm font-semibold text-white">{stageName}</h3>
            <p className="text-xs text-zinc-400">{job?.message || "Running generation pipeline..."}</p>
          </div>
        </div>

        <button
          onClick={handleCancel}
          disabled={isCancelling}
          className="rounded-lg border border-red-500/30 bg-red-950/40 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-900/50 transition-colors disabled:opacity-50"
        >
          {isCancelling ? "Cancelling..." : "Cancel Job"}
        </button>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-zinc-400">
          <span>
            {job?.current ? `Items: ${job.current.done} of ${job.current.total}` : "Progress"}
          </span>
          <span className="font-mono text-zinc-200">{progressPercent}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-900 border border-zinc-800">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500 transition-all duration-300 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {job?.warnings && job.warnings.length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-950/30 p-3 space-y-1.5 text-xs text-amber-200">
          <div className="flex items-center gap-1.5 font-medium text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5" /> Pipeline Warnings
          </div>
          <ul className="list-disc pl-4 space-y-0.5">
            {job.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
