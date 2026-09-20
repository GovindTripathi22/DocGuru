"use client";

import React, { useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  Download,
  RotateCcw,
  Clock,
  Cpu,
  Layers,
  FileCheck,
  AlertTriangle,
} from "lucide-react";

interface ComponentResult {
  name: string;
  status: "identical" | "changed" | "intentional_override";
  detail?: string;
}

interface ValidationReport {
  passed: boolean;
  status?: "passed" | "failed" | "not_applicable";
  original_style_hash?: string;
  generated_style_hash?: string;
  hash_match?: boolean;
  font_drift_detected?: boolean;
  border_drift_detected?: boolean;
  margin_drift_detected?: boolean;
  layout_drift_detected?: boolean;
  header_footer_preserved?: boolean;
  table_formatting_preserved?: boolean;
  components?: ComponentResult[];
  issues?: string[];
  intentional_overrides?: Array<{ target: string; value: string }>;
  warnings?: string[];
}

export interface GenerationResultData {
  success: boolean;
  output_filename: string;
  download_url: string;
  generation_mode?: string;
  template_id?: string;
  plan_summary?: Array<{ title: string; layout?: string }>;
  validation: ValidationReport;
  warnings?: string[];
  execution_time_sec?: number;
  timings?: Record<string, number>;
  model?: string;
}

interface ResultPanelProps {
  result: GenerationResultData;
  templateType: "docx" | "pptx" | "pdf";
  onReset: () => void;
}

export function ResultPanel({ result, templateType, onReset }: ResultPanelProps) {
  const [revalidating, setRevalidating] = useState(false);
  const [currentVal, setCurrentVal] = useState<ValidationReport>(result.validation);
  const [reverifyMessage, setReverifyMessage] = useState<string | null>(null);

  const valStatus = currentVal.status || (currentVal.passed ? "passed" : "failed");
  const isPdf = templateType === "pdf";

  const handleReverify = async () => {
    setRevalidating(true);
    setReverifyMessage(null);
    try {
      const res = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: result.template_id,
          generated_filename: result.output_filename,
        }),
      });
      if (res.ok) {
        const valData: ValidationReport = await res.json();
        setCurrentVal(valData);
        setReverifyMessage("Validation re-verified against template package.");
      } else {
        setReverifyMessage("Re-validation request failed.");
      }
    } catch {
      setReverifyMessage("Network error during re-verification.");
    } finally {
      setRevalidating(false);
    }
  };

  const components: ComponentResult[] = currentVal.components || [
    {
      name: "Typography & Styles",
      status: currentVal.font_drift_detected ? "changed" : "identical",
      detail: currentVal.font_drift_detected ? "Font drift detected" : "Font hierarchy preserved",
    },
    {
      name: "Page & Margin Setup",
      status: currentVal.margin_drift_detected ? "changed" : "identical",
      detail: currentVal.margin_drift_detected ? "Margins altered" : "Margins preserved",
    },
    {
      name: "Borders & Shading",
      status: currentVal.border_drift_detected ? "changed" : "identical",
      detail: currentVal.border_drift_detected ? "Borders altered" : "Border definitions preserved",
    },
    {
      name: "Headers & Footers",
      status: currentVal.header_footer_preserved === false ? "changed" : "identical",
      detail: currentVal.header_footer_preserved === false ? "Header/footer drift" : "Header & footer preserved",
    },
    {
      name: "Master Layouts",
      status: currentVal.layout_drift_detected ? "changed" : "identical",
      detail: currentVal.layout_drift_detected ? "Layout geometry modified" : "Layout structures preserved",
    },
  ];

  return (
    <div className="w-full space-y-6">
      {/* Status Banner */}
      <div
        className={`rounded-2xl border p-6 backdrop-blur-xl ${
          isPdf
            ? "border-cyan-500/30 bg-cyan-950/20 text-cyan-200"
            : valStatus === "passed"
            ? "border-emerald-500/30 bg-emerald-950/20 text-emerald-200"
            : "border-red-500/40 bg-red-950/30 text-red-200"
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            {isPdf ? (
              <FileCheck className="h-6 w-6 text-cyan-400 shrink-0" />
            ) : valStatus === "passed" ? (
              <CheckCircle2 className="h-6 w-6 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="h-6 w-6 text-red-400 shrink-0" />
            )}
            <div>
              <h2 className="text-base font-semibold text-white">
                {isPdf
                  ? "Approximate layout (PDF reference mode)"
                  : valStatus === "passed"
                  ? "Template Invariants Verified"
                  : "Template Drift Detected"}
              </h2>
              <p className="text-xs text-zinc-300 mt-0.5">
                {isPdf
                  ? "Derived layout dimensions, typography, and margins from PDF structure."
                  : valStatus === "passed"
                  ? "Target styles, theme fonts, and layout structures match the original template."
                  : "Output document diverged from the original template package."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {valStatus === "passed" || isPdf ? (
              <a
                href={result.download_url}
                download={result.output_filename}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-md hover:bg-indigo-500 transition-colors"
              >
                <Download className="h-4 w-4" /> Download Artifact
              </a>
            ) : (
              <div className="flex flex-col items-end gap-1">
                <button
                  disabled
                  className="inline-flex items-center gap-2 rounded-xl bg-zinc-800 px-4 py-2.5 text-xs font-medium text-zinc-500 cursor-not-allowed"
                >
                  <Download className="h-4 w-4" /> Download Disabled (Drift Detected)
                </button>
                <a
                  href={result.download_url}
                  className="text-[11px] text-zinc-400 hover:text-zinc-300 underline"
                >
                  Download anyway for diagnostics
                </a>
              </div>
            )}

            <button
              onClick={handleReverify}
              disabled={revalidating}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 transition-colors disabled:opacity-50"
            >
              <RotateCcw className={`h-3.5 w-3.5 ${revalidating ? "animate-spin" : ""}`} /> Re-verify
            </button>
          </div>
        </div>

        {reverifyMessage && (
          <p className="mt-3 text-xs text-zinc-400 border-t border-zinc-800/80 pt-2">{reverifyMessage}</p>
        )}
      </div>

      {/* Metadata & Diagnostics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 space-y-1">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Clock className="h-4 w-4 text-zinc-400" /> Execution Time
          </div>
          <p className="text-sm font-semibold text-white">
            {result.execution_time_sec ?? result.timings?.execution_time_sec ?? 0}s
          </p>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 space-y-1">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Cpu className="h-4 w-4 text-zinc-400" /> Model / Mode
          </div>
          <p className="text-sm font-semibold text-white">
            {result.model || "Configured Provider"}{" "}
            <span className="text-xs text-zinc-400">({result.generation_mode || "standard"})</span>
          </p>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 space-y-1">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Layers className="h-4 w-4 text-zinc-400" /> Planned Sections
          </div>
          <p className="text-sm font-semibold text-white">
            {result.plan_summary?.length ?? 0} entries
          </p>
        </div>
      </div>

      {/* Components Verification Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">Component Verification Results</h3>
          <span className="text-xs text-zinc-400 font-mono">
            Original: {currentVal.original_style_hash?.slice(0, 16) || "N/A"} • Generated: {currentVal.generated_style_hash?.slice(0, 16) || "N/A"}
          </span>
        </div>

        <div className="divide-y divide-zinc-800/60">
          {components.map((comp, idx) => (
            <div key={idx} className="px-6 py-3.5 flex items-center justify-between text-xs">
              <span className="font-medium text-zinc-200">{comp.name}</span>
              <div className="flex items-center gap-2.5">
                <span className="text-zinc-400">{comp.detail}</span>
                {comp.status === "identical" && (
                  <span className="inline-flex items-center gap-1 rounded bg-emerald-950/60 px-2 py-0.5 text-[11px] text-emerald-400 border border-emerald-500/30">
                    <CheckCircle2 className="h-3 w-3" /> Identical
                  </span>
                )}
                {comp.status === "intentional_override" && (
                  <span className="inline-flex items-center gap-1 rounded bg-indigo-950/60 px-2 py-0.5 text-[11px] text-indigo-400 border border-indigo-500/30">
                    Override
                  </span>
                )}
                {comp.status === "changed" && (
                  <span className="inline-flex items-center gap-1 rounded bg-red-950/60 px-2 py-0.5 text-[11px] text-red-400 border border-red-500/30">
                    <AlertCircle className="h-3 w-3" /> Changed
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Issues list if any */}
      {currentVal.issues && currentVal.issues.length > 0 && (
        <div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-5 space-y-2 text-xs text-red-200">
          <div className="flex items-center gap-2 font-medium text-red-400">
            <AlertCircle className="h-4 w-4" /> Detected Invariant Issues ({currentVal.issues.length})
          </div>
          <ul className="list-disc pl-5 space-y-1">
            {currentVal.issues.map((issue, idx) => (
              <li key={idx}>{issue}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings if any */}
      {result.warnings && result.warnings.length > 0 && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-950/20 p-5 space-y-2 text-xs text-amber-200">
          <div className="flex items-center gap-2 font-medium text-amber-400">
            <AlertTriangle className="h-4 w-4" /> Warnings
          </div>
          <ul className="list-disc pl-5 space-y-1">
            {result.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={onReset}
          className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-800 transition-colors"
        >
          Create Another Document
        </button>
      </div>
    </div>
  );
}
