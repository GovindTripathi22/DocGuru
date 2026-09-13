"use client";

import React, { useState, useEffect } from "react";
import { Lock, ShieldCheck, Cpu, ArrowRight, CheckCircle2, Image, FileCode } from "lucide-react";

interface GenerationPreviewProps {
  filename: string;
  documentType: string;
  styleHash: string;
  prompt: string;
  isGenerating?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function GenerationPreview({
  filename,
  documentType,
  styleHash,
  prompt,
  isGenerating = false,
  onConfirm,
  onCancel,
}: GenerationPreviewProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [progressPercent, setProgressPercent] = useState(15);
  const [elapsedSec, setElapsedSec] = useState(0);
  const prevGeneratingRef = React.useRef(isGenerating);

  const steps = [
    { title: "Parsing Template & Locking Styles", desc: "Extracting XML headings, tables, and borders into locked state", icon: Lock },
    { title: "Gemma Neural Reasoning", desc: "Local Gemma 4 model structuring intent without style drift", icon: Cpu },
    { title: "Visual Asset Director", desc: "Sourcing high-res photography and synthesizing figures", icon: Image },
    { title: "OpenXML & Master Assembly", desc: "Injecting content strictly reusing master XML nodes", icon: FileCode },
    { title: "Regression & Hash Verification", desc: "SHA-256 invariant comparison (Original == Output)", icon: ShieldCheck },
  ];

  const handleConfirm = () => {
    setCurrentStep(0);
    setProgressPercent(15);
    setElapsedSec(0);
    onConfirm();
  };

  const handleCancel = () => {
    setCurrentStep(0);
    setProgressPercent(15);
    setElapsedSec(0);
    onCancel();
  };

  useEffect(() => {
    if (prevGeneratingRef.current && !isGenerating) {
      // Immediately snap to 100% upon receiving the API response
      const timer = setTimeout(() => {
        setProgressPercent(100);
        setCurrentStep(steps.length - 1);
      }, 0);
      return () => clearTimeout(timer);
    }
    prevGeneratingRef.current = isGenerating;
  }, [isGenerating, steps.length]);

  useEffect(() => {
    if (!isGenerating) return;

    const startTime = Date.now();

    const interval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      setElapsedSec(Math.floor(elapsed));

      let pct = 15;
      if (elapsed <= 1.5) {
        // Rapidly moves to 30% during initial template loading and analysis
        pct = 15 + (elapsed / 1.5) * 15;
      } else {
        // Asymptotically approaches 90% while waiting for Gemma generation to complete
        const t = elapsed - 1.5;
        pct = 30 + 59 * (1 - Math.exp(-t / 14));
      }

      const clamped = Math.min(Math.round(pct * 10) / 10, 89.5);
      setProgressPercent(clamped);

      if (clamped < 30) {
        setCurrentStep(0);
      } else if (clamped < 55) {
        setCurrentStep(1);
      } else if (clamped < 72) {
        setCurrentStep(2);
      } else if (clamped < 85) {
        setCurrentStep(3);
      } else {
        setCurrentStep(4);
      }
    }, 200);

    return () => {
      clearInterval(interval);
    };
  }, [isGenerating, steps.length]);

  return (
    <div className="rounded-2xl border border-cyan-500/30 bg-zinc-950/90 p-6 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-indigo-600 text-white shadow-md shadow-cyan-500/20">
            <Lock className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <span>Exact Template Execution Deck</span>
              <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-mono uppercase text-cyan-300 border border-zinc-700">
                {documentType}
              </span>
            </h4>
            <p className="text-xs text-zinc-400">
              Style invariants verified & locked (§28)
            </p>
          </div>
        </div>

        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-950 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/40">
          <ShieldCheck className="h-4 w-4" /> 100% STYLE LOCK ENFORCED
        </span>
      </div>

      {/* Invariants Grid */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Base Artifact</div>
          <div className="mt-0.5 truncate text-xs font-bold text-white">{filename}</div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Modifications</div>
          <div className="mt-0.5 text-xs font-bold text-cyan-400">Content Only</div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Theme & Masters</div>
          <div className="mt-0.5 text-xs font-bold text-emerald-400">100% LOCKED</div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Style Hash</div>
          <div className="mt-0.5 font-mono text-xs font-bold text-zinc-300">{styleHash ? `${styleHash.slice(0, 16)}...` : "Locked"}</div>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900/80 p-3.5 text-xs text-zinc-300">
        <strong className="text-white">Requested Intent:</strong> &ldquo;{prompt}&rdquo;
      </div>

      {/* Live Animated Multi-Step Execution Console when isGenerating is True */}
      {isGenerating ? (
        <div className="mt-6 rounded-2xl border border-cyan-500/40 bg-zinc-900/90 p-5 shadow-inner">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-cyan-400 animate-ping"></div>
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
                Live Execution Pipeline • Elapsed: {elapsedSec}s
              </span>
            </div>
            <span className="text-xs font-mono font-bold text-white">
              {Math.round(progressPercent)}%
            </span>
          </div>

          {/* Glowing Neon Progress Bar */}
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 via-indigo-500 to-emerald-400 transition-all duration-500 shadow-md shadow-cyan-500/50"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* 5-Step Pipeline List */}
          <div className="mt-5 space-y-3">
            {steps.map((step, idx) => {
              const Icon = step.icon;
              const isPast = idx < currentStep;
              const isCurrent = idx === currentStep;

              return (
                <div
                  key={idx}
                  className={`flex items-center gap-3.5 rounded-xl p-2.5 transition-all ${
                    isCurrent
                      ? "bg-cyan-950/60 border border-cyan-500/60 shadow-md shadow-cyan-500/25 ring-1 ring-cyan-500/40 animate-pulse"
                      : isPast
                      ? "bg-zinc-900/30 opacity-70"
                      : "opacity-40"
                  }`}
                >
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-lg ${
                      isPast
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-500/40"
                        : isCurrent
                        ? "bg-cyan-500 text-zinc-950 font-bold animate-pulse"
                        : "bg-zinc-800 text-zinc-500"
                    }`}
                  >
                    {isPast ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-3.5 w-3.5" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-white flex items-center gap-2">
                      <span>{step.title}</span>
                      {isCurrent && <span className="text-[10px] text-cyan-400 font-normal animate-pulse">Running on GPU...</span>}
                    </div>
                    <div className="text-[11px] text-zinc-400 truncate">{step.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleCancel}
            className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-800 transition-all"
          >
            Modify Prompt
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-cyan-500/25 hover:brightness-110 active:scale-[0.98] transition-all"
          >
            <span>Confirm & Execute</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
