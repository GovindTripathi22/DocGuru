"use client";

import React from "react";
import { FileText, Presentation, FileCode } from "lucide-react";
import { TemplateSpec } from "@/types/template";

interface TemplateLockDisplayProps {
  spec: TemplateSpec;
}

export function TemplateLockDisplay({ spec }: TemplateLockDisplayProps) {
  const isDocx = spec.document_type === "docx";
  const isPptx = spec.document_type === "pptx";
  const isPdf = spec.document_type === "pdf";

  const getDimensionDetail = (): string | undefined => {
    if (isDocx && spec.page) {
      const margins = spec.page.margins;
      return `${spec.page.width_pt} × ${spec.page.height_pt} pt, ${spec.page.orientation}; margins T ${margins.top_pt}, R ${margins.right_pt}, B ${margins.bottom_pt}, L ${margins.left_pt} pt`;
    }
    if (isPptx && spec.slide_dimensions) {
      return `${spec.slide_dimensions.width_inches}" x ${spec.slide_dimensions.height_inches}" (${spec.slide_dimensions.aspect_ratio})`;
    }
    if (isPdf && spec.page) {
      return `${spec.page.width_pt}x${spec.page.height_pt} pt (PDF Reference)`;
    }
    return undefined;
  };

  const detectedItems: Array<{ name: string; detail: string }> = [];
  const fontNames = [...new Set([
    ...(spec.fonts?.all_detected_fonts || []),
    spec.fonts?.default,
    spec.fonts?.body,
    spec.fonts?.heading1,
    spec.fonts?.heading2,
    spec.theme?.font_scheme?.major_font,
    spec.theme?.font_scheme?.minor_font,
  ].filter((font): font is string => typeof font === "string" && font.trim().length > 0))];
  if (fontNames.length > 0) detectedItems.push({ name: "Fonts found", detail: fontNames.join(", ") });

  const dimensions = getDimensionDetail();
  if (dimensions) {
    detectedItems.push({
      name: isDocx ? "Page size and margins" : isPptx ? "Slide dimensions" : "PDF reference geometry",
      detail: dimensions,
    });
  }

  const themeColors = Object.entries(spec.theme?.color_scheme || {})
    .filter((entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].length > 0)
    .map(([name, color]) => `${name}: ${color}`);
  if (themeColors.length > 0) detectedItems.push({ name: "Theme colors", detail: themeColors.join(", ") });

  if (spec.header) {
    detectedItems.push({
      name: "Header",
      detail: spec.header.has_content ? spec.header.text_preview || "Content found" : "No content detected",
    });
  }
  if (spec.footer) {
    detectedItems.push({
      name: "Footer",
      detail: spec.footer.has_content ? spec.footer.text_preview || "Content found" : "No content detected",
    });
  }
  if (isDocx && spec.available_heading_styles) {
    detectedItems.push({
      name: "Heading styles",
      detail: spec.available_heading_styles.length ? spec.available_heading_styles.join(", ") : "None found",
    });
  }
  if (isPptx && spec.available_layout_names) {
    detectedItems.push({
      name: "Slide layouts",
      detail: spec.available_layout_names.length ? spec.available_layout_names.join(", ") : "None found",
    });
  }
  if (spec.table_rules) {
    detectedItems.push({ name: "Tables found", detail: String(spec.table_rules.length) });
  }

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div className="flex items-center gap-3.5">
          <div
            className={`flex h-12 w-12 items-center justify-center rounded-xl border ${
              isDocx
                ? "border-cyan-500/40 bg-cyan-950/40 text-cyan-400"
                : isPptx
                ? "border-amber-500/40 bg-amber-950/40 text-amber-400"
                : "border-indigo-500/40 bg-indigo-950/40 text-indigo-400"
            }`}
          >
            {isDocx && <FileText className="h-6 w-6" />}
            {isPptx && <Presentation className="h-6 w-6" />}
            {isPdf && <FileCode className="h-6 w-6" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-white text-base">{spec.filename}</h3>
              <span className="rounded-md bg-zinc-800 border border-zinc-700 px-2 py-0.5 text-xs font-medium uppercase text-zinc-300">
                {spec.document_type}
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {isDocx
                ? "DOCX template"
                : isPptx
                ? "PPTX template"
                : "PDF reference"}{" "}
              {spec.style_hash && <>• Style fingerprint:{" "}</>}
              {spec.style_hash && (
              <code className="font-mono text-zinc-300 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                {spec.style_hash}
              </code>
              )}
            </p>
          </div>
        </div>

        <div className="rounded-xl bg-zinc-900 px-3.5 py-2 text-zinc-300 border border-zinc-800">
          <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Source properties</div>
          <div className="text-[11px] text-zinc-400 font-normal">Values reported by the template analyzer</div>
        </div>
      </div>

      <div className="mt-5">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Template properties found
        </h4>

        {detectedItems.length > 0 ? (
          <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {detectedItems.map((item) => (
              <div
                key={item.name}
                className="flex items-start gap-2.5 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3"
              >
                <span aria-hidden="true" className="mt-1 h-2 w-2 shrink-0 rounded-full bg-cyan-400" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-white">{item.name}</span>
                    <span className="inline-flex items-center rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400 border border-zinc-700">
                      From template
                    </span>
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-zinc-400">{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-xs text-zinc-400">The analyzer did not report additional template properties.</p>
        )}
      </div>

      {/* Extracted Document Rules */}
      {spec.extracted_rules && spec.extracted_rules.length > 0 && (
        <details className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-3.5 text-xs text-zinc-300 group">
          <summary className="font-medium flex items-center justify-between cursor-pointer list-none select-none text-zinc-200">
            <span className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800 text-[11px] text-zinc-300 font-bold">
                {spec.extracted_rules.length}
              </span>
              Extracted Formatting Guidelines & Notes
            </span>
            <span className="text-[11px] text-zinc-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-3 max-h-48 overflow-y-auto space-y-1.5 pr-2 pt-2 border-t border-zinc-800">
            {spec.extracted_rules.map((rule, rIdx) => (
              <div
                key={rIdx}
                className="flex items-start gap-2 text-[11px] text-zinc-300 bg-zinc-900 p-2 rounded-lg border border-zinc-800"
              >
                <span className="text-indigo-400 font-bold">•</span>
                <span>{rule}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Existing Outline */}
      {spec.document_outline && spec.document_outline.length > 0 && (
        <details className="mt-3 rounded-xl border border-zinc-800 bg-zinc-900/30 p-3.5 text-xs text-zinc-300 group">
          <summary className="font-medium flex items-center justify-between cursor-pointer list-none select-none text-zinc-200">
            <span className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800 text-[11px] text-zinc-300 font-bold">
                {spec.document_outline.length}
              </span>
              Detected Heading Outline
            </span>
            <span className="text-[11px] text-zinc-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-3 max-h-40 overflow-y-auto flex flex-wrap gap-1.5 pt-2 border-t border-zinc-800">
            {spec.document_outline.map((heading, hIdx) => (
              <span key={hIdx} className="text-[11px] bg-zinc-900 border border-zinc-800 text-zinc-300 px-2 py-1 rounded-md">
                {heading}
              </span>
            ))}
          </div>
        </details>
      )}

      {isPdf && (
        <div className="mt-4 rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-3 text-xs text-cyan-200">
          <strong>PDF Reference Mode:</strong> Page dimensions, dominant fonts, and heading sizes are measured and applied to a generated DOCX base. Visual layout is approximate.
        </div>
      )}
    </div>
  );
}
