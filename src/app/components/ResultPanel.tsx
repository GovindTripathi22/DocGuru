"use client";

import React, { useEffect, useRef, useState } from "react";
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
  FileText,
  Presentation,
  Copy,
  Check,
  SlidersHorizontal,
} from "lucide-react";
import type { ResearchSource } from "@/types/template";

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

interface PreviewSectionItem {
  title: string;
  heading_style?: string;
  paragraphs?: string[];
  bullets?: string[];
  table_data?: {
    title?: string;
    headers: string[];
    rows: string[][];
  };
}

interface PreviewSlideItem {
  slide_number?: number;
  title: string;
  layout_name?: string;
  bullets?: string[];
  speaker_notes?: string;
}

export interface GenerationResultData {
  success: boolean;
  output_filename: string;
  download_url: string;
  generation_mode?: string;
  template_id?: string;
  plan_summary?: Array<{ title: string; layout?: string }>;
  plan?: {
    title?: string;
    sections?: PreviewSectionItem[];
    slides?: PreviewSlideItem[];
  };
  validation: ValidationReport;
  warnings?: string[];
  research_sources?: ResearchSource[];
  execution_time_sec?: number;
  timings?: Record<string, number>;
  model?: string;
}

interface ResultPanelProps {
  result: GenerationResultData;
  templateType: "docx" | "pptx" | "pdf";
  previewAvailable?: boolean;
  onReset: () => void;
  onEditPrompt?: () => void;
}

export function ResultPanel({
  result,
  templateType,
  previewAvailable = false,
  onReset,
  onEditPrompt,
}: ResultPanelProps) {
  const [revalidating, setRevalidating] = useState(false);
  const [reverifiedOverride, setReverifiedOverride] = useState<{
    filename: string;
    validation: ValidationReport;
  } | null>(null);
  const [reverifyMessage, setReverifyMessage] = useState<string | null>(null);
  const [activeItemIndex, setActiveItemIndex] = useState<number | "all">("all");
  const [copiedContent, setCopiedContent] = useState(false);
  const validationController = useRef<AbortController | null>(null);

  useEffect(() => () => validationController.current?.abort(), []);

  const currentVal =
    reverifiedOverride && reverifiedOverride.filename === result.output_filename
      ? reverifiedOverride.validation
      : result.validation;

  const valStatus = currentVal.status || (currentVal.passed ? "passed" : "failed");
  const isPdf = templateType === "pdf";

  const handleReverify = async () => {
    setRevalidating(true);
    setReverifyMessage(null);
    validationController.current?.abort();
    const controller = new AbortController();
    validationController.current = controller;
    try {
      const res = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          template_id: result.template_id,
          generated_filename: result.output_filename,
        }),
      });
      if (res.ok) {
        const valData: ValidationReport = await res.json();
        setReverifiedOverride({ filename: result.output_filename, validation: valData });
        setReverifyMessage("Validation re-verified against template package.");
      } else {
        setReverifyMessage("Re-validation request failed.");
      }
    } catch {
      if (!controller.signal.aborted) setReverifyMessage("Network error during re-verification.");
    } finally {
      if (validationController.current === controller) {
        validationController.current = null;
        setRevalidating(false);
      }
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
      detail:
        currentVal.header_footer_preserved === false
          ? "Header/footer drift"
          : "Header & footer preserved",
    },
    {
      name: "Master Layouts",
      status: currentVal.layout_drift_detected ? "changed" : "identical",
      detail: currentVal.layout_drift_detected
        ? "Layout geometry modified"
        : "Layout structures preserved",
    },
  ];

  const previewSections = result.plan?.sections || [];
  const previewSlides = result.plan?.slides || [];
  const hasDetailedPreview = previewSections.length > 0 || previewSlides.length > 0;

  const displayedSections =
    activeItemIndex === "all"
      ? previewSections
      : previewSections.filter((_, idx) => idx === activeItemIndex);

  const displayedSlides =
    activeItemIndex === "all"
      ? previewSlides
      : previewSlides.filter((_, idx) => idx === activeItemIndex);

  const handleCopyPreviewText = () => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    let text = "";
    if (previewSections.length > 0) {
      text = previewSections
        .map((s) => {
          const lines = [s.title, ...(s.paragraphs || [])];
          if (s.bullets?.length) {
            lines.push(...s.bullets.map((b) => `• ${b}`));
          }
          return lines.join("\n\n");
        })
        .join("\n\n---\n\n");
    } else if (previewSlides.length > 0) {
      text = previewSlides
        .map(
          (sl, idx) =>
            `Slide ${sl.slide_number ?? idx + 1}: ${sl.title}\n${(sl.bullets || [])
              .map((b) => `• ${b}`)
              .join("\n")}`,
        )
        .join("\n\n");
    } else if (result.plan_summary?.length) {
      text = result.plan_summary.map((item, idx) => `${idx + 1}. ${item.title}`).join("\n");
    }
    if (!text) return;
    void navigator.clipboard.writeText(text);
    setCopiedContent(true);
    setTimeout(() => setCopiedContent(false), 1800);
  };

  return (
    <div className="w-full space-y-5">
      {/* Status Banner */}
      <div
        className={`rounded-2xl border p-5 sm:p-6 backdrop-blur-xl shadow-lg transition-all ${
          isPdf
            ? "border-sky-300 bg-sky-50/90 text-sky-950"
            : valStatus === "passed"
            ? "border-emerald-300 bg-emerald-50/90 text-emerald-950"
            : "border-rose-300 bg-rose-50/90 text-rose-950"
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            {isPdf ? (
              <FileCheck className="h-6 w-6 text-sky-600 shrink-0" />
            ) : valStatus === "passed" ? (
              <CheckCircle2 className="h-6 w-6 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="h-6 w-6 text-rose-600 shrink-0" />
            )}
            <div>
              <h2 className="text-base font-bold text-slate-900">
                {isPdf
                  ? "Approximate layout (PDF reference mode)"
                  : valStatus === "passed"
                  ? "Template checks passed"
                  : "Template Drift Detected"}
              </h2>
              <p className="text-xs text-slate-600 font-medium mt-0.5">
                {isPdf
                  ? "Derived layout dimensions, typography, and margins from PDF structure."
                  : valStatus === "passed"
                  ? "No differences were detected in the template properties checked below."
                  : "One or more checked template properties differ in the generated file."}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {valStatus === "passed" || isPdf ? (
              <a
                href={result.download_url}
                download={result.output_filename}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 via-sky-500 to-cyan-500 px-4 py-2.5 text-xs font-bold text-white shadow-[0_0_16px_rgba(14,165,233,0.35)] hover:shadow-[0_0_24px_rgba(14,165,233,0.55)] hover:scale-[1.02] transition-all whitespace-nowrap shrink-0"
              >
                <Download className="h-4 w-4" /> Download Artifact
              </a>
            ) : (
              <div className="flex flex-col items-end gap-1">
                <button
                  disabled
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-500 cursor-not-allowed whitespace-nowrap shrink-0 shadow-sm"
                >
                  <Download className="h-4 w-4" /> Download Disabled (Drift Detected)
                </button>
                <a
                  href={result.download_url}
                  className="text-[11px] text-slate-500 hover:text-slate-800 underline font-medium"
                >
                  Download anyway for diagnostics
                </a>
              </div>
            )}

            <button
              onClick={handleReverify}
              disabled={revalidating}
              className="inline-flex items-center gap-1.5 rounded-xl border border-sky-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 hover:border-sky-400 hover:bg-sky-50 hover:text-sky-950 transition-colors disabled:opacity-50 whitespace-nowrap shrink-0 shadow-sm"
            >
              <RotateCcw
                className={`h-3.5 w-3.5 text-slate-500 motion-reduce:animate-none ${
                  revalidating ? "animate-spin" : ""
                }`}
              />{" "}
              Re-verify
            </button>

            {onEditPrompt && (
              <button
                type="button"
                onClick={onEditPrompt}
                className="inline-flex items-center gap-1.5 rounded-xl border border-sky-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 hover:border-sky-400 hover:bg-sky-50 hover:text-sky-950 transition-colors whitespace-nowrap shrink-0 shadow-sm"
              >
                <SlidersHorizontal className="h-3.5 w-3.5 text-sky-600" />
                Edit Prompt
              </button>
            )}
          </div>
        </div>

        {reverifyMessage && (
          <p className="mt-3 text-xs text-slate-600 font-medium border-t border-slate-200/80 pt-2">
            {reverifyMessage}
          </p>
        )}
      </div>

      {/* Metadata & Diagnostics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-sky-200/80 bg-white/80 p-3.5 space-y-1 shadow-sm">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            <Clock className="h-4 w-4 text-sky-600" /> Execution Time
          </div>
          <p className="text-sm font-bold text-slate-900 tabular-nums">
            {result.execution_time_sec ?? result.timings?.execution_time_sec ?? 0}s
          </p>
        </div>

        <div className="rounded-xl border border-sky-200/80 bg-white/80 p-3.5 space-y-1 shadow-sm">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            <Cpu className="h-4 w-4 text-sky-600" /> Model / Mode
          </div>
          <p className="text-sm font-bold text-slate-900">
            {result.model || "Configured Provider"}{" "}
            <span className="text-xs text-slate-500 font-normal">({result.generation_mode || "standard"})</span>
          </p>
        </div>

        <div className="rounded-xl border border-sky-200/80 bg-white/80 p-3.5 space-y-1 shadow-sm">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            <Layers className="h-4 w-4 text-sky-600" /> Planned Sections
          </div>
          <p className="text-sm font-bold text-slate-900 tabular-nums">
            {result.plan_summary?.length ?? 0} entries
          </p>
        </div>
      </div>

      {/* Preview availability */}
      {!previewAvailable && (
        <p className="rounded-xl border border-sky-200/80 bg-white/80 p-4 text-sm text-slate-700 shadow-sm font-medium">
          Inline preview is unavailable on this server. Download the artifact to review it in a
          compatible document or presentation app.
        </p>
      )}

      {/* Interactive Generated Content & Structure Inspector */}
      {(hasDetailedPreview || (result.plan_summary && result.plan_summary.length > 0)) && (
        <section className="rounded-2xl border border-sky-200/80 bg-white/90 shadow-[0_4px_25px_rgba(186,230,253,0.3)] overflow-hidden">
          <div className="px-5 py-3.5 border-b border-sky-200/80 bg-sky-50/50 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              {templateType === "pptx" ? (
                <Presentation className="h-4 w-4 text-amber-600" />
              ) : (
                <FileText className="h-4 w-4 text-sky-600" />
              )}
              <h3 className="text-sm font-bold text-slate-900">
                Generated {templateType === "pptx" ? "Presentation Slides" : "Document Structure"}
              </h3>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="text-xs text-slate-500 font-mono tabular-nums hidden sm:inline">
                {result.output_filename}
              </span>
              <button
                type="button"
                onClick={handleCopyPreviewText}
                className="inline-flex items-center gap-1.5 rounded-lg border border-sky-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-sky-300 hover:bg-sky-50 transition-colors shadow-sm"
              >
                {copiedContent ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5 text-slate-400" />
                    Copy text
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Interactive Section / Slide Filter Bar */}
          {(previewSections.length > 1 || previewSlides.length > 1) && (
            <div className="px-5 py-2.5 bg-sky-50/60 border-b border-sky-200/70 flex items-center gap-1.5 overflow-x-auto">
              <button
                type="button"
                onClick={() => setActiveItemIndex("all")}
                className={`rounded-lg px-2.5 py-1 text-xs font-bold transition-colors whitespace-nowrap shrink-0 ${
                  activeItemIndex === "all"
                    ? "bg-sky-600 text-white shadow-sm"
                    : "bg-white text-slate-600 hover:text-slate-900 border border-sky-200"
                }`}
              >
                All ({previewSections.length || previewSlides.length})
              </button>
              {(previewSections.length > 0 ? previewSections : previewSlides).map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  title={item.title}
                  onClick={() => setActiveItemIndex(idx)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap shrink-0 ${
                    activeItemIndex === idx
                      ? "bg-sky-600 text-white font-bold shadow-sm"
                      : "bg-white text-slate-600 hover:text-slate-900 border border-sky-200"
                  }`}
                >
                  <span className="block max-w-[180px] truncate">
                    {templateType === "pptx" ? `Slide ${idx + 1}: ${item.title}` : item.title}
                  </span>
                </button>
              ))}
            </div>
          )}

          {displayedSections.length > 0 ? (
            <div className="divide-y divide-sky-100 max-h-[440px] overflow-y-auto">
              {displayedSections.map((sec, idx) => (
                <div key={idx} className="p-5 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-bold text-slate-900">{sec.title}</h4>
                    {sec.heading_style && (
                      <span className="text-[11px] font-mono text-slate-500">
                        Style: {sec.heading_style}
                      </span>
                    )}
                  </div>
                  {sec.paragraphs?.map((para, pIdx) => (
                    <p key={pIdx} className="text-xs leading-relaxed text-slate-700">
                      {para}
                    </p>
                  ))}
                  {sec.bullets && sec.bullets.length > 0 && (
                    <ul className="list-disc pl-5 space-y-1 text-xs text-slate-700">
                      {sec.bullets.map((b, bIdx) => (
                        <li key={bIdx}>{b}</li>
                      ))}
                    </ul>
                  )}
                  {sec.table_data && (
                    <div className="mt-3 overflow-x-auto rounded-xl border border-sky-200 shadow-sm">
                      {sec.table_data.title && (
                        <div className="bg-sky-100/70 px-3.5 py-2 text-[11px] font-bold text-slate-800 border-b border-sky-200">
                          {sec.table_data.title}
                        </div>
                      )}
                      <table className="w-full text-left text-xs text-slate-700">
                        <thead className="bg-sky-50 text-[11px] uppercase text-slate-700 font-bold border-b border-sky-200">
                          <tr>
                            {sec.table_data.headers.map((h, hIdx) => (
                              <th key={hIdx} className="px-3.5 py-2 font-bold">
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-sky-100 tabular-nums">
                          {sec.table_data.rows.map((row, rIdx) => (
                            <tr key={rIdx} className="hover:bg-sky-50/60">
                              {row.map((cell, cIdx) => (
                                <td key={cIdx} className="px-3.5 py-2">
                                  {cell}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : displayedSlides.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-5">
              {displayedSlides.map((slide, idx) => (
                <div
                  key={idx}
                  className="rounded-xl border border-sky-200/80 bg-white p-4 space-y-2.5 flex flex-col justify-between shadow-sm"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2 text-[11px] text-slate-500 font-medium">
                      <span className="font-mono font-bold text-amber-700 tabular-nums">
                        Slide {slide.slide_number ?? idx + 1}
                      </span>
                      {slide.layout_name && <span>Layout: {slide.layout_name}</span>}
                    </div>
                    <h4 className="text-sm font-bold text-slate-900">{slide.title}</h4>
                    {slide.bullets && slide.bullets.length > 0 && (
                      <ul className="list-disc pl-4 space-y-1 text-xs text-slate-700">
                        {slide.bullets.map((b, bIdx) => (
                          <li key={bIdx}>{b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {slide.speaker_notes && (
                    <p className="pt-2 border-t border-sky-100 text-[11px] text-slate-500 font-medium">
                      Notes: {slide.speaker_notes}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="p-5 flex flex-wrap gap-2">
              {result.plan_summary?.map((item, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-sky-200 bg-sky-50/70 px-3 py-2 text-xs text-slate-800 shadow-sm"
                >
                  <span className="font-mono text-slate-400 mr-1.5 tabular-nums">{idx + 1}.</span>
                  <span className="font-semibold">{item.title}</span>
                  {item.layout && (
                    <span className="ml-2 text-[11px] text-slate-500">({item.layout})</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Components Verification Table */}
      <div className="rounded-2xl border border-sky-200/80 bg-white/90 shadow-[0_4px_25px_rgba(186,230,253,0.3)] overflow-hidden">
        <div className="px-5 py-3.5 border-b border-sky-200/80 bg-sky-50/50 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold text-slate-900">Component Verification Results</h3>
          <span className="text-xs text-slate-500 font-mono tabular-nums">
            Original: {currentVal.original_style_hash?.slice(0, 16) || "N/A"} • Generated:{" "}
            {currentVal.generated_style_hash?.slice(0, 16) || "N/A"}
          </span>
        </div>

        <div className="divide-y divide-sky-100">
          {components.map((comp, idx) => (
            <div key={idx} className="px-5 py-3 flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-800">{comp.name}</span>
              <div className="flex items-center gap-2.5">
                <span className="text-slate-500 font-medium">{comp.detail}</span>
                {comp.status === "identical" && (
                  <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-300 shadow-sm">
                    <CheckCircle2 className="h-3 w-3 text-emerald-600" /> Identical
                  </span>
                )}
                {comp.status === "intentional_override" && (
                  <span className="inline-flex items-center gap-1 rounded bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700 border border-sky-300 shadow-sm">
                    Override
                  </span>
                )}
                {comp.status === "changed" && (
                  <span className="inline-flex items-center gap-1 rounded bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-300 shadow-sm">
                    <AlertCircle className="h-3 w-3 text-rose-600" /> Changed
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Issues list if any */}
      {currentVal.issues && currentVal.issues.length > 0 && (
        <div className="rounded-2xl border border-rose-300 bg-rose-50 p-5 space-y-2 text-xs text-rose-900 shadow-sm">
          <div className="flex items-center gap-2 font-bold text-rose-800">
            <AlertCircle className="h-4 w-4 text-rose-600" /> Detected Invariant Issues ({currentVal.issues.length})
          </div>
          <ul className="list-disc pl-5 space-y-1">
            {currentVal.issues.map((issue, idx) => (
              <li key={idx}>{issue}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Research sources if any */}
      {result.research_sources && result.research_sources.length > 0 && (
        <section className="rounded-2xl border border-sky-200 bg-sky-50/70 p-5 space-y-3 text-xs text-slate-800 shadow-sm">
          <h3 className="font-bold text-sky-900">Research sources</h3>
          <ol className="list-decimal space-y-2 pl-5">
            {result.research_sources.map((source) => (
              <li key={source.id} className="pl-1">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-semibold text-sky-700 underline decoration-sky-400 underline-offset-2 hover:text-sky-950"
                >
                  {source.title}
                </a>
                {source.published_date && (
                  <span className="ml-1 text-slate-500 tabular-nums font-normal">({source.published_date})</span>
                )}
                <div className="break-all text-[10px] text-slate-400">{source.url}</div>
              </li>
            ))}
          </ol>
          <p className="text-[11px] text-slate-500 font-medium">
            Sources were retrieved for this document and were not independently verified.
          </p>
        </section>
      )}

      {/* Warnings if any */}
      {(() => {
        const visibleWarnings = (result.warnings || []).filter(
          (w) =>
            !w.startsWith("long_sentence_split_at_") &&
            !w.startsWith("heading_style_fallback:") &&
            !w.startsWith("paragraph_style_fallback:"),
        );
        if (visibleWarnings.length === 0) return null;
        return (
          <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 space-y-2 text-xs text-amber-900 shadow-sm">
            <div className="flex items-center gap-2 font-bold text-amber-800">
              <AlertTriangle className="h-4 w-4 text-amber-600" /> Warnings
            </div>
            <ul className="list-disc pl-5 space-y-1">
              {visibleWarnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>
        );
      })()}

      <div className="flex flex-wrap items-center justify-end gap-3">
        {onEditPrompt && (
          <button
            type="button"
            onClick={onEditPrompt}
            className="rounded-xl border border-sky-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:border-sky-300 hover:bg-sky-50 transition-colors shadow-sm"
          >
            Edit Prompt & Regenerate
          </button>
        )}
        <button
          onClick={onReset}
          className="rounded-xl border border-sky-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:border-sky-300 hover:bg-sky-50 transition-colors shadow-sm"
        >
          Create Another Document
        </button>
      </div>
    </div>
  );
}
