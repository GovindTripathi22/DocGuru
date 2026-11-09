"use client";

import React, { useState, useEffect, useCallback } from "react";
import { FileText, CheckCircle2, AlertTriangle, XCircle, Loader2 } from "lucide-react";

export type HealthStatus = "checking" | "ready" | "demo" | "misconfigured" | "offline";

interface HealthData {
  status?: string;
  version?: string;
  model_provider?: string;
  model_name?: string;
  mode?: "live" | "demo" | "misconfigured";
  ready?: boolean;
  capabilities?: { research?: boolean; max_upload_mb?: number };
}

export function Header({ onHealthUpdate }: { onHealthUpdate?: (health: HealthData | null) => void }) {
  const [healthStatus, setHealthStatus] = useState<HealthStatus>("checking");
  const [version, setVersion] = useState<string>("0.1.0");
  const [modelInfo, setModelInfo] = useState<string>("Checking...");

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) {
        setHealthStatus("offline");
        setModelInfo("Service unavailable");
        onHealthUpdate?.(null);
        return;
      }
      const data: HealthData = await res.json();
      if (data.version) setVersion(data.version);

      const provider = data.model_provider || "unknown";
      const model = data.model_name || "unknown";
      setModelInfo(`${provider} (${model})`);

      if (data.mode === "demo") {
        setHealthStatus("demo");
      } else if (data.mode === "misconfigured" || !data.ready) {
        setHealthStatus("misconfigured");
      } else {
        setHealthStatus("ready");
      }
      onHealthUpdate?.(data);
    } catch {
      setHealthStatus("offline");
      setModelInfo("Backend offline");
      onHealthUpdate?.(null);
    }
  }, [onHealthUpdate]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchHealth();
    }, 0);
    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        void fetchHealth();
      }
    }, 30000);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [fetchHealth]);

  return (
    <header className="border-b border-sky-200/80 bg-white/80 backdrop-blur-2xl sticky top-0 z-50 shadow-[0_4px_20px_rgba(186,230,253,0.25)] transition-all">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 via-sky-600 to-cyan-500 text-white shadow-[0_0_16px_rgba(14,165,233,0.35)] transition-transform hover:scale-105">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-base font-bold tracking-tight text-slate-900 flex items-center gap-2">
                DocGuru <span className="text-xs font-semibold text-sky-700 px-2 py-0.5 rounded-full bg-sky-100/90 border border-sky-200 shadow-sm">v{version}</span>
              </h1>
              {healthStatus === "ready" && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.18)]">
                  <CheckCircle2 className="h-3 w-3 text-emerald-600" /> Ready
                </span>
              )}
              {healthStatus === "demo" && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700 border border-amber-300 shadow-sm">
                  <AlertTriangle className="h-3 w-3 text-amber-600" /> Demo Mode
                </span>
              )}
              {healthStatus === "misconfigured" && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-300 shadow-sm">
                  <XCircle className="h-3 w-3 text-rose-600" /> Misconfigured
                </span>
              )}
              {healthStatus === "offline" && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-600 border border-slate-300 shadow-sm">
                  <XCircle className="h-3 w-3 text-slate-500" /> Offline
                </span>
              )}
              {healthStatus === "checking" && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-50 px-2.5 py-0.5 text-[11px] font-medium text-sky-700 border border-sky-200">
                  <Loader2 className="h-3 w-3 animate-spin text-sky-600 motion-reduce:animate-none" /> Checking...
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 font-medium">
              Template property checks for DOCX and PPTX files
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 rounded-xl border border-sky-200/80 bg-white/90 px-3.5 py-1.5 text-xs text-slate-600 shadow-sm backdrop-blur-md">
            <span className="text-slate-400 font-medium">Provider:</span>
            <strong className="text-slate-800 font-semibold">{modelInfo}</strong>
          </div>
        </div>
      </div>
    </header>
  );
}
