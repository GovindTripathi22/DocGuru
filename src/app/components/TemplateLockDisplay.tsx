"use client";

import React, { useState } from "react";
import {
  FileText,
  Presentation,
  FileCode,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  ShieldCheck,
} from "lucide-react";
import { TemplateSpec } from "@/types/template";

interface TemplateLockDisplayProps {
  spec: TemplateSpec;
  onReset?: () => void;
}

export function TemplateLockDisplay({ spec, onReset }: TemplateLockDisplayProps) {
  const [showDetails, setShowDetails] = useState(true);
  const [copiedHash, setCopiedHash] = useState(false);

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
  const fontNames = [
    ...new Set(
      [
        ...(spec.fonts?.all_detected_fonts || []),
        spec.fonts?.default,
        spec.fonts?.body,
        spec.fonts?.heading1,
        spec.fonts?.heading2,
        spec.theme?.font_scheme?.major_font,
        spec.theme?.font_scheme?.minor_font,
      ].filter((font): font is string => typeof font === "string" && font.trim().length > 0),
    ),
  ];
  if (fontNames.length > 0) {
    detectedItems.push({ name: "Fonts found", detail: fontNames.join(", ") });
  }

  const dimensions = getDimensionDetail();
  if (dimensions) {
    detectedItems.push({
      name: isDocx
        ? "Page size and margins"
        : isPptx
        ? "Slide dimensions"
        : "PDF reference geometry",
      detail: dimensions,
    });
  }

  const themeColorEntries = Object.entries(spec.theme?.color_scheme || {}).filter(
    (entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].length > 0,
  );
  const themeColors = themeColorEntries.map(([name, color]) => `${name}: ${color}`);
  if (themeColors.length > 0) {
    detectedItems.push({ name: "Theme colors", detail: themeColors.join(", ") });
  }

  if (spec.header) {
    detectedItems.push({
      name: "Header",
      detail: spec.header.has_content
        ? spec.header.text_preview || "Content found"
        : "No content detected",
    });
  }
  if (spec.footer) {
    detectedItems.push({
      name: "Footer",
      detail: spec.footer.has_content
        ? spec.footer.text_preview || "Content found"
        : "No content detected",
    });
  }
  if (isDocx && spec.available_heading_styles) {
    detectedItems.push({
      name: "Heading styles",
      detail: spec.available_heading_styles.length
        ? spec.available_heading_styles.join(", ")
        : "None found",
    });
  }
  if (isPptx && spec.available_layout_names) {
    detectedItems.push({
      name: "Slide layouts",
      detail: spec.available_layout_names.length
        ? spec.available_layout_names.join(", ")
        : "None found",
    });
  }
  if (spec.table_rules) {
    detectedItems.push({ name: "Tables found", detail: String(spec.table_rules.length) });
  }
  if (spec.has_embedded_rules && spec.parsed_typography_rules) {
    const typo = spec.parsed_typography_rules as Record<string, unknown>;
    const body = typo.body as Record<string, unknown> | undefined;
    const h1 = typo.heading1 as Record<string, unknown> | undefined;
    const fontFamily =
      (typeof typo.font_family === "string" ? typo.font_family : null) ||
      (typeof h1?.font_name === "string" ? h1.font_name : null) ||
      (typeof body?.font_name === "string" ? body.font_name : null);
    const h1Size =
      typeof h1?.size_pt === "number"
        ? h1.size_pt
        : typeof typo.heading1_size_pt === "number"
        ? typo.heading1_size_pt
        : null;
    const bodySize =
      typeof body?.size_pt === "number"
        ? body.size_pt
        : typeof typo.body_size_pt === "number"
        ? typo.body_size_pt
        : null;
    const lineSpacing =
      typeof body?.line_spacing === "number"
        ? body.line_spacing
        : typeof typo.line_spacing === "number"
        ? typo.line_spacing
        : null;
    const summaryParts = [
      fontFamily,
      h1Size !== null ? `H1 ${h1Size}pt` : null,
      bodySize !== null ? `Body ${bodySize}pt` : null,
      lineSpacing !== null ? `${lineSpacing}x spacing` : null,
    ].filter(Boolean);
    if (summaryParts.length > 0) {
      detectedItems.push({
        name: "Document rule spec",
        detail: summaryParts.join(" · "),
      });
    }
  }

  const handleCopyHash = () => {
    if (!spec.style_hash || typeof navigator === "undefined" || !navigator.clipboard) return;
    void navigator.clipboard.writeText(spec.style_hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 1800);
  };

  return (
    <div className="rounded-2xl border border-sky-200/80 bg-white/90 p-4 sm:p-5 shadow-[0_4px_25px_rgba(186,230,253,0.3)] backdrop-blur-2xl space-y-3 transition-all duration-300">
      {/* Friendly Template Badge & Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-11 w-11 items-center justify-center rounded-xl border shrink-0 ${
              isDocx
                ? "border-sky-300 bg-sky-50 text-sky-700 shadow-sm"
                : isPptx
                ? "border-amber-300 bg-amber-50 text-amber-700 shadow-sm"
                : "border-rose-300 bg-rose-50 text-rose-700 shadow-sm"
            }`}
          >
            {isDocx && <FileText className="h-5 w-5" />}
            {isPptx && <Presentation className="h-5 w-5" />}
            {isPdf && <FileCode className="h-5 w-5" />}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-bold text-slate-900 text-sm sm:text-base">{spec.filename}</h3>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-300 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700 shadow-[0_0_10px_rgba(16,185,129,0.18)]">
                <ShieldCheck className="h-3 w-3 text-emerald-600" />
                Template Locked
              </span>
              {spec.has_embedded_rules && (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 border border-sky-300 px-2.5 py-0.5 text-[10px] font-bold text-sky-800">
                  Embedded Rules Detected
                </span>
              )}
              <span className="rounded bg-sky-100/90 border border-sky-200 px-1.5 py-0.5 text-[10px] font-bold uppercase text-sky-800">
                {spec.document_type}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              {isDocx
                ? "Word Document template"
                : isPptx
                ? "PowerPoint presentation template"
                : "PDF reference format"}
              {spec.total_pages_or_slides > 0 &&
                ` · ${spec.total_pages_or_slides} ${
                  isPptx
                    ? spec.total_pages_or_slides === 1
                      ? "slide"
                      : "slides"
                    : spec.total_pages_or_slides === 1
                    ? "page"
                    : "pages"
                }`}
              {" · Design properties locked to template"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowDetails((prev) => !prev)}
            aria-expanded={showDetails}
            className="inline-flex items-center gap-1.5 rounded-xl border border-sky-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-sky-400 hover:bg-sky-50 hover:text-sky-950 transition-colors whitespace-nowrap shadow-sm"
          >
            {showDetails ? (
              <>
                <ChevronUp className="h-3.5 w-3.5 text-slate-500" />
                Compact view
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5 text-slate-500" />
                Inspect properties ({detectedItems.length})
              </>
            )}
          </button>

          {onReset && (
            <button
              type="button"
              onClick={onReset}
              className="inline-flex items-center gap-1.5 rounded-xl border border-sky-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-sky-400 hover:bg-sky-50 hover:text-sky-950 transition-colors whitespace-nowrap shadow-sm shrink-0"
            >
              <RotateCcw className="h-3.5 w-3.5 text-slate-500" />
              Change template
            </button>
          )}
        </div>
      </div>

      {/* Collapsible Detected Technical Properties (Clean & Organized) */}
      {showDetails && (
        <div className="border-t border-sky-200/70 pt-3 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-700">Template properties found</h4>
            {spec.style_hash && (
              <button
                type="button"
                onClick={handleCopyHash}
                title="Copy style fingerprint"
                className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-slate-600 hover:text-slate-900 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 shadow-sm"
              >
                Fingerprint: {spec.style_hash}
                {copiedHash ? (
                  <Check className="h-2.5 w-2.5 text-emerald-600" />
                ) : (
                  <Copy className="h-2.5 w-2.5 text-slate-400" />
                )}
              </button>
            )}
          </div>

          {detectedItems.length > 0 ? (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {detectedItems.map((item) => (
                <div
                  key={item.name}
                  className="rounded-xl border border-sky-200/70 bg-white/80 p-2.5 shadow-sm"
                >
                  <span className="text-[11px] font-bold text-slate-800 block">{item.name}</span>
                  <p
                    title={item.detail}
                    className="mt-0.5 text-xs text-slate-600 font-medium leading-snug truncate"
                  >
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">
              The analyzer did not report additional template properties.
            </p>
          )}

          {/* Extracted Rules & Outline Row */}
          {((spec.extracted_rules && spec.extracted_rules.length > 0) ||
            (spec.document_outline && spec.document_outline.length > 0)) && (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 pt-1">
              {spec.extracted_rules && spec.extracted_rules.length > 0 && (
                <details className="rounded-xl border border-sky-200 bg-white/80 p-2.5 text-xs text-slate-700 shadow-sm group">
                  <summary className="font-bold flex items-center justify-between cursor-pointer list-none select-none text-slate-800 text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="text-sky-600 font-bold tabular-nums">
                        [{spec.extracted_rules.length}]
                      </span>
                      Extracted Formatting Rules
                    </span>
                    <span className="text-[11px] text-slate-400 group-open:rotate-180 transition-transform">
                      ▼
                    </span>
                  </summary>
                  <div className="mt-2 max-h-36 overflow-y-auto space-y-1 pr-1 pt-1.5 border-t border-sky-200/60">
                    {spec.extracted_rules.map((rule, rIdx) => (
                      <div
                        key={rIdx}
                        className="text-[11px] text-slate-700 font-medium bg-sky-50/70 p-1.5 rounded border border-sky-100"
                      >
                        • {rule}
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {spec.document_outline && spec.document_outline.length > 0 && (
                <details className="rounded-xl border border-sky-200 bg-white/80 p-2.5 text-xs text-slate-700 shadow-sm group">
                  <summary className="font-bold flex items-center justify-between cursor-pointer list-none select-none text-slate-800 text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="text-cyan-600 font-bold tabular-nums">
                        [{spec.document_outline.length}]
                      </span>
                      Detected Heading Outline
                    </span>
                    <span className="text-[11px] text-slate-400 group-open:rotate-180 transition-transform">
                      ▼
                    </span>
                  </summary>
                  <div className="mt-2 max-h-36 overflow-y-auto flex flex-wrap gap-1 pt-1.5 border-t border-sky-200/60">
                    {spec.document_outline.map((heading, hIdx) => (
                      <span
                        key={hIdx}
                        className="text-[11px] bg-sky-50 border border-sky-200 text-slate-700 font-medium px-2 py-0.5 rounded shadow-sm"
                      >
                        {heading}
                      </span>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      )}

      {isPdf && (
        <div className="rounded-xl border border-sky-300 bg-sky-50 p-2.5 text-xs text-sky-900 shadow-sm">
          <strong>PDF Reference Mode:</strong> Page dimensions, dominant fonts, and heading sizes
          are measured and applied to a generated DOCX base. Visual layout is approximate.
        </div>
      )}
    </div>
  );
}
