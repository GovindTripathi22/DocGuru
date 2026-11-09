"use client";

import React, { useEffect, useState, useRef } from "react";
import { Upload, FileText, Presentation, FileCode, AlertCircle, Loader2, ArrowUpRight } from "lucide-react";
import { TemplateUploadResponse } from "@/types/template";

interface FileUploadProps {
  onTemplateLoaded: (templateData: TemplateUploadResponse) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  maxUploadMB?: number;
}

const SAMPLE_PRESETS = [
  {
    id: "executive-docx",
    filename: "executive-architecture-report.docx",
    label: "Executive Report (.docx)",
    description: "Aptos typography, 72pt margins, header/footer & benchmark table styles",
    mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  },
  {
    id: "strategy-pptx",
    filename: "quarterly-strategy-briefing.pptx",
    label: "Strategy Deck (.pptx)",
    description: "16:9 widescreen slide geometry with Title, Content & Comparison layouts",
    mime: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  },
  {
    id: "reference-pdf",
    filename: "ieee-systems-specification.pdf",
    label: "Technical Reference (.pdf)",
    description: "612×792 pt reference geometry with formal numbered section guidelines",
    mime: "application/pdf",
  },
] as const;

function extractUploadErrorMessage(errData: unknown): string {
  if (!errData || typeof errData !== "object") {
    return "Failed to upload and analyze template.";
  }
  const record = errData as Record<string, unknown>;
  if (typeof record.error === "string" && record.error.trim()) {
    return record.error;
  }
  if (record.error && typeof record.error === "object") {
    const nested = record.error as Record<string, unknown>;
    if (typeof nested.message === "string" && nested.message.trim()) {
      return nested.message;
    }
  }
  if (typeof record.detail === "string" && record.detail.trim()) {
    return record.detail;
  }
  return "Failed to upload and analyze template.";
}

export function FileUpload({
  onTemplateLoaded,
  isLoading,
  setIsLoading,
  maxUploadMB = 25,
}: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadController = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      uploadController.current?.abort();
      uploadController.current = null;
    },
    [],
  );

  const handleFile = async (file: File, presetId?: string) => {
    setError(null);
    const validExtensions = [".docx", ".pptx", ".pdf"];
    const fileExt = "." + file.name.split(".").pop()?.toLowerCase();

    if (!validExtensions.includes(fileExt)) {
      setError(`Invalid file type "${fileExt}". Please upload a DOCX, PPTX, or PDF file.`);
      return;
    }
    if (file.size > maxUploadMB * 1024 * 1024) {
      setError(`File exceeds the ${maxUploadMB} MB upload limit.`);
      return;
    }

    setIsLoading(true);
    if (presetId) setActivePreset(presetId);
    const formData = new FormData();
    formData.append("file", file);
    if (presetId) {
      formData.append("preset", presetId);
    }
    uploadController.current?.abort();
    const controller = new AbortController();
    uploadController.current = controller;

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(extractUploadErrorMessage(errData));
      }

      const data = await response.json();
      onTemplateLoaded(data);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred during upload.";
      setError(message);
    } finally {
      if (uploadController.current === controller) {
        uploadController.current = null;
        setActivePreset(null);
        setIsLoading(false);
      }
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLButtonElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleSampleSelect = (preset: (typeof SAMPLE_PRESETS)[number]) => {
    const sampleFile = new File(["sample-template"], preset.filename, { type: preset.mime });
    void handleFile(sampleFile, preset.id);
  };

  return (
    <div className="w-full space-y-4">
      <input
        ref={fileInputRef}
        type="file"
        accept=".docx,.pptx,.pdf"
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose a DOCX, PPTX, or PDF template"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.currentTarget.value = "";
          if (file) void handleFile(file);
        }}
      />

      <button
        type="button"
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        disabled={isLoading}
        aria-describedby={error ? "upload-help upload-error" : "upload-help"}
        className={`group relative flex w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-400 sm:p-7 ${
          isDragOver
            ? "border-violet-400 bg-violet-950/30 shadow-[0_0_30px_rgba(139,92,246,0.3)] scale-[1.01]"
            : "border-white/10 bg-white/[0.02] hover:border-violet-500/50 hover:bg-white/[0.04] hover:shadow-[0_0_25px_rgba(139,92,246,0.12)] hover:scale-[1.005]"
        } ${isLoading ? "pointer-events-none opacity-60" : ""}`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-900/90 ring-1 ring-white/10 group-hover:scale-110 group-hover:ring-violet-500/50 group-hover:shadow-[0_0_20px_rgba(139,92,246,0.3)] transition-all duration-300">
          {isLoading ? (
            <Loader2 className="h-6 w-6 animate-spin text-indigo-400 motion-reduce:animate-none" />
          ) : (
            <Upload className="h-6 w-6 text-indigo-400" />
          )}
        </div>

        <div className="mt-3">
          <p className="text-base font-semibold text-zinc-100">
            {isLoading
              ? "Analyzing template structure and styles..."
              : "Upload Base Template Artifact"}
          </p>
          <p className="mt-1 text-xs text-zinc-400 tabular-nums">
            Drag & drop your DOCX, PPTX, or PDF here, or press Enter to browse (up to {maxUploadMB} MB)
          </p>
          <span id="upload-help" className="sr-only">
            DOCX, PPTX, or PDF files up to {maxUploadMB} megabytes.
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-center gap-3 text-xs text-zinc-300">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-1.5 font-medium text-blue-300">
            <FileText className="h-3.5 w-3.5 text-blue-400" /> DOCX (Word)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-1.5 font-medium text-amber-300">
            <Presentation className="h-3.5 w-3.5 text-amber-400" /> PPTX (PowerPoint)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-1.5 font-medium text-rose-300">
            <FileCode className="h-3.5 w-3.5 text-rose-400" /> PDF (Reference)
          </span>
        </div>
      </button>

      {error && (
        <div
          id="upload-error"
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2.5 rounded-xl border border-rose-500/40 bg-rose-950/30 p-3.5 text-xs text-rose-200"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Built-in Sample Templates for Instant Testing */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 backdrop-blur-xl shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-zinc-800/80">
          <div>
            <h4 className="text-xs font-semibold text-zinc-200">
              No template file on hand? Load a verified sample template
            </h4>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Inspect extracted OpenXML typography, margins, slide layouts, and style fingerprints immediately.
            </p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {SAMPLE_PRESETS.map((preset) => {
            const isPresetLoading = isLoading && activePreset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                disabled={isLoading}
                onClick={() => handleSampleSelect(preset)}
                className="group flex flex-col justify-between rounded-xl border border-white/10 bg-white/[0.02] p-3.5 text-left transition-all duration-300 ease-out hover:border-violet-500/60 hover:bg-white/[0.05] hover:shadow-[0_4px_20px_rgba(139,92,246,0.15)] hover:scale-[1.015] active:scale-[0.99] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-zinc-100 group-hover:text-indigo-300 transition-colors whitespace-nowrap">
                      {preset.label}
                    </span>
                    {isPresetLoading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400 shrink-0" />
                    ) : (
                      <ArrowUpRight className="h-3.5 w-3.5 text-zinc-500 group-hover:text-indigo-400 transition-colors shrink-0" />
                    )}
                  </div>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-400">
                    {preset.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
