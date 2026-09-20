"use client";

import React, { useState } from "react";
import { Header } from "./components/Header";
import { ModeBanner } from "./components/ModeBanner";
import { FileUpload } from "./components/FileUpload";
import { TemplateLockDisplay } from "./components/TemplateLockDisplay";
import { PromptInput } from "./components/PromptInput";
import { ProgressPanel } from "./components/ProgressPanel";
import { ResultPanel, GenerationResultData } from "./components/ResultPanel";
import { Shield } from "lucide-react";
import { TemplateUploadResponse, PromptData } from "@/types/template";

export default function Home() {
  const [templateData, setTemplateData] = useState<TemplateUploadResponse | null>(null);
  const [isLoadingTemplate, setIsLoadingTemplate] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [generationResult, setGenerationResult] = useState<GenerationResultData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<{ mode?: "live" | "demo" | "misconfigured"; model_provider?: string } | null>(null);

  const handleTemplateLoaded = (data: TemplateUploadResponse) => {
    setTemplateData(data);
    setActiveJobId(null);
    setGenerationResult(null);
    setError(null);
  };

  const handlePromptSubmit = async (data: PromptData) => {
    if (!templateData) return;
    setError(null);

    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: templateData.template_id,
          prompt: data.prompt,
          document_type: templateData.document_type,
          mode: data.mode,
          target_pages_or_slides: data.targetPagesOrSlides,
          custom_instructions: data.customInstructions,
          include_images: data.includeImages ?? true,
          image_mode: data.imageMode ?? "auto",
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: "Generation request failed." }));
        throw new Error(errData.error?.message || errData.error || errData.detail || "Generation request failed.");
      }

      const resData = await response.json();
      if (resData.job_id) {
        setActiveJobId(resData.job_id);
      } else {
        setGenerationResult(resData);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to initiate document generation.";
      setError(message);
    }
  };

  const handleReset = () => {
    setTemplateData(null);
    setActiveJobId(null);
    setGenerationResult(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] font-sans antialiased text-zinc-100 flex flex-col">
      <Header onHealthUpdate={setHealthData} />
      <ModeBanner mode={healthData?.mode} provider={healthData?.model_provider} />

      <main className="mx-auto flex-1 w-full max-w-6xl px-6 py-8">
        {/* Hero Section */}
        <div className="mb-8 rounded-3xl bg-zinc-950 p-8 text-white border border-zinc-800 relative overflow-hidden">
          <div className="max-w-3xl relative z-10 space-y-3">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-zinc-900 px-3.5 py-1 text-xs font-medium text-zinc-300 border border-zinc-800">
              <Shield className="h-3.5 w-3.5 text-indigo-400" />
              <span>Exact Template Inheritance Architecture</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Generate new content while preserving template design.
            </h2>
            <p className="text-sm leading-relaxed text-zinc-400">
              Upload a DOCX, PPTX, or PDF template and give a prompt. DocGuru generates fresh, tailored content while inheriting typography, page setup, header/footer layouts, and slide masters without unexpected formatting drift.
            </p>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mb-6 rounded-2xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-300 flex items-center justify-between">
            <div>
              <strong>Error:</strong> {error}
            </div>
            <button
              onClick={() => setError(null)}
              className="text-xs bg-red-900/60 px-2 py-1 rounded text-red-200 hover:bg-red-900"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Step 1: Upload Template */}
        {!templateData && (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-white">Select Base Template</h3>
              <p className="text-xs text-zinc-400 mt-1">
                Upload a DOCX, PPTX, or reference PDF template to extract layout invariants
              </p>
            </div>

            <FileUpload
              onTemplateLoaded={handleTemplateLoaded}
              isLoading={isLoadingTemplate}
              setIsLoading={setIsLoadingTemplate}
            />
          </div>
        )}

        {/* Step 2: Template Loaded & Prompt Input / Progress */}
        {templateData && !generationResult && (
          <div className="space-y-6">
            <TemplateLockDisplay spec={templateData.template_spec} />

            {activeJobId ? (
              <ProgressPanel
                jobId={activeJobId}
                onComplete={(result) => {
                  setGenerationResult(result);
                  setActiveJobId(null);
                }}
                onError={(err) => {
                  setError(err.message || "Generation job failed.");
                  setActiveJobId(null);
                }}
                onCancel={() => {
                  setActiveJobId(null);
                }}
              />
            ) : (
              <PromptInput
                documentType={templateData.document_type}
                onGenerate={handlePromptSubmit}
                isGenerating={false}
                extractedRules={templateData.extracted_rules || templateData.template_spec?.extracted_rules}
                documentOutline={templateData.document_outline || templateData.template_spec?.document_outline}
              />
            )}
          </div>
        )}

        {/* Step 3: Result Display */}
        {generationResult && (
          <div className="space-y-6">
            <ResultPanel
              result={generationResult}
              templateType={templateData?.document_type || "docx"}
              onReset={handleReset}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-zinc-800/80 py-6 text-center text-xs text-zinc-500">
        DocGuru • Exact Template Inheritance System • Built with Next.js & FastAPI
      </footer>
    </div>
  );
}
