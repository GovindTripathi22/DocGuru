"use client";

import React, { useEffect, useRef, useState } from "react";
import { Sparkles, ArrowRight, Wand2, Sliders, X, CheckCircle, ChevronDown, ChevronUp } from "lucide-react";
import { GenerationMode, PromptData } from "@/types/template";

interface PromptInputProps {
  documentType: "docx" | "pptx" | "pdf";
  researchAvailable: boolean;
  researchCapabilityKnown: boolean;
  imageSearchAvailable?: boolean;
  placeholdersAvailable?: boolean;
  onGenerate: (data: PromptData) => void;
  isGenerating: boolean;
  extractedRules?: string[];
  documentOutline?: string[];
  initialPrompt?: string;
}

export function PromptInput({
  documentType,
  researchAvailable,
  researchCapabilityKnown,
  imageSearchAvailable,
  placeholdersAvailable,
  onGenerate,
  isGenerating,
  extractedRules,
  documentOutline,
  initialPrompt = "",
}: PromptInputProps) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [mode, setMode] = useState<GenerationMode>(
    documentType === "pptx" ? "create_presentation" : "create_document",
  );
  const [targetSlides, setTargetSlides] = useState<number | string>(5);
  const [lengthMode, setLengthMode] = useState<"pages" | "detail">("detail");
  const [targetPages, setTargetPages] = useState<number | string>(5);
  const [detailLevel, setDetailLevel] = useState<"low" | "medium" | "high">("medium");
  const [templateMode, setTemplateMode] = useState<"auto" | "fill" | "append">("auto");
  const [editAction, setEditAction] = useState<"append" | "insert_after">("append");
  const [editTargetIndex, setEditTargetIndex] = useState<number | string>("");
  const [researchEnabled, setResearchEnabled] = useState(false);
  const [customInstructions, setCustomInstructions] = useState("");
  const [imageMode, setImageMode] = useState<"off" | "search" | "placeholder">("search");
  const [includeTables, setIncludeTables] = useState<boolean>(true);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhanceSuccess, setEnhanceSuccess] = useState(false);
  const [enhanceError, setEnhanceError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showAuthorDetails, setShowAuthorDetails] = useState(false);
  const [author, setAuthor] = useState("");
  const [guide, setGuide] = useState("");
  const [department, setDepartment] = useState("");
  const [institution, setInstitution] = useState("");
  const [overrideTarget, setOverrideTarget] = useState<
    "none" | "table_border" | "page_border" | "heading_color"
  >("none");
  const [overrideColor, setOverrideColor] = useState("#0284c7");
  const [enabledRuleIndexes, setEnabledRuleIndexes] = useState<number[]>(() =>
    (extractedRules || []).slice(0, 12).map((_, index) => index),
  );
  const enhanceController = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      enhanceController.current?.abort();
      enhanceController.current = null;
    },
    [],
  );

  const samplePrompts =
    documentType === "pptx"
      ? [
          "5-slide executive presentation on AI roadmap and adoption benchmarks",
          "Quarterly strategy deck with market comparison and key growth milestones",
          "Product overview presentation with architecture diagrams and feature tables",
        ]
      : [
          "Comprehensive business report on digital transformation with benchmark tables",
          "Technical project proposal with architecture breakdown and implementation roadmap",
          "Executive briefing on renewable energy transition with comparative evaluation metrics",
        ];

  const handleEnhancePrompt = async () => {
    if (!prompt.trim() || isEnhancing) return;
    setIsEnhancing(true);
    setEnhanceError(null);
    setEnhanceSuccess(false);
    enhanceController.current?.abort();
    const controller = new AbortController();
    enhanceController.current = controller;

    try {
      const res = await fetch("/api/enhance-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          prompt: prompt.trim(),
          document_type: documentType,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.enhanced_prompt) {
          setPrompt(data.enhanced_prompt);
          setEnhanceSuccess(true);
          setTimeout(() => setEnhanceSuccess(false), 3000);
        }
      } else {
        setEnhanceError("Could not enhance prompt. Please check backend connection.");
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      const clean = prompt.trim();
      const fallback =
        documentType === "pptx"
          ? `${clean}. Structure the output as an executive presentation deck with clear section slides, bulleted key takeaways, and comparison layouts following template typography.`
          : `${clean}. Structure the output as a comprehensive technical document with executive summary, architectural analysis, comparative benchmark tables, and actionable implementation roadmap, preserving the uploaded template's typography, hierarchy, and layout rules.`;
      setPrompt(fallback);
      setEnhanceSuccess(true);
      setTimeout(() => setEnhanceSuccess(false), 3000);
    } finally {
      if (enhanceController.current === controller) {
        enhanceController.current = null;
        setIsEnhancing(false);
      }
    }
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    const rawSlides =
      typeof targetSlides === "number" ? targetSlides : parseInt(targetSlides, 10) || 5;
    const rawPages =
      typeof targetPages === "number" ? targetPages : parseInt(targetPages, 10) || 5;
    const finalTargetSlides = Math.min(50, Math.max(1, rawSlides));
    const finalTargetPages = Math.min(50, Math.max(1, rawPages));

    const finalEditTarget =
      typeof editTargetIndex === "number"
        ? editTargetIndex
        : editTargetIndex === ""
        ? undefined
        : Number.parseInt(editTargetIndex, 10);

    onGenerate({
      prompt: prompt.trim(),
      mode,
      ...(documentType === "docx" && !mode.startsWith("edit") ? { templateMode } : {}),
      ...(mode === "edit_document"
        ? {
            editAction,
            ...(editAction !== "append" && finalEditTarget !== undefined
              ? { editTargetIndex: finalEditTarget }
              : {}),
          }
        : {}),
      ...(overrideTarget !== "none"
        ? { override: { target: overrideTarget, value: overrideColor } }
        : {}),
      ...(documentType === "pptx"
        ? { targetSlides: finalTargetSlides }
        : lengthMode === "pages"
        ? { targetPages: finalTargetPages }
        : { detailLevel }),
      researchEnabled: documentType !== "pptx" && mode.startsWith("create") && researchEnabled,
      customInstructions: customInstructions.trim() || undefined,
      includeImages: imageMode !== "off",
      imageMode,
      includeTables,
      enabledRuleIndexes,
      ...(author.trim() ? { author: author.trim() } : {}),
      ...(guide.trim() ? { guide: guide.trim() } : {}),
      ...(department.trim() ? { department: department.trim() } : {}),
      ...(institution.trim() ? { institution: institution.trim() } : {}),
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const visibleRules = (extractedRules || []).slice(0, 12);
  const allRulesSelected =
    visibleRules.length > 0 && enabledRuleIndexes.length === visibleRules.length;

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-sky-200/80 bg-white/90 p-5 sm:p-6 shadow-[0_8px_30px_rgba(186,230,253,0.35)] backdrop-blur-2xl space-y-5 transition-all duration-300"
    >
      {/* Step Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sky-200/70 pb-4">
        <div>
          <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-sky-600" />
            {documentType === "pptx" ? "Configure Presentation" : "Configure Document"}
          </h3>
          <p className="text-xs text-slate-500 mt-0.5 font-medium">
            Describe what you need. All fonts, colors, and layout rules from your template will be applied automatically.
          </p>
        </div>

        {enhanceSuccess && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-300 px-3 py-1 text-xs font-semibold text-emerald-700 animate-fadeIn shadow-sm">
            <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
            ✨ Prompt enhanced with structure!
          </span>
        )}
      </div>

      {enhanceError && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 flex items-center justify-between shadow-sm">
          <span className="font-medium">{enhanceError}</span>
          <button
            type="button"
            aria-label="Dismiss enhancement notice"
            onClick={() => setEnhanceError(null)}
            className="text-amber-700 hover:text-amber-950 px-1 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Interactive Prompt Area */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label htmlFor="document-prompt" className="text-xs font-bold text-slate-800">
            Document prompt
          </label>
          <span className="text-[11px] text-slate-500 font-medium hidden sm:inline">
            Press <kbd className="px-1.5 py-0.5 bg-sky-100 border border-sky-200 rounded text-sky-800 font-mono text-[10px]">Ctrl+Enter</kbd> to generate
          </span>
        </div>

        <div className="relative">
          <textarea
            id="document-prompt"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              documentType === "pptx"
                ? "e.g., 'Create a 5-slide presentation on digital transformation strategy and cloud adoption with comparison charts'..."
                : "e.g., 'Write a comprehensive business report on renewable energy integration with executive summary and benchmark tables'..."
            }
            className="w-full resize-none rounded-xl border border-sky-200/90 bg-white p-4 pr-32 text-sm text-slate-900 placeholder-slate-400 transition-all duration-300 focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-400/30 focus:shadow-[0_0_20px_rgba(14,165,233,0.2)]"
            required
          />

          <div className="absolute right-3 bottom-3.5 flex items-center gap-1.5">
            {prompt.trim().length > 0 && (
              <button
                type="button"
                onClick={() => setPrompt("")}
                title="Clear prompt"
                aria-label="Clear prompt"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-300 bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-800 transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={handleEnhancePrompt}
              disabled={!prompt.trim() || isEnhancing}
              className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-sky-600 via-sky-500 to-cyan-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-[0_0_14px_rgba(14,165,233,0.3)] hover:shadow-[0_0_20px_rgba(14,165,233,0.5)] hover:scale-[1.02] active:scale-[0.98] disabled:opacity-40 disabled:transform-none disabled:shadow-none transition-all duration-200 whitespace-nowrap shrink-0"
            >
              {isEnhancing ? (
                <>
                  <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Enhancing...</span>
                </>
              ) : (
                <>
                  <Wand2 className="h-3.5 w-3.5" />
                  <span>Enhance</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* 1-Click Starter Suggestions */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-[11px] font-semibold text-slate-500">Quick ideas:</span>
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setPrompt(p)}
              className="rounded-lg border border-sky-200 bg-sky-50/70 px-2.5 py-1 text-left text-xs font-medium text-slate-700 hover:border-sky-400 hover:bg-sky-100 hover:text-sky-950 transition-all truncate max-w-xs shadow-sm"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Primary Essential Options (Length, Images & Tables) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* Document / Presentation Length */}
        {documentType === "pptx" ? (
          <div className="rounded-xl border border-sky-200/80 bg-white/75 p-4 flex flex-col justify-between shadow-sm">
            <div>
              <div className="flex items-center justify-between gap-2">
                <label htmlFor="target-slides" className="text-xs font-bold text-slate-800">
                  Target slide count
                </label>
                <div className="flex items-center gap-1">
                  {[3, 5, 8, 12].map((presetCount) => (
                    <button
                      key={presetCount}
                      type="button"
                      onClick={() => setTargetSlides(presetCount)}
                      className={`rounded px-2.5 py-0.5 text-xs font-semibold tabular-nums transition-colors ${
                        Number(targetSlides) === presetCount
                          ? "bg-sky-600 text-white font-bold shadow-sm"
                          : "bg-sky-50 text-slate-700 border border-sky-200 hover:bg-sky-100"
                      }`}
                    >
                      {presetCount} slides
                    </button>
                  ))}
                </div>
              </div>
              <input
                id="target-slides"
                type="number"
                min={1}
                max={50}
                value={targetSlides}
                onChange={(e) =>
                  setTargetSlides(e.target.value === "" ? "" : parseInt(e.target.value, 10) || 1)
                }
                className="mt-2.5 w-full rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm text-slate-900 tabular-nums focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
              />
            </div>
            <p className="mt-2 text-[11px] text-slate-500 font-medium">
              Slides automatically inherit slide master styles and typography.
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-sky-200/80 bg-white/75 p-4 space-y-3 shadow-sm">
            <fieldset>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <legend className="text-xs font-bold text-slate-800">Document length</legend>
                <div className="flex gap-1">
                  {(["detail", "pages"] as const).map((choice) => (
                    <button
                      key={choice}
                      type="button"
                      aria-pressed={lengthMode === choice}
                      onClick={() => setLengthMode(choice)}
                      className={
                        lengthMode === choice
                          ? "rounded-md border border-sky-400 bg-sky-100 px-2 py-0.5 text-[11px] font-bold text-sky-900 shadow-sm"
                          : "rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:text-slate-900"
                      }
                    >
                      {choice === "pages" ? "Choose pages" : "Choose detail"}
                    </button>
                  ))}
                </div>
              </div>

              {lengthMode === "pages" ? (
                <div className="mt-2.5">
                  <label htmlFor="target-pages" className="block text-xs font-semibold text-slate-700">
                    Approximate page count (1–50)
                  </label>
                  <input
                    id="target-pages"
                    type="number"
                    min={1}
                    max={50}
                    value={targetPages}
                    onChange={(e) =>
                      setTargetPages(
                        e.target.value === "" ? "" : parseInt(e.target.value, 10) || 1,
                      )
                    }
                    className="mt-1.5 w-full rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm text-slate-900 tabular-nums focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
                  />
                  <p className="mt-1.5 text-[11px] text-slate-500 font-medium">
                    Approximate content length; pagination adapts to your template fonts and margins.
                  </p>
                </div>
              ) : (
                <div className="mt-2.5">
                  <span className="sr-only">Detail level</span>
                  <div className="grid grid-cols-3 gap-2">
                    {(
                      [
                        ["low", "Low", "~2 pages"],
                        ["medium", "Medium", "~5 pages"],
                        ["high", "High", "~10 pages"],
                      ] as const
                    ).map(([value, label, estimate]) => (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={detailLevel === value}
                        onClick={() => setDetailLevel(value)}
                        className={
                          detailLevel === value
                            ? "rounded-xl border-2 border-sky-500 bg-sky-50/90 p-2.5 text-left text-sky-950 shadow-[0_0_16px_rgba(14,165,233,0.2)] scale-[1.01] transition-all duration-200 font-bold"
                            : "rounded-xl border border-sky-200/80 bg-white/80 p-2.5 text-left text-slate-700 hover:border-sky-300 hover:bg-sky-50/40 hover:scale-[1.005] transition-all duration-200"
                        }
                      >
                        <span className="block text-xs font-bold">{label}</span>
                        <span className="mt-0.5 block text-[11px] text-slate-500 font-medium tabular-nums">
                          {estimate}
                        </span>
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500 font-medium">
                    Target length estimate; preserves all original template spacing.
                  </p>
                </div>
              )}
            </fieldset>
          </div>
        )}

        {/* Visuals & Figures */}
        <div className="rounded-xl border border-sky-200/80 bg-white/75 p-4 flex flex-col justify-between shadow-sm">
          <fieldset>
            <legend className="text-xs font-bold text-slate-800">Figures and images</legend>
            <p className="mt-1 text-[11px] text-slate-500 font-medium">
              Include contextual illustrations or generate pure text and tables.
            </p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs">
              <label
                className={
                  imageSearchAvailable === false
                    ? "flex items-center gap-2 text-slate-400"
                    : "flex items-center gap-2 text-slate-800 font-medium cursor-pointer"
                }
              >
                <input
                  type="radio"
                  name="image-mode"
                  checked={imageMode === "search"}
                  disabled={imageSearchAvailable === false}
                  onChange={() => setImageMode("search")}
                  className="accent-sky-600"
                />
                Include images
              </label>
              <label className="flex items-center gap-2 text-slate-800 font-medium cursor-pointer">
                <input
                  type="radio"
                  name="image-mode"
                  checked={imageMode === "off"}
                  onChange={() => setImageMode("off")}
                  className="accent-sky-600"
                />
                No images
              </label>
              {placeholdersAvailable !== false && (
                <label className="flex items-center gap-2 text-slate-800 font-medium cursor-pointer">
                  <input
                    type="radio"
                    name="image-mode"
                    checked={imageMode === "placeholder"}
                    onChange={() => setImageMode("placeholder")}
                    className="accent-sky-600"
                  />
                  Neutral placeholders
                </label>
              )}
            </div>
          </fieldset>

          {documentType !== "pptx" && mode.startsWith("create") && (
            <div className="border-t border-sky-200/70 pt-2.5 mt-3">
              <label
                className={
                  researchAvailable
                    ? "flex cursor-pointer items-start gap-2 text-xs text-slate-800"
                    : "flex cursor-not-allowed items-start gap-2 text-xs text-slate-400"
                }
              >
                <input
                  type="checkbox"
                  checked={researchEnabled}
                  disabled={!researchAvailable}
                  onChange={(e) => setResearchEnabled(e.target.checked)}
                  className="mt-0.5 rounded border-sky-300 bg-white text-sky-600 focus:ring-sky-500 disabled:opacity-50"
                />
                <span>
                  <span className="font-bold">Research sources</span>
                  <span className="mt-0.5 block text-[11px] text-slate-500 font-medium">
                    {researchAvailable
                      ? "Optional web search citations; results are not independently verified."
                      : researchCapabilityKnown
                      ? "Unavailable because the backend has no Tavily API key configured."
                      : "Availability cannot be confirmed until the backend health check succeeds."}
                  </span>
                </span>
              </label>
            </div>
          )}
        </div>

        {/* Data Tables & Benchmarks */}
        {documentType !== "pptx" && (
          <div className="rounded-xl border border-sky-200/80 bg-white/75 p-4 flex flex-col justify-between shadow-sm">
            <fieldset>
              <legend className="text-xs font-bold text-slate-800">Data tables &amp; benchmarks</legend>
              <p className="mt-1 text-[11px] text-slate-500 font-medium">
                Include formatted tables for comparative benchmarks, specifications, and metrics.
              </p>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs">
                <label className="flex items-center gap-2 text-slate-800 font-medium cursor-pointer">
                  <input
                    type="radio"
                    name="table-mode"
                    checked={includeTables}
                    onChange={() => setIncludeTables(true)}
                    className="accent-sky-600"
                  />
                  Include tables
                </label>
                <label className="flex items-center gap-2 text-slate-800 font-medium cursor-pointer">
                  <input
                    type="radio"
                    name="table-mode"
                    checked={!includeTables}
                    onChange={() => setIncludeTables(false)}
                    className="accent-sky-600"
                  />
                  No tables
                </label>
              </div>
            </fieldset>
            <div className="border-t border-sky-200/70 pt-2.5 mt-3">
              <span className="text-[11px] text-slate-500 font-medium">
                Rendered with OpenXML table grid borders and typography rules.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Detected Template Rules (Shown neatly when template contains extracted rules) */}
      {visibleRules.length > 0 && (
        <fieldset className="rounded-xl border border-sky-200 bg-sky-50/60 p-3.5 text-xs shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div>
              <legend className="font-bold text-sky-900">Detected template rules</legend>
              <p className="text-[11px] text-slate-500 font-medium">Rules extracted from your template to guide AI structure</p>
            </div>
            <button
              type="button"
              onClick={() =>
                setEnabledRuleIndexes(
                  allRulesSelected ? [] : visibleRules.map((_, index) => index),
                )
              }
              className="text-[11px] font-bold text-sky-600 hover:text-sky-800 underline underline-offset-2"
            >
              {allRulesSelected ? "Deselect all" : "Select all"} ({enabledRuleIndexes.length}/{visibleRules.length})
            </button>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {visibleRules.map((rule, index) => (
              <label
                key={`${index}-${rule}`}
                className="flex items-start gap-2 rounded-lg border border-sky-200/80 bg-white/90 p-2 text-slate-800 cursor-pointer hover:border-sky-400 hover:bg-sky-50/80 transition-colors shadow-sm"
              >
                <input
                  type="checkbox"
                  checked={enabledRuleIndexes.includes(index)}
                  onChange={(event) =>
                    setEnabledRuleIndexes((current) =>
                      event.target.checked
                        ? [...current, index].sort((left, right) => left - right)
                        : current.filter((item) => item !== index),
                    )
                  }
                  className="mt-0.5 accent-sky-600"
                />
                <span className="leading-snug text-xs font-medium">{rule}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {/* Optional Report & Front-Matter Metadata (Cover Page / Certificate / Acknowledgement) */}
      {documentType !== "pptx" && (
        <div className="rounded-xl border border-sky-200/80 bg-white/80 p-3.5 text-xs shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="font-bold text-slate-800">
                Cover Page &amp; Seminar Metadata (Optional)
              </span>
              <p className="text-[11px] text-slate-500 font-medium">
                Populate Student Name, Guide, Department, and Institution on cover and certificate pages, or include them directly in your prompt.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowAuthorDetails(!showAuthorDetails)}
              className="text-xs font-bold text-sky-700 hover:text-sky-900 flex items-center gap-1"
            >
              {showAuthorDetails ? (
                <>
                  <ChevronUp className="h-3.5 w-3.5" />
                  Hide fields
                </>
              ) : (
                <>
                  <ChevronDown className="h-3.5 w-3.5" />
                  Fill author &amp; guide details
                </>
              )}
            </button>
          </div>

          {showAuthorDetails && (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 border-t border-sky-100 pt-3">
              <label className="grid gap-1 text-xs font-bold text-slate-800">
                Student / Author Name
                <input
                  type="text"
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                  placeholder="e.g., Devon Vance (Roll No. 42)"
                  className="rounded-lg border border-sky-200 bg-white px-3 py-1.5 text-xs font-normal text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
                />
              </label>
              <label className="grid gap-1 text-xs font-bold text-slate-800">
                Guide / Supervisor Name
                <input
                  type="text"
                  value={guide}
                  onChange={(e) => setGuide(e.target.value)}
                  placeholder="e.g., Dr. S. K. Wankhade"
                  className="rounded-lg border border-sky-200 bg-white px-3 py-1.5 text-xs font-normal text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
                />
              </label>
              <label className="grid gap-1 text-xs font-bold text-slate-800">
                Department
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder="e.g., Department of Computer Engineering"
                  className="rounded-lg border border-sky-200 bg-white px-3 py-1.5 text-xs font-normal text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
                />
              </label>
              <label className="grid gap-1 text-xs font-bold text-slate-800">
                Institution / College
                <input
                  type="text"
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  placeholder="e.g., Institute of Engineering & Technology"
                  className="rounded-lg border border-sky-200 bg-white px-3 py-1.5 text-xs font-normal text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400"
                />
              </label>
            </div>
          )}
        </div>
      )}

      {/* Advanced Settings (Collapsed by default so regular users are not overwhelmed) */}
      <div className="border-t border-sky-200/70 pt-2">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs font-bold text-sky-700 hover:text-sky-900 flex items-center gap-1.5 py-1"
        >
          {showAdvanced ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              − Hide generation options
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              + Show advanced options
            </>
          )}
        </button>

        {showAdvanced && (
          <div className="mt-3 space-y-4 rounded-xl border border-sky-200 bg-sky-50/40 p-4 shadow-sm">
            {/* Mode Selector */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sky-200/60 pb-3">
              <div>
                <span className="text-xs font-bold text-slate-800">Execution Mode</span>
                <p className="text-[11px] text-slate-500 font-medium">Choose full generation or surgical modification</p>
              </div>
              <div className="flex rounded-lg bg-white border border-sky-200 p-1 shadow-sm">
                <button
                  type="button"
                  onClick={() =>
                    setMode(documentType === "pptx" ? "create_presentation" : "create_document")
                  }
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-semibold transition-all ${
                    mode.startsWith("create")
                      ? "bg-sky-600 text-white font-bold shadow-sm"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Full Generation
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setMode(documentType === "pptx" ? "edit_presentation" : "edit_document")
                  }
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-semibold transition-all ${
                    mode.startsWith("edit")
                      ? "bg-sky-600 text-white font-bold shadow-sm"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <Sliders className="h-3.5 w-3.5" />
                  {documentType === "pptx" ? "Append Slides" : "Surgical Edit"}
                </button>
              </div>
            </div>

            {/* Surgical Edit Outline & Action Picker */}
            {mode === "edit_document" && documentOutline && documentOutline.length > 0 && (
              <fieldset className="grid gap-3 rounded-xl border border-sky-300 bg-white/90 p-3.5 text-xs sm:grid-cols-2 shadow-sm">
                <legend className="px-1 font-bold text-sky-900">Edit the template</legend>
                <label className="grid gap-1 text-slate-800 font-medium">
                  Edit action
                  <select
                    value={editAction}
                    onChange={(event) => setEditAction(event.target.value as typeof editAction)}
                    className="rounded-lg border border-sky-200 bg-white px-2.5 py-2 text-slate-900"
                  >
                    <option value="append">Append a section</option>
                    <option value="insert_after">Insert after a heading</option>
                  </select>
                </label>
                {editAction !== "append" && (
                  <label className="grid gap-1 text-slate-800 font-medium">
                    Target heading
                    <select
                      value={editTargetIndex}
                      onChange={(event) => setEditTargetIndex(event.target.value)}
                      required
                      className="rounded-lg border border-sky-200 bg-white px-2.5 py-2 text-slate-900"
                    >
                      <option value="">Choose a heading</option>
                      {documentOutline.map((heading, index) => (
                        <option key={`${index}-${heading}`} value={index}>
                          {heading}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </fieldset>
            )}

            {/* Document Template Mode */}
            {documentType === "docx" && mode.startsWith("create") && (
              <div>
                <label htmlFor="template-mode" className="block text-xs font-bold text-slate-800">
                  How to use the document template
                </label>
                <select
                  id="template-mode"
                  value={templateMode}
                  onChange={(event) => setTemplateMode(event.target.value as typeof templateMode)}
                  className="mt-1.5 w-full rounded-lg border border-sky-200 bg-white px-3 py-2 text-xs text-slate-900 shadow-sm"
                >
                  <option value="auto">Choose automatically (recommended)</option>
                  <option value="fill">Fill detected placeholders</option>
                  <option value="append">Append after existing content</option>
                </select>
              </div>
            )}

            {/* Audience Instructions & Color Overrides */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-bold text-slate-800">
                  Target audience / Special focus
                </label>
                <input
                  type="text"
                  value={customInstructions}
                  onChange={(e) => setCustomInstructions(e.target.value)}
                  placeholder="Target audience: engineering leads or executive summary"
                  className="mt-1.5 w-full rounded-lg border border-sky-200 bg-white px-3 py-2 text-xs text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400 shadow-sm"
                />
              </div>

              {documentType !== "pptx" && (
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="grid gap-1 text-xs font-bold text-slate-800">
                    Formatting override
                    <select
                      value={overrideTarget}
                      onChange={(event) =>
                        setOverrideTarget(event.target.value as typeof overrideTarget)
                      }
                      className="rounded-lg border border-sky-200 bg-white px-2.5 py-2 text-xs text-slate-900 shadow-sm"
                    >
                      <option value="none">No override</option>
                      <option value="table_border">Table border color</option>
                      <option value="page_border">Page border color</option>
                      <option value="heading_color">Heading color</option>
                    </select>
                  </label>
                  {overrideTarget !== "none" && (
                    <label className="grid gap-1 text-xs font-bold text-slate-800">
                      Override color
                      <input
                        type="color"
                        value={overrideColor}
                        onChange={(event) => setOverrideColor(event.target.value)}
                        className="h-9 w-full rounded border border-sky-200 bg-white cursor-pointer"
                      />
                    </label>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-sky-200/70 pt-4">
        <div className="text-[11px] text-slate-500 font-medium">
          DocGuru compares selected typography, layout, and page dimensions with the uploaded template.
        </div>

        <button
          type="submit"
          disabled={!prompt.trim() || isGenerating}
          className={`flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 via-sky-500 to-cyan-500 px-6 py-3 text-xs font-bold text-white shadow-[0_0_20px_rgba(14,165,233,0.35)] hover:shadow-[0_0_28px_rgba(14,165,233,0.55)] hover:scale-[1.015] active:scale-[0.985] focus:outline-none focus:ring-4 focus:ring-sky-400/30 transition-all duration-300 whitespace-nowrap shrink-0 ${
            !prompt.trim() || isGenerating ? "pointer-events-none opacity-50 shadow-none transform-none" : ""
          }`}
        >
          {isGenerating ? (
            <>
              <div className="h-4 w-4 animate-spin motion-reduce:animate-none rounded-full border-2 border-white border-t-transparent" />
              <span>Generating Artifact...</span>
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              <span>Generate using this template</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </form>
  );
}
