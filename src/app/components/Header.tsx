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
    <header className="border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-xl sticky top-0 z-50">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
                DocGuru <span className="text-xs font-medium text-zinc-400 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800">v{version}</span>
              </h1>
              {healthStatus === "ready" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-950/60 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/30">
                  <CheckCircle2 className="h-3 w-3" /> Ready
                </span>
              )}
              {healthStatus === "demo" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-950/60 px-2.5 py-0.5 text-[11px] font-medium text-amber-400 border border-amber-500/30">
                  <AlertTriangle className="h-3 w-3" /> Demo Mode
                </span>
              )}
              {healthStatus === "misconfigured" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-red-950/60 px-2.5 py-0.5 text-[11px] font-medium text-red-400 border border-red-500/30">
                  <XCircle className="h-3 w-3" /> Misconfigured
                </span>
              )}
              {healthStatus === "offline" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-zinc-900 px-2.5 py-0.5 text-[11px] font-medium text-zinc-400 border border-zinc-700">
                  <XCircle className="h-3 w-3" /> Offline
                </span>
              )}
              {healthStatus === "checking" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-zinc-900 px-2.5 py-0.5 text-[11px] font-medium text-zinc-400 border border-zinc-800">
                  <Loader2 className="h-3 w-3 animate-spin" /> Checking...
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400">
              Verified template inheritance for DOCX and PPTX documents
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs text-zinc-300">
            <span className="text-zinc-400">Provider:</span>
            <strong className="text-white font-medium">{modelInfo}</strong>
          </div>
        </div>
      </div>
    </header>
  );
}
