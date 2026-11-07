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

  const handleCopyHash = () => {
    if (!spec.style_hash || typeof navigator === "undefined" || !navigator.clipboard) return;
    void navigator.clipboard.writeText(spec.style_hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 1800);
  };

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/90 p-5 backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-11 w-11 items-center justify-center rounded-xl border ${
              isDocx
                ? "border-cyan-500/40 bg-cyan-950/40 text-cyan-400"
                : isPptx
                ? "border-amber-500/40 bg-amber-950/40 text-amber-400"
                : "border-indigo-500/40 bg-indigo-950/40 text-indigo-400"
            }`}
          >
            {isDocx && <FileText className="h-5 w-5" />}
            {isPptx && <Presentation className="h-5 w-5" />}
            {isPdf && <FileCode className="h-5 w-5" />}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-bold text-white text-sm sm:text-base">{spec.filename}</h3>
              <span className="rounded bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-zinc-300">
                {spec.document_type}
              </span>
              {themeColorEntries.length > 0 && (
                <div
                  className="hidden sm:flex items-center gap-1 ml-1"
                  title="Detected theme palette"
                >
                  {themeColorEntries.slice(0, 5).map(([name, hex]) => (
                    <span
                      key={name}
                      title={`${name}: ${hex}`}
                      className="h-3 w-3 rounded-sm border border-white/20"
                      style={{ backgroundColor: hex.startsWith("#") ? hex : `#${hex}` }}
                    />
                  ))}
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-zinc-400 mt-0.5 tabular-nums">
              <span>{isDocx ? "DOCX template" : isPptx ? "PPTX template" : "PDF reference"}</span>
              {spec.total_pages_or_slides > 0 && (
                <span>
                  · {spec.total_pages_or_slides}{" "}
                  {isPptx
                    ? spec.total_pages_or_slides === 1
                      ? "slide"
                      : "slides"
                    : spec.total_pages_or_slides === 1
                    ? "page"
                    : "pages"}
                </span>
              )}
              {spec.style_hash && (
                <span className="inline-flex items-center gap-1">
                  · Fingerprint:{" "}
                  <button
                    type="button"
                    onClick={handleCopyHash}
                    title="Copy style hash"
                    className="inline-flex items-center gap-1 font-mono text-[11px] text-zinc-300 bg-zinc-900 hover:bg-zinc-800 px-1.5 py-0.5 rounded border border-zinc-800 transition-colors"
                  >
                    {spec.style_hash}
                    {copiedHash ? (
                      <Check className="h-2.5 w-2.5 text-emerald-400" />
                    ) : (
                      <Copy className="h-2.5 w-2.5 text-zinc-500" />
                    )}
                  </button>
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowDetails((prev) => !prev)}
            aria-expanded={showDetails}
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-900/70 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:border-zinc-700 hover:bg-zinc-800 hover:text-white transition-colors whitespace-nowrap"
          >
            {showDetails ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                Compact view
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                Inspect properties ({detectedItems.length})
              </>
            )}
          </button>

          {onReset && (
            <button
              type="button"
              onClick={onReset}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:border-zinc-700 hover:bg-zinc-800 hover:text-white transition-colors whitespace-nowrap shrink-0"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Change template
            </button>
          )}
        </div>
      </div>

      {showDetails && (
        <div className="mt-4 border-t border-zinc-800/80 pt-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-zinc-400">Template properties found</h4>
            <span className="text-[11px] text-zinc-500">
              Values reported by the template analyzer
            </span>
          </div>

          {detectedItems.length > 0 ? (
            <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {detectedItems.map((item) => (
                <div
                  key={item.name}
                  className="flex flex-col justify-between rounded-xl border border-zinc-800/90 bg-zinc-900/40 p-2.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold text-zinc-200">{item.name}</span>
                    <span className="text-[10px] text-zinc-500">From template</span>
                  </div>
                  <p
                    title={item.detail}
                    className="mt-1 break-words text-xs leading-snug text-zinc-300 tabular-nums line-clamp-2"
                  >
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2.5 text-xs text-zinc-400">
              The analyzer did not report additional template properties.
            </p>
          )}

          {/* Extracted Rules & Outline Row */}
          {((spec.extracted_rules && spec.extracted_rules.length > 0) ||
            (spec.document_outline && spec.document_outline.length > 0)) && (
            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {spec.extracted_rules && spec.extracted_rules.length > 0 && (
                <details className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-3 text-xs text-zinc-300 group">
                  <summary className="font-medium flex items-center justify-between cursor-pointer list-none select-none text-zinc-200">
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs text-indigo-400 font-semibold tabular-nums">
                        [{spec.extracted_rules.length}]
                      </span>
                      Extracted Formatting Guidelines & Notes
                    </span>
                    <span className="text-[11px] text-zinc-400 group-open:rotate-180 transition-transform">
                      ▼
                    </span>
                  </summary>
                  <div className="mt-2.5 max-h-40 overflow-y-auto space-y-1.5 pr-1 pt-2 border-t border-zinc-800">
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

              {spec.document_outline && spec.document_outline.length > 0 && (
                <details className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-3 text-xs text-zinc-300 group">
                  <summary className="font-medium flex items-center justify-between cursor-pointer list-none select-none text-zinc-200">
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs text-cyan-400 font-semibold tabular-nums">
                        [{spec.document_outline.length}]
                      </span>
                      Detected Heading Outline
                    </span>
                    <span className="text-[11px] text-zinc-400 group-open:rotate-180 transition-transform">
                      ▼
                    </span>
                  </summary>
                  <div className="mt-2.5 max-h-40 overflow-y-auto flex flex-wrap gap-1.5 pt-2 border-t border-zinc-800">
                    {spec.document_outline.map((heading, hIdx) => (
                      <span
                        key={hIdx}
                        className="text-[11px] bg-zinc-900 border border-zinc-800 text-zinc-300 px-2 py-1 rounded-md"
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
        <div className="mt-3 rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-3 text-xs text-cyan-200">
          <strong>PDF Reference Mode:</strong> Page dimensions, dominant fonts, and heading sizes
          are measured and applied to a generated DOCX base. Visual layout is approximate.
        </div>
      )}
    </div>
  );
}
