"use client";

import React, { useState } from "react";
import { Sparkles, ArrowRight, Wand2, Image as ImageIcon, Sliders } from "lucide-react";
import { PromptData } from "@/types/template";

interface PromptInputProps {
  documentType: "docx" | "pptx" | "pdf";
  onGenerate: (data: PromptData) => void;
  isGenerating: boolean;
  extractedRules?: string[];
  documentOutline?: string[];
}

export function PromptInput({
  documentType,
  onGenerate,
  isGenerating,
  extractedRules,
  documentOutline,
}: PromptInputProps) {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<string>(
    documentType === "pptx" ? "create_presentation" : "create_document"
  );
  const [targetCount, setTargetCount] = useState<number | string>(documentType === "pptx" ? 5 : 4);
  const [customInstructions, setCustomInstructions] = useState("");
  const [includeImages, setIncludeImages] = useState(true);
  const [imageMode, setImageMode] = useState<"search" | "generate" | "auto">("auto");
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhanceError, setEnhanceError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const samplePrompts = documentType === "pptx" ? [
    "Create a presentation on AI misinformation using this PPT's theme with visual figures.",
    "Build a 5-slide deck on quantum computing breakthroughs with market benchmarks and architecture diagrams.",
    "Generate an executive strategy presentation with comparison tables and slide visuals."
  ] : mode.startsWith("edit") ? [
    "Add a new chapter on Quantum Neural Networks with architecture breakdown and comparative performance table.",
    "Insert an experimental evaluation section following the document's embedded formatting rules.",
    "Expand the Methodology section with algorithmic complexity analysis and benchmark figures."
  ] : [
    "Create a comprehensive report on AlphaGo using this document's format with architecture figures.",
    "Generate a technical paper on distributed consensus algorithms with comparative benchmark tables.",
    "Write an executive briefing on AI safety guidelines and change the blue border to yellow."
  ];

  const handleEnhancePrompt = async () => {
    if (!prompt.trim() || isEnhancing) return;
    setIsEnhancing(true);
    setEnhanceError(null);

    try {
      const res = await fetch("/api/enhance-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
      console.error("Failed to enhance prompt", e);
      setEnhanceError("Enhance request failed. Falling back to local prompt.");
    } finally {
      setIsEnhancing(false);
    }
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    const finalTargetCount = typeof targetCount === "number" ? targetCount : parseInt(targetCount, 10) || (documentType === "pptx" ? 5 : 4);

    onGenerate({
      prompt: prompt.trim(),
      mode,
      targetPagesOrSlides: finalTargetCount,
      customInstructions: customInstructions.trim() || undefined,
      includeImages,
      imageMode,
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
            Neural Prompt Studio & Visual Director
          </h3>
          <p className="text-xs text-zinc-400">
            Gemma 4 plans content, sources high-res visuals, and strictly enforces template invariants.
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
            Surgical Edit / Add Chapter
          </button>
        </div>
      </div>

      {/* Extracted Rules Enforced Banner */}
      {extractedRules && extractedRules.length > 0 && (
        <div className="mt-3.5 rounded-xl border border-cyan-500/30 bg-cyan-950/20 px-3.5 py-2.5 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-cyan-300 font-medium">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-[11px] text-cyan-400 font-bold">
              {extractedRules.length}
            </span>
            <span>
              <strong>Embedded Document Rules Active:</strong> AI generation is locked to follow all extracted formatting and submission guidelines.
            </span>
          </div>
          <span className="shrink-0 text-[10px] text-cyan-400 bg-cyan-900/40 px-2 py-0.5 rounded border border-cyan-500/30 font-semibold uppercase tracking-wider">
            Auto-Enforced
          </span>
        </div>
      )}

      {/* Target Landmark Quick-Selector for Surgical Edits */}
      {mode.startsWith("edit") && documentOutline && documentOutline.length > 0 && (
        <div className="mt-3.5 rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-3 text-xs">
          <div className="font-semibold text-indigo-300 mb-2 flex items-center gap-1.5">
            <Sliders className="h-3.5 w-3.5 text-indigo-400" />
            <span>Target Existing Landmark / Chapter:</span>
          </div>
          <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto pr-1">
            <button
              type="button"
              onClick={() => setPrompt((prev) => prev ? `Append new chapter: ${prev}` : "Append new chapter on ")}
              className="rounded-lg bg-indigo-600/30 border border-indigo-500/40 px-2.5 py-1 text-xs text-indigo-200 hover:bg-indigo-600/50 transition-all font-medium"
            >
              + Append New Chapter
            </button>
            {documentOutline.map((heading, hIdx) => (
              <button
                key={hIdx}
                type="button"
                onClick={() => setPrompt(`Insert after "${heading}": `)}
                className="rounded-lg bg-zinc-900/80 border border-zinc-700/80 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-indigo-400 hover:text-indigo-200 transition-all"
              >
                Insert after: {heading}
              </button>
            ))}
          </div>
        </div>
      )}

      {enhanceError && (
        <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-950/30 p-2.5 text-xs text-amber-300 flex items-center justify-between">
          <span>{enhanceError}</span>
          <button type="button" onClick={() => setEnhanceError(null)} className="text-amber-400 hover:text-amber-200">✕</button>
        </div>
      )}

      {/* Main Textarea with Enhance Button */}
      <div className="mt-4 relative">
        <textarea
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            documentType === "pptx"
              ? "e.g., 'Create a presentation on AI misinformation using this PPT's theme with diagrams.' (Press Ctrl+Enter to generate)"
              : "e.g., 'Create a comprehensive report on AlphaGo with benchmark tables, diagrams, and keep the exact corporate theme.' (Press Ctrl+Enter to generate)"
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

      {/* Visual Figure & Image Director Controls */}
      <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-zinc-200">
            <input
              type="checkbox"
              checked={includeImages}
              onChange={(e) => setIncludeImages(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-800 text-cyan-500 focus:ring-cyan-400"
            />
            <ImageIcon className="h-4 w-4 text-cyan-400" />
            <span>Include High-Resolution Images & Figures</span>
          </label>
        </div>

        {includeImages && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-zinc-400">Mode:</span>
            <div className="flex rounded-lg bg-zinc-800 p-0.5 border border-zinc-700">
              <button
                type="button"
                onClick={() => setImageMode("search")}
                className={`px-2.5 py-0.5 rounded text-[11px] font-semibold transition-all ${
                  imageMode === "search" ? "bg-cyan-500 text-zinc-950 font-bold" : "text-zinc-400 hover:text-white"
                }`}
              >
                🔍 Real Search
              </button>
              <button
                type="button"
                onClick={() => setImageMode("generate")}
                className={`px-2.5 py-0.5 rounded text-[11px] font-semibold transition-all ${
                  imageMode === "generate" ? "bg-indigo-600 text-white font-bold" : "text-zinc-400 hover:text-white"
                }`}
              >
                🎨 AI Synth
              </button>
              <button
                type="button"
                onClick={() => setImageMode("auto")}
                className={`px-2.5 py-0.5 rounded text-[11px] font-semibold transition-all ${
                  imageMode === "auto" ? "bg-emerald-500 text-zinc-950 font-bold" : "text-zinc-400 hover:text-white"
                }`}
              >
                ⚡ Auto Sourcing
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Advanced Options Accordion */}
      <div className="mt-4 border-t border-zinc-800/80 pt-3">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5"
        >
          {showAdvanced ? "− Hide generation options" : "+ Show advanced options (sections, surgical theme overrides)"}
        </button>

        {showAdvanced && (
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 rounded-xl bg-zinc-900/60 p-4 border border-zinc-800">
            <div>
              <label className="block text-xs font-semibold text-zinc-300">
                Target {documentType === "pptx" ? "Slide Count" : "Section Count"}
              </label>
              <input
                type="number"
                min={1}
                max={15}
                value={targetCount}
                onChange={(e) => setTargetCount(e.target.value === "" ? "" : parseInt(e.target.value, 10) || 1)}
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-white focus:border-cyan-400 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-300">
                Surgical Theme Override / Special Focus
              </label>
              <input
                type="text"
                value={customInstructions}
                onChange={(e) => setCustomInstructions(e.target.value)}
                placeholder="e.g., 'Change blue border to yellow' or 'Include MCTS comparison table'"
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-white focus:border-cyan-400 focus:outline-none"
              />
            </div>
          </div>
        )}
      </div>

      {/* Action Bar */}
      <div className="mt-5 flex items-center justify-between border-t border-zinc-800/80 pt-4">
        <div className="text-[11px] text-zinc-400">
          Strict Style Lock guarantees original fonts, borders, and margins remain 100% untouched.
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
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <span>Generating Artifact...</span>
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              <span>Generate with Exact Template</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </form>
  );
}
