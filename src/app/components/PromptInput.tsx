"use client";

import React, { useEffect, useRef, useState } from "react";
import { Sparkles, ArrowRight, Wand2, Sliders } from "lucide-react";
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
}: PromptInputProps) {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<GenerationMode>(
    documentType === "pptx" ? "create_presentation" : "create_document"
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
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhanceError, setEnhanceError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [overrideTarget, setOverrideTarget] = useState<"none" | "table_border" | "page_border" | "heading_color">("none");
  const [overrideColor, setOverrideColor] = useState("#000000");
  const [enabledRuleIndexes, setEnabledRuleIndexes] = useState<number[]>(
    () => (extractedRules || []).slice(0, 12).map((_, index) => index),
  );
  const enhanceController = useRef<AbortController | null>(null);

  useEffect(() => () => {
    enhanceController.current?.abort();
    enhanceController.current = null;
  }, []);

  const samplePrompts = documentType === "pptx" ? [
    ...(mode.startsWith("edit")
      ? [
          "Append a new section on digital trust architecture using this presentation's layouts.",
          "Add slides comparing current and emerging quantum computing approaches.",
          "Append an executive strategy section with a comparison table and diagrams.",
        ]
      : [
          "Create a presentation on digital trust architecture using this presentation's layout styles.",
          "Build a 5-slide deck on quantum computing developments with market benchmarks and architecture diagrams.",
          "Generate an executive strategy presentation with comparison tables and slide visuals.",
        ])
  ] : mode.startsWith("edit") ? [
    "Add a new chapter on distributed systems with architectural breakdown and comparative performance table.",
    "Insert an experimental evaluation section following the document's embedded formatting rules.",
    "Expand the Methodology section with algorithmic complexity analysis and benchmark figures."
  ] : [
    "Create a comprehensive report on renewable energy grid integration using this document's format.",
    "Generate a technical paper on distributed consensus algorithms with comparative benchmark tables.",
    "Write an executive briefing on software supply chain security standards."
  ];

  const handleEnhancePrompt = async () => {
    if (!prompt.trim() || isEnhancing) return;
    setIsEnhancing(true);
    setEnhanceError(null);
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
        }
      } else {
        setEnhanceError("Could not enhance prompt. Please check backend connection.");
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      console.error("Failed to enhance prompt", e);
      setEnhanceError("Enhance request failed. Falling back to local prompt.");
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

    const finalTargetSlides = typeof targetSlides === "number" ? targetSlides : parseInt(targetSlides, 10) || 5;
    const finalTargetPages = typeof targetPages === "number" ? targetPages : parseInt(targetPages, 10) || 5;
    const finalEditTarget = typeof editTargetIndex === "number"
      ? editTargetIndex
      : editTargetIndex === "" ? undefined : Number.parseInt(editTargetIndex, 10);

    onGenerate({
      prompt: prompt.trim(),
      mode,
      ...(documentType === "docx" && !mode.startsWith("edit") ? { templateMode } : {}),
      ...(mode === "edit_document" ? {
        editAction,
        ...(editAction !== "append" && finalEditTarget !== undefined ? { editTargetIndex: finalEditTarget } : {}),
      } : {}),
      ...(overrideTarget !== "none" ? { override: { target: overrideTarget, value: overrideColor } } : {}),
      ...(documentType === "pptx"
        ? { targetSlides: finalTargetSlides }
        : lengthMode === "pages"
          ? { targetPages: finalTargetPages }
          : { detailLevel }),
      researchEnabled: documentType !== "pptx" && mode.startsWith("create") && researchEnabled,
      customInstructions: customInstructions.trim() || undefined,
      includeImages: imageMode !== "off",
      imageMode,
      enabledRuleIndexes,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-cyan-500/20 bg-zinc-950/80 p-6 shadow-2xl backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Wand2 className="h-4 w-4 text-cyan-400" />
            Document generation options
          </h3>
          <p className="text-xs text-zinc-400">
            Describe the document you need, choose its length, and review the template properties and selected rules before generating.
          </p>
        </div>

        {/* Mode Selector */}
        <div className="flex rounded-xl bg-zinc-900 border border-zinc-800 p-1">
          <button
            type="button"
            onClick={() => setMode(documentType === "pptx" ? "create_presentation" : "create_document")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold transition-all ${
              mode.startsWith("create")
                ? "bg-cyan-500 text-zinc-950 shadow-md font-bold"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Full Generation
          </button>
          <button
            type="button"
            onClick={() => setMode(documentType === "pptx" ? "edit_presentation" : "edit_document")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold transition-all ${
              mode.startsWith("edit")
                ? "bg-indigo-600 text-white shadow-md font-bold"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Sliders className="h-3.5 w-3.5" />
            {documentType === "pptx" ? "Append Slides" : "Surgical Edit / Add Chapter"}
          </button>
        </div>
      </div>

      {/* Let users choose which rules to include with this generation request. */}
      {extractedRules && extractedRules.length > 0 && (
        <fieldset className="mt-3.5 rounded-xl border border-cyan-500/30 bg-cyan-950/20 px-3.5 py-2.5 text-xs">
          <legend className="px-1 font-medium text-cyan-200">Detected template rules</legend>
          <p className="mb-2 text-zinc-300">Choose which detected rules to include with the generation request. Review the document after generation.</p>
          <div className="space-y-2">
            {extractedRules.slice(0, 12).map((rule, index) => (
              <label key={`${index}-${rule}`} className="flex items-start gap-2 text-zinc-200">
                <input
                  type="checkbox"
                  checked={enabledRuleIndexes.includes(index)}
                  onChange={(event) => setEnabledRuleIndexes((current) => event.target.checked
                    ? [...current, index].sort((left, right) => left - right)
                    : current.filter((item) => item !== index))}
                  className="mt-0.5 accent-cyan-500"
                />
                <span>{rule}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {/* Explicit edit action and outline target; no instruction parsing. */}
      {mode === "edit_document" && documentOutline && documentOutline.length > 0 && (
        <fieldset className="mt-3.5 grid gap-3 rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-3 text-xs sm:grid-cols-2">
          <legend className="px-1 font-semibold text-indigo-200">Edit the template</legend>
          <label className="grid gap-1 text-zinc-200">
            Edit action
            <select
              value={editAction}
              onChange={(event) => setEditAction(event.target.value as typeof editAction)}
              className="rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-2 text-zinc-100"
            >
              <option value="append">Append a section</option>
              <option value="insert_after">Insert after a heading</option>
            </select>
          </label>
          {editAction !== "append" && (
            <label className="grid gap-1 text-zinc-200">
              Target heading
              <select
                value={editTargetIndex}
                onChange={(event) => setEditTargetIndex(event.target.value)}
                required
                className="rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-2 text-zinc-100"
              >
                <option value="">Choose a heading</option>
                {documentOutline.map((heading, index) => (
                  <option key={`${index}-${heading}`} value={index}>{heading}</option>
                ))}
              </select>
            </label>
          )}
        </fieldset>
      )}

      {enhanceError && (
        <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-950/30 p-2.5 text-xs text-amber-300 flex items-center justify-between">
          <span>{enhanceError}</span>
          <button type="button" onClick={() => setEnhanceError(null)} className="text-amber-400 hover:text-amber-200">✕</button>
        </div>
      )}

      {/* Main Textarea with Enhance Button */}
      <div className="mt-4 relative">
        <label htmlFor="document-prompt" className="sr-only">Document prompt</label>
        <textarea
          id="document-prompt"
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            documentType === "pptx"
              ? "e.g., 'Create a presentation on digital trust architecture using this presentation's theme.' (Press Ctrl+Enter to generate)"
              : "e.g., 'Create a comprehensive report on renewable energy grid integration with benchmark tables and diagrams.' (Press Ctrl+Enter to generate)"
          }
          className="w-full resize-none rounded-xl border border-zinc-800 bg-zinc-900/90 p-4 pr-36 text-sm text-white placeholder-zinc-500 transition-all focus:border-cyan-400 focus:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-cyan-400/20"
          required
        />

        {/* Magic Enhance Button */}
        <button
          type="button"
          onClick={handleEnhancePrompt}
          disabled={!prompt.trim() || isEnhancing}
          className="absolute right-3 bottom-4 flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 px-3 py-1.5 text-xs font-bold text-white shadow-md shadow-cyan-500/20 hover:brightness-110 disabled:opacity-40 transition-all"
        >
          {isEnhancing ? (
            <>
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <span>Enhancing...</span>
            </>
          ) : (
            <>
              <Wand2 className="h-3.5 w-3.5" />
              <span>✨ Enhance</span>
            </>
          )}
        </button>
      </div>

      {/* Quick Prompts */}
      <div className="mt-3">
        <span className="text-[11px] font-semibold text-zinc-400">Quick Templates:</span>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setPrompt(p)}
              className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-2.5 py-1 text-left text-xs text-zinc-300 transition-all hover:border-cyan-500/50 hover:bg-cyan-950/30 hover:text-cyan-300"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {documentType === "pptx" ? (
        <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <label htmlFor="target-slides" className="block text-xs font-semibold text-zinc-200">Target slide count</label>
          <input
            id="target-slides"
            type="number"
            min={1}
            max={50}
            value={targetSlides}
            onChange={(e) => setTargetSlides(e.target.value === "" ? "" : parseInt(e.target.value, 10) || 1)}
            className="mt-2 w-full max-w-xs rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white focus:border-cyan-400 focus:outline-none"
          />
        </div>
      ) : mode.startsWith("create") && (
        <div className="mt-4 space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <fieldset>
            <legend className="text-xs font-semibold text-zinc-200">Document length</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {(["detail", "pages"] as const).map((choice) => (
                <button
                  key={choice}
                  type="button"
                  aria-pressed={lengthMode === choice}
                  onClick={() => setLengthMode(choice)}
                  className={lengthMode === choice
                    ? "rounded-lg border border-cyan-400 bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-zinc-950"
                    : "rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:border-zinc-500"}
                >
                  {choice === "pages" ? "Choose pages" : "Choose detail"}
                </button>
              ))}
            </div>
            {lengthMode === "pages" ? (
              <div className="mt-3">
                <label htmlFor="target-pages" className="block text-xs text-zinc-300">Approximate page count (1–50)</label>
                <input
                  id="target-pages"
                  type="number"
                  min={1}
                  max={50}
                  value={targetPages}
                  onChange={(e) => setTargetPages(e.target.value === "" ? "" : parseInt(e.target.value, 10) || 1)}
                  className="mt-1.5 w-full max-w-xs rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white focus:border-cyan-400 focus:outline-none"
                />
                <p className="mt-1.5 text-[11px] text-zinc-400">This is an approximate content target. Actual pagination varies by template and rendering software.</p>
              </div>
            ) : (
              <div className="mt-3">
                <span className="block text-xs text-zinc-300">Detail level</span>
                <div className="mt-1.5 grid grid-cols-3 gap-2">
                  {([
                    ["low", "Low", "~2 pages"],
                    ["medium", "Medium", "~5 pages"],
                    ["high", "High", "~10 pages"],
                  ] as const).map(([value, label, estimate]) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={detailLevel === value}
                      onClick={() => setDetailLevel(value)}
                      className={detailLevel === value
                        ? "rounded-lg border border-cyan-400 bg-cyan-950/50 px-3 py-2 text-left text-cyan-200"
                        : "rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-left text-zinc-300 hover:border-zinc-500"}
                    >
                      <span className="block text-xs font-semibold">{label}</span>
                      <span className="mt-0.5 block text-[10px] text-zinc-400">{estimate}</span>
                    </button>
                  ))}
                </div>
                <p className="mt-1.5 text-[11px] text-zinc-400">Approximate length only; pagination varies by template and rendering software.</p>
              </div>
            )}
          </fieldset>

          <div className="border-t border-zinc-800 pt-3">
            <label className={researchAvailable
              ? "flex cursor-pointer items-start gap-2 text-xs text-zinc-200"
              : "flex cursor-not-allowed items-start gap-2 text-xs text-zinc-500"}
            >
              <input
                type="checkbox"
                checked={researchEnabled}
                disabled={!researchAvailable}
                onChange={(e) => setResearchEnabled(e.target.checked)}
                className="mt-0.5 rounded border-zinc-700 bg-zinc-800 text-cyan-500 focus:ring-cyan-400 disabled:opacity-50"
              />
              <span>
                <span className="font-semibold">Research sources</span>
                <span className="mt-0.5 block text-[11px] text-zinc-400">
                  {researchAvailable
                    ? "Optional. Adds citations from retrieved web sources; results are not independently verified."
                    : researchCapabilityKnown
                      ? "Unavailable because the backend has no Tavily API key configured."
                      : "Availability cannot be confirmed until the backend health check succeeds."}
                </span>
              </span>
            </label>
          </div>
        </div>
      )}

      {documentType === "docx" && mode.startsWith("create") && (
        <div className="mt-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <label htmlFor="template-mode" className="block text-xs font-semibold text-zinc-200">How to use the document template</label>
          <select
            id="template-mode"
            value={templateMode}
            onChange={(event) => setTemplateMode(event.target.value as typeof templateMode)}
            className="mt-2 w-full max-w-xs rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white"
          >
            <option value="auto">Choose automatically (recommended)</option>
            <option value="fill">Fill detected placeholders</option>
            <option value="append">Append after existing content</option>
          </select>
          <p className="mt-1.5 text-[11px] text-zinc-400">Use Auto when the template does not contain clear placeholders or a replaceable section.</p>
        </div>
      )}

      <fieldset className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3.5">
        <legend className="px-1 text-xs font-semibold text-zinc-200">Figures and images</legend>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
          <label className="flex items-center gap-2 text-zinc-200">
            <input type="radio" name="image-mode" checked={imageMode === "off"} onChange={() => setImageMode("off")} />
            No images
          </label>
          <label className={imageSearchAvailable === false ? "flex items-center gap-2 text-zinc-500" : "flex items-center gap-2 text-zinc-200"}>
            <input type="radio" name="image-mode" checked={imageMode === "search"} disabled={imageSearchAvailable === false} onChange={() => setImageMode("search")} />
            Search for images
          </label>
          <label className={placeholdersAvailable === false ? "flex items-center gap-2 text-zinc-500" : "flex items-center gap-2 text-zinc-200"}>
            <input type="radio" name="image-mode" checked={imageMode === "placeholder"} disabled={placeholdersAvailable === false} onChange={() => setImageMode("placeholder")} />
            Neutral placeholders
          </label>
        </div>
        {imageSearchAvailable === false && <p className="mt-2 text-zinc-400">Image search is unavailable in the current configuration.</p>}
        {imageSearchAvailable && placeholdersAvailable === false && <p className="mt-2 text-zinc-400">Neutral placeholders are disabled by the server operator.</p>}
      </fieldset>

      {/* Advanced Options Accordion */}
      <div className="mt-4 border-t border-zinc-800/80 pt-3">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5"
        >
          {showAdvanced ? "− Hide generation options" : "+ Show advanced options"}
        </button>

        {showAdvanced && (
          <div className="mt-3 grid grid-cols-1 gap-4 rounded-xl bg-zinc-900/60 p-4 border border-zinc-800">
            <div>
              <label className="block text-xs font-semibold text-zinc-300">
                Surgical Theme Override / Special Focus
              </label>
              <input
                type="text"
                value={customInstructions}
                onChange={(e) => setCustomInstructions(e.target.value)}
                placeholder="e.g., 'Target audience: engineering leads' or 'Include comparison table'"
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-white focus:border-cyan-400 focus:outline-none"
              />
            </div>
            {documentType !== "pptx" && (
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="grid gap-1 text-xs font-semibold text-zinc-300">
                  Formatting override
                  <select
                    value={overrideTarget}
                    onChange={(event) => setOverrideTarget(event.target.value as typeof overrideTarget)}
                    className="rounded-lg border border-zinc-700 bg-zinc-800 px-2.5 py-2 text-xs text-white"
                  >
                    <option value="none">No override</option>
                    <option value="table_border">Table border color</option>
                    <option value="page_border">Page border color</option>
                    <option value="heading_color">Heading color</option>
                  </select>
                </label>
                {overrideTarget !== "none" && (
                  <label className="grid gap-1 text-xs font-semibold text-zinc-300">
                    Override color
                    <input
                      type="color"
                      value={overrideColor}
                      onChange={(event) => setOverrideColor(event.target.value)}
                      className="h-9 w-full rounded border border-zinc-700 bg-zinc-800"
                    />
                  </label>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Action Bar */}
      <div className="mt-5 flex items-center justify-between border-t border-zinc-800/80 pt-4">
        <div className="text-[11px] text-zinc-400">
          After generation, DocGuru compares selected typography, layout, and page dimensions with the uploaded template.
        </div>

        <button
          type="submit"
          disabled={!prompt.trim() || isGenerating}
          className={`flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-cyan-500/20 transition-all hover:brightness-110 focus:outline-none focus:ring-4 focus:ring-cyan-500/20 active:scale-[0.98] ${
            !prompt.trim() || isGenerating ? "pointer-events-none opacity-50" : ""
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
