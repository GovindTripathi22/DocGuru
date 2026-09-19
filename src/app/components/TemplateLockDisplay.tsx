"use client";

import React from "react";
import { CheckCircle2, Lock, FileText, Presentation, FileCode, ShieldCheck } from "lucide-react";
import { TemplateSpec } from "@/types/template";

interface TemplateLockDisplayProps {
  spec: TemplateSpec;
}

export function TemplateLockDisplay({ spec }: TemplateLockDisplayProps) {
  const isDocx = spec.document_type === "docx";
  const isPptx = spec.document_type === "pptx";
  const isPdf = spec.document_type === "pdf";

  const getDimensionDetail = () => {
    if (isDocx && spec.page) {
      return `${spec.page.width_pt}x${spec.page.height_pt} pt (${spec.page.orientation || 'portrait'})`;
    }
    if (isPptx && spec.slide_dimensions) {
      return `${spec.slide_dimensions.width_inches}" x ${spec.slide_dimensions.height_inches}" (${spec.slide_dimensions.aspect_ratio})`;
    }
    if (isPdf && spec.page) {
      return `${spec.page.width_pt}x${spec.page.height_pt} pt (PDF Reference)`;
    }
    return "Standard Layout";
  };

  const lockItems = [
    { name: "Typography & Fonts", status: "LOCKED", detail: spec.fonts?.all_detected_fonts?.join(", ") || spec.fonts?.default || "Preserved" },
    { name: "Theme & Palette", status: "LOCKED", detail: "Exact RGB & Accent Hex values locked" },
    { name: "Sacred Borders", status: "LOCKED", detail: "Paragraph, table & page borders immutable" },
    { name: isDocx ? "Page Margins & Size" : isPptx ? "Slide Dimensions" : "Page Geometry", status: "LOCKED", detail: getDimensionDetail() },
    { name: "Headers & Footers", status: "LOCKED", detail: spec.header?.has_content || spec.footer?.has_content ? "Pre-configured institutional links preserved" : "Package structure locked" },
    { name: isDocx ? "Heading Styles" : isPptx ? "Slide Master & Layouts" : "Visual Structure", status: "LOCKED", detail: isDocx ? (spec.available_heading_styles?.join(", ") || "Standard hierarchy") : isPptx ? `${spec.available_layout_names?.length || 0} layouts inherited` : "Reconstructed structure" },
    { name: "Table Shading & Grid", status: "LOCKED", detail: `${spec.table_rules?.length || 0} table structures detected & clonable` },
  ];

  return (
    <div className="rounded-2xl border border-cyan-500/20 bg-zinc-950/80 p-6 shadow-2xl backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div className="flex items-center gap-3.5">
          <div className={`flex h-12 w-12 items-center justify-center rounded-xl border ${
            isDocx ? "border-cyan-500/40 bg-cyan-950/60 text-cyan-400 shadow-md shadow-cyan-500/20" :
            isPptx ? "border-amber-500/40 bg-amber-950/60 text-amber-400 shadow-md shadow-amber-500/20" :
            "border-rose-500/40 bg-rose-950/60 text-rose-400 shadow-md shadow-rose-500/20"
          }`}>
            {isDocx && <FileText className="h-6 w-6" />}
            {isPptx && <Presentation className="h-6 w-6" />}
            {isPdf && <FileCode className="h-6 w-6" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-white text-base">
                {spec.filename}
              </h3>
              <span className="rounded-md bg-zinc-800 border border-zinc-700 px-2 py-0.5 text-xs font-semibold uppercase text-cyan-300">
                {spec.document_type}
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              {isDocx ? `${spec.total_pages_or_slides} Section(s)` : isPptx ? `${spec.total_pages_or_slides} Slide(s)` : `${spec.total_pages_or_slides} Page(s)`} • Style Hash: <code className="font-mono text-cyan-400 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">{spec.style_hash}</code>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 rounded-xl bg-emerald-950/80 px-3.5 py-2 text-emerald-400 border border-emerald-500/40 shadow-xs shadow-emerald-500/20">
          <ShieldCheck className="h-5 w-5 text-emerald-400" />
          <div className="text-left">
            <div className="text-xs font-bold leading-tight uppercase tracking-wider">Template Invariant Lock</div>
            <div className="text-[11px] text-emerald-300/80 font-medium">All formatting immutable • Content-only generation</div>
          </div>
        </div>
      </div>

      <div className="mt-5">
        <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
          <Lock className="h-3.5 w-3.5 text-cyan-400" />
          Enforced Template Invariants
        </h4>

        <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {lockItems.map((item, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2.5 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-3 transition-all hover:border-cyan-500/40 hover:bg-zinc-900/90"
            >
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">
                    {item.name}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-bold tracking-wider text-emerald-400 border border-zinc-700">
                    <Lock className="h-2.5 w-2.5" />
                    {item.status}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-[11px] text-zinc-400">
                  {item.detail}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Extracted Document Rules & Guidelines */}
      {spec.extracted_rules && spec.extracted_rules.length > 0 && (
        <details className="mt-4 rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-3.5 text-xs text-cyan-200 group">
          <summary className="font-bold flex items-center justify-between cursor-pointer list-none select-none text-cyan-300">
            <span className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan-500/20 text-[11px] text-cyan-400 font-extrabold">
                {spec.extracted_rules.length}
              </span>
              Embedded Document Rules & Formatting Guidelines Detected
            </span>
            <span className="text-[11px] text-cyan-400/80 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-3 max-h-48 overflow-y-auto space-y-1.5 pr-2 pt-2 border-t border-cyan-500/20">
            {spec.extracted_rules.map((rule, rIdx) => (
              <div key={rIdx} className="flex items-start gap-2 text-[11px] text-zinc-300 bg-zinc-900/50 p-2 rounded-lg border border-zinc-800">
                <span className="text-cyan-400 font-bold">•</span>
                <span>{rule}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Existing Document Outline */}
      {spec.document_outline && spec.document_outline.length > 0 && (
        <details className="mt-3 rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-3.5 text-xs text-indigo-200 group">
          <summary className="font-bold flex items-center justify-between cursor-pointer list-none select-none text-indigo-300">
            <span className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500/20 text-[11px] text-indigo-400 font-extrabold">
                {spec.document_outline.length}
              </span>
              Existing Document Chapters & Landmarks
            </span>
            <span className="text-[11px] text-indigo-400/80 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-3 max-h-40 overflow-y-auto flex flex-wrap gap-1.5 pt-2 border-t border-indigo-500/20">
            {spec.document_outline.map((heading, hIdx) => (
              <span key={hIdx} className="text-[11px] bg-zinc-900 border border-zinc-700 text-zinc-300 px-2 py-1 rounded-md">
                {heading}
              </span>
            ))}
          </div>
        </details>
      )}

      {isPdf && (
        <div className="mt-4 rounded-xl border border-amber-500/40 bg-amber-950/30 p-3 text-xs text-amber-300">
          <strong>Visual Reference Notice:</strong> This PDF was parsed for visual reference and layout reconstruction. For guaranteed 100% byte-for-byte editable template inheritance, providing the original DOCX or PPTX is strongly recommended.
        </div>
      )}
    </div>
  );
}
