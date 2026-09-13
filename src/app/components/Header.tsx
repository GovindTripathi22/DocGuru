"use client";

import React, { useState, useEffect } from "react";
import { Lock, ShieldCheck, Sparkles } from "lucide-react";

export function Header() {
  const [modelLabel, setModelLabel] = useState<string>("Ollama (gemma2:2b)");
  const [isConnected, setIsConnected] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchHealth() {
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setIsConnected(true);
            const rawProvider = data.model_provider || "ollama";
            const provider = rawProvider === "google_ai" ? "Gemini" : rawProvider.charAt(0).toUpperCase() + rawProvider.slice(1);
            const model = data.model_name || "gemma2:2b";
            setModelLabel(`${provider} (${model})`);
          }
        } else {
          if (isMounted) setIsConnected(false);
        }
      } catch {
        if (isMounted) setIsConnected(false);
      }
    }

    fetchHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <header className="border-b border-cyan-500/20 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-50">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-indigo-600 text-white shadow-lg shadow-cyan-500/25 border border-cyan-400/40">
            <Lock className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-base font-extrabold tracking-tight text-white flex items-center gap-2">
                AetherStudio <span className="text-xs font-semibold text-cyan-400 px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-500/40">v2.4 Pro</span>
              </h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-950/80 px-2.5 py-0.5 text-[11px] font-bold text-emerald-400 border border-emerald-500/40 shadow-xs shadow-emerald-500/20">
                <ShieldCheck className="h-3 w-3" />
                EXACT STYLE LOCK ENFORCED
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Zero Theme Drift • OpenXML Surgical Mutation • Gemma 4 Neural Planner
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/80 px-3 py-1.5 text-xs text-zinc-300 backdrop-blur-md">
            <Sparkles className={`h-3.5 w-3.5 ${isConnected ? "text-cyan-400 animate-pulse" : "text-zinc-500"}`} />
            <span>Local Engine: <strong className="text-white">{modelLabel}</strong></span>
          </div>
          <div className={`h-2 w-2 rounded-full ${isConnected ? "bg-emerald-400 animate-ping" : "bg-zinc-600"}`}></div>
        </div>
      </div>
    </header>
  );
}
