"use client";

import React, { useState } from "react";
import { Header } from "./components/Header";
import { FileUpload } from "./components/FileUpload";
import { TemplateLockDisplay } from "./components/TemplateLockDisplay";
import { PromptInput } from "./components/PromptInput";
import { GenerationPreview } from "./components/GenerationPreview";
import { DiffViewer } from "./components/DiffViewer";
import { Shield } from "lucide-react";
import { TemplateUploadResponse, PromptData, GenerationResult } from "@/types/template";

export default function Home() {
  const [templateData, setTemplateData] = useState<TemplateUploadResponse | null>(null);
  const [isLoadingTemplate, setIsLoadingTemplate] = useState(false);
  const [pendingPromptData, setPendingPromptData] = useState<PromptData | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleTemplateLoaded = (data: TemplateUploadResponse) => {
    setTemplateData(data);
    setPendingPromptData(null);
    setGenerationResult(null);
    setError(null);
  };

  const handlePromptSubmit = (data: PromptData) => {
    setPendingPromptData(data);
    setError(null);
  };

  const handleExecuteGeneration = async () => {
    if (!templateData || !pendingPromptData) return;

    setIsGenerating(true);
    setError(null);

    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: templateData.template_id,
          prompt: pendingPromptData.prompt,
          document_type: templateData.document_type,
          mode: pendingPromptData.mode,
          target_pages_or_slides: pendingPromptData.targetPagesOrSlides,
          custom_instructions: pendingPromptData.customInstructions,
          include_images: pendingPromptData.includeImages ?? true,
          image_mode: pendingPromptData.imageMode ?? "auto",
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: "Generation failed." }));
        throw new Error(errData.error || errData.detail || "Generation failed.");
      }

      const result = await response.json();
      setGenerationResult(result);
      setPendingPromptData(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An error occurred during artifact generation.";
      setError(message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleReset = () => {
    setTemplateData(null);
    setPendingPromptData(null);
    setGenerationResult(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] font-sans antialiased text-zinc-100 flex flex-col selection:bg-cyan-500 selection:text-zinc-950">
      <Header />

      <main className="mx-auto flex-1 w-full max-w-6xl px-6 py-8">
        {/* Futuristic Hero Banner */}
        <div className="mb-8 rounded-3xl bg-gradient-to-br from-zinc-900/90 via-slate-950 to-zinc-950 p-8 text-white shadow-2xl shadow-cyan-950/20 border border-cyan-500/25 relative overflow-hidden">
          <div className="absolute top-0 right-0 -mt-8 -mr-8 h-48 w-48 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none"></div>
          <div className="absolute bottom-0 left-1/3 -mb-8 h-32 w-64 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none"></div>
          
          <div className="max-w-3xl relative z-10">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-cyan-950/80 px-3.5 py-1 text-xs font-semibold text-cyan-300 border border-cyan-500/30 shadow-xs shadow-cyan-500/20">
              <Shield className="h-3.5 w-3.5 text-cyan-400" />
              <span>Exact Template Inheritance Architecture</span>
            </div>
            <h2 className="mt-4 text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Never recreate themes from scratch.
              <span className="block bg-gradient-to-r from-cyan-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">
                Modify the existing artifact programmatically.
              </span>
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-300">
              Supply any DOCX, PPTX, or PDF. Local Gemma 4 plans the content, sources relevant visual figures, and strictly reuses existing heading styles, slide masters, and table structures without mutating fonts, margins, or sacred borders.
            </p>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 rounded-2xl border border-rose-500/40 bg-rose-950/40 p-4 text-sm text-rose-300 flex items-center justify-between">
            <div>
              <strong>Error:</strong> {error}
            </div>
            <button
              onClick={() => setError(null)}
              className="text-xs bg-rose-900/60 px-2 py-1 rounded text-rose-200 hover:bg-rose-900"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Step 1: Upload or Display Loaded Template */}
        {!templateData && (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-bold text-white">
                Step 1: Provide Your Base Template
              </h3>
              <p className="text-xs text-zinc-400">
                Upload your branded presentation, report, or academic paper template
              </p>
            </div>

            <FileUpload
              onTemplateLoaded={handleTemplateLoaded}
              isLoading={isLoadingTemplate}
              setIsLoading={setIsLoadingTemplate}
            />
          </div>
        )}

        {/* Step 2: Template Loaded State */}
        {templateData && !generationResult && (
          <div className="space-y-6">
            <TemplateLockDisplay spec={templateData.template_spec} />

            {pendingPromptData ? (
              <GenerationPreview
                filename={templateData.original_filename}
                documentType={templateData.document_type}
                styleHash={templateData.template_spec?.style_hash || ""}
                prompt={pendingPromptData.prompt}
                isGenerating={isGenerating}
                onConfirm={handleExecuteGeneration}
                onCancel={() => setPendingPromptData(null)}
              />
            ) : (
              <PromptInput
                documentType={templateData.document_type}
                onGenerate={handlePromptSubmit}
                isGenerating={isGenerating}
                extractedRules={templateData.extracted_rules || templateData.template_spec?.extracted_rules}
                documentOutline={templateData.document_outline || templateData.template_spec?.document_outline}
              />
            )}
          </div>
        )}

        {/* Step 3: Generation & Diff Viewer Results */}
        {generationResult && (
          <div className="space-y-6">
            <DiffViewer
              outputFilename={generationResult.output_filename}
              downloadUrl={generationResult.download_url}
              validation={generationResult.validation}
              executionTime={generationResult.execution_time_sec}
              plan={generationResult.plan}
              documentType={templateData?.document_type || "docx"}
              onReset={handleReset}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-zinc-800/80 py-6 text-center text-xs text-zinc-500">
        Exact Template Inheritance System • Gemma 4 Agentic Engine • Python-Docx & Python-Pptx OXML Architecture
      </footer>
    </div>
  );
}
