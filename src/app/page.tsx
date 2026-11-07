"use client";

import React, { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Header } from "./components/Header";
import { ModeBanner } from "./components/ModeBanner";
import { FileUpload } from "./components/FileUpload";
import { TemplateLockDisplay } from "./components/TemplateLockDisplay";
import { PromptInput } from "./components/PromptInput";
import { ProgressPanel } from "./components/ProgressPanel";
import { ResultPanel, GenerationResultData } from "./components/ResultPanel";
import { Shield, Check } from "lucide-react";
import { TemplateUploadResponse, PromptData } from "@/types/template";
import { buildGenerationPayload } from "@/lib/generation-request";

interface StoredWorkflow {
  templateData?: TemplateUploadResponse | null;
  activeJobId?: string | null;
  generationResult?: GenerationResultData | null;
  lastPrompt?: string;
}

function readStoredWorkflow(): StoredWorkflow | null {
  if (typeof window === "undefined") return null;
  try {
    const serialized = window.sessionStorage.getItem("docguru-workflow");
    return serialized ? (JSON.parse(serialized) as StoredWorkflow) : null;
  } catch {
    return null;
  }
}

const subscribeToHydration = () => () => {};
const getClientHydrationSnapshot = () => true;
const getServerHydrationSnapshot = () => false;

export default function Home() {
  const [initialWorkflow] = useState(readStoredWorkflow);
  const [templateData, setTemplateData] = useState<TemplateUploadResponse | null>(
    initialWorkflow?.templateData || null,
  );
  const [isLoadingTemplate, setIsLoadingTemplate] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(
    initialWorkflow?.activeJobId || null,
  );
  const [generationResult, setGenerationResult] = useState<GenerationResultData | null>(
    initialWorkflow?.generationResult || null,
  );
  const [lastPrompt, setLastPrompt] = useState<string>(initialWorkflow?.lastPrompt || "");
  const [error, setError] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<{
    mode?: "live" | "demo" | "misconfigured";
    model_provider?: string;
    capabilities?: {
      research?: boolean;
      images?: boolean;
      image_placeholders?: boolean;
      preview?: boolean;
      max_upload_mb?: number;
    };
  } | null>(null);
  const restoredSession = useSyncExternalStore(
    subscribeToHydration,
    getClientHydrationSnapshot,
    getServerHydrationSnapshot,
  );
  const generationController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!restoredSession) return;
    if (!templateData && !activeJobId && !generationResult) {
      sessionStorage.removeItem("docguru-workflow");
      return;
    }
    sessionStorage.setItem(
      "docguru-workflow",
      JSON.stringify({ templateData, activeJobId, generationResult, lastPrompt }),
    );
  }, [restoredSession, templateData, activeJobId, generationResult, lastPrompt]);

  useEffect(() => {
    if (!activeJobId) return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [activeJobId]);

  useEffect(() => () => generationController.current?.abort(), []);

  const handleTemplateLoaded = (data: TemplateUploadResponse) => {
    setTemplateData(data);
    setActiveJobId(null);
    setGenerationResult(null);
    setError(null);
  };

  const handlePromptSubmit = async (data: PromptData) => {
    if (!templateData) return;
    setError(null);
    setLastPrompt(data.prompt);

    const controller = new AbortController();
    try {
      generationController.current?.abort();
      generationController.current = controller;
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify(
          buildGenerationPayload(templateData.template_id, templateData.document_type, data),
        ),
      });

      if (!response.ok) {
        const errData = await response
          .json()
          .catch(() => ({ detail: "Generation request failed." }));
        throw new Error(
          errData.error?.message ||
            errData.error ||
            errData.detail ||
            "Generation request failed.",
        );
      }

      const resData = await response.json();
      if (resData.job_id) {
        setActiveJobId(resData.job_id);
      } else {
        setGenerationResult(resData);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const message =
        err instanceof Error ? err.message : "Failed to initiate document generation.";
      setError(message);
    } finally {
      if (generationController.current === controller) generationController.current = null;
    }
  };

  const handleReset = () => {
    setTemplateData(null);
    setActiveJobId(null);
    setGenerationResult(null);
    setLastPrompt("");
    setError(null);
    sessionStorage.removeItem("docguru-workflow");
  };

  const handleEditPrompt = () => {
    setGenerationResult(null);
    setActiveJobId(null);
    setError(null);
  };

  const currentStep = generationResult ? 3 : templateData ? 2 : 1;

  const handleStepClick = (targetStep: number) => {
    if (targetStep === 1 && currentStep > 1) {
      handleReset();
    } else if (targetStep === 2 && currentStep === 3) {
      handleEditPrompt();
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] font-sans antialiased text-zinc-100 flex flex-col">
      <Header onHealthUpdate={setHealthData} />
      <ModeBanner mode={healthData?.mode} provider={healthData?.model_provider} />

      <main className="mx-auto flex-1 w-full max-w-6xl px-6 py-5">
        {/* Hero Section — compact once a template is loaded so the workspace stays front and center */}
        {currentStep === 1 ? (
          <div className="mb-5 rounded-2xl bg-zinc-950 p-6 text-white border border-zinc-800 relative overflow-hidden">
            <div className="max-w-3xl relative z-10 space-y-2">
              <div className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-300">
                <Shield className="h-3.5 w-3.5 text-indigo-400" />
                <span>Template-aware document generation</span>
              </div>
              <h2
                style={{ textWrap: "balance" }}
                className="text-2xl sm:text-3xl font-bold tracking-tight text-white"
              >
                Generate new content while preserving template design.
              </h2>
              <p className="text-sm leading-relaxed text-zinc-400">
                Upload a DOCX or PPTX template, or a PDF reference, and describe what you need.
                DocGuru generates content using the selected template and compares supported style
                and layout properties after generation. PDF output uses an approximate layout
                reference.
              </p>
            </div>
          </div>
        ) : (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-800/80 bg-zinc-950/60 px-4 py-2.5">
            <div className="flex items-center gap-2 text-xs text-zinc-300">
              <Shield className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
              <h2 className="font-semibold text-white">
                Generate new content while preserving template design.
              </h2>
            </div>
            <span className="text-[11px] text-zinc-400 hidden sm:inline">
              Click any completed step below to go back and adjust settings
            </span>
          </div>
        )}

        {/* Interactive Workflow Stepper */}
        {restoredSession && (
          <nav
            aria-label="Document generation workflow steps"
            className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3"
          >
            {[
              { step: 1, title: "01. Select Base Template", desc: "Upload DOCX, PPTX, or PDF" },
              {
                step: 2,
                title: "02. Configure & Generate",
                desc: "Set prompt, rules, and length",
              },
              {
                step: 3,
                title: "03. Verify & Export",
                desc: "Inspect style diff and download",
              },
            ].map((item) => {
              const isActive = currentStep === item.step;
              const isCompleted = currentStep > item.step;
              const isClickable = isCompleted;
              return (
                <button
                  key={item.step}
                  type="button"
                  disabled={!isClickable}
                  onClick={() => handleStepClick(item.step)}
                  className={`flex items-center justify-between rounded-xl border px-4 py-2.5 text-left text-xs transition-all ${
                    isActive
                      ? "border-indigo-500/60 bg-indigo-950/25 text-white shadow-sm"
                      : isCompleted
                      ? "cursor-pointer border-emerald-500/35 bg-emerald-950/15 text-zinc-200 hover:border-emerald-400/60 hover:bg-emerald-950/25"
                      : "cursor-default border-zinc-800/80 bg-zinc-950/40 text-zinc-500"
                  }`}
                >
                  <div>
                    <div className="font-semibold">{item.title}</div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">{item.desc}</div>
                  </div>
                  {isCompleted && (
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                      <Check className="h-3 w-3" />
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        )}

        {/* Error Notification */}
        {error && (
          <div
            role="alert"
            aria-live="assertive"
            className="mb-5 rounded-2xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-300 flex items-center justify-between"
          >
            <div>
              <strong>Error:</strong> {error}
            </div>
            <button
              onClick={() => setError(null)}
              className="text-xs bg-red-900/60 px-2.5 py-1 rounded text-red-200 hover:bg-red-900 whitespace-nowrap shrink-0"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Step 1: Upload Template */}
        {restoredSession && !templateData && (
          <div className="space-y-4">
            <div className="text-center">
              <h3 className="text-base font-semibold text-white">Select Base Template</h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Upload a DOCX or PPTX template, or a PDF reference, to analyze its available
                properties
              </p>
            </div>

            <FileUpload
              onTemplateLoaded={handleTemplateLoaded}
              isLoading={isLoadingTemplate}
              setIsLoading={setIsLoadingTemplate}
              maxUploadMB={healthData?.capabilities?.max_upload_mb}
            />
          </div>
        )}

        {/* Step 2: Template Loaded & Prompt Input / Progress */}
        {restoredSession && templateData && !generationResult && (
          <div className="space-y-4">
            <TemplateLockDisplay spec={templateData.template_spec} onReset={handleReset} />

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
                key={templateData.template_id}
                documentType={templateData.document_type}
                researchAvailable={healthData?.capabilities?.research === true}
                researchCapabilityKnown={healthData !== null}
                imageSearchAvailable={healthData?.capabilities?.images}
                placeholdersAvailable={healthData?.capabilities?.image_placeholders}
                onGenerate={handlePromptSubmit}
                isGenerating={false}
                initialPrompt={lastPrompt}
                extractedRules={
                  templateData.extracted_rules || templateData.template_spec?.extracted_rules
                }
                documentOutline={
                  templateData.document_outline || templateData.template_spec?.document_outline
                }
              />
            )}
          </div>
        )}

        {/* Step 3: Result Display */}
        {restoredSession && generationResult && (
          <div className="space-y-5">
            <ResultPanel
              result={generationResult}
              templateType={templateData?.document_type || "docx"}
              previewAvailable={healthData?.capabilities?.preview === true}
              onReset={handleReset}
              onEditPrompt={handleEditPrompt}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-zinc-800/80 py-5 text-center text-xs text-zinc-400">
        DocGuru • Template-aware document generation
      </footer>
    </div>
  );
}
