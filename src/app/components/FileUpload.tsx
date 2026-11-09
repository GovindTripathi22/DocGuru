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
        className={`group relative flex w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-all duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sky-500 sm:p-7 ${
          isDragOver
            ? "border-sky-500 bg-sky-50/80 shadow-[0_0_35px_rgba(14,165,233,0.3)] scale-[1.01]"
            : "border-sky-300/80 bg-white/70 hover:border-sky-500 hover:bg-white/95 hover:shadow-[0_8px_30px_rgba(14,165,233,0.22)] hover:scale-[1.005]"
        } ${isLoading ? "pointer-events-none opacity-60" : ""}`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 via-sky-600 to-cyan-500 text-white shadow-[0_0_20px_rgba(14,165,233,0.35)] group-hover:scale-110 group-hover:shadow-[0_0_26px_rgba(14,165,233,0.5)] transition-all duration-300">
          {isLoading ? (
            <Loader2 className="h-6 w-6 animate-spin text-white motion-reduce:animate-none" />
          ) : (
            <Upload className="h-6 w-6 text-white" />
          )}
        </div>

        <div className="mt-3">
          <p className="text-base font-bold text-slate-900">
            {isLoading
              ? "Analyzing template structure and styles..."
              : "Upload Base Template Artifact"}
          </p>
          <p className="mt-1 text-xs text-slate-500 font-medium tabular-nums">
            Drag & drop your DOCX, PPTX, or PDF here, or press Enter to browse (up to {maxUploadMB} MB)
          </p>
          <span id="upload-help" className="sr-only">
            DOCX, PPTX, or PDF files up to {maxUploadMB} megabytes.
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-center gap-3 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50/90 px-3 py-1.5 font-semibold text-sky-700 shadow-sm">
            <FileText className="h-3.5 w-3.5 text-sky-600" /> DOCX (Word)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50/90 px-3 py-1.5 font-semibold text-amber-700 shadow-sm">
            <Presentation className="h-3.5 w-3.5 text-amber-600" /> PPTX (PowerPoint)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50/90 px-3 py-1.5 font-semibold text-rose-700 shadow-sm">
            <FileCode className="h-3.5 w-3.5 text-rose-600" /> PDF (Reference)
          </span>
        </div>
      </button>

      {error && (
        <div
          id="upload-error"
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2.5 rounded-xl border border-rose-300 bg-rose-50 p-3.5 text-xs text-rose-800 shadow-sm"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span className="font-medium">{error}</span>
        </div>
      )}

      {/* Built-in Sample Templates for Instant Testing */}
      <div className="rounded-2xl border border-sky-200/80 bg-white/80 p-4.5 backdrop-blur-xl shadow-[0_4px_20px_rgba(186,230,253,0.3)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-sky-200/60">
          <div>
            <h4 className="text-xs font-bold text-slate-800">
              No template file on hand? Load a verified sample template
            </h4>
            <p className="text-[11px] text-slate-500 mt-0.5 font-medium">
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
                className="group flex flex-col justify-between rounded-xl border border-sky-200/70 bg-white/90 p-3.5 text-left transition-all duration-300 ease-out hover:border-sky-500 hover:bg-sky-50/60 hover:shadow-[0_6px_22px_rgba(14,165,233,0.18)] hover:scale-[1.015] active:scale-[0.99] disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-500"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-800 group-hover:text-sky-700 transition-colors whitespace-nowrap">
                      {preset.label}
                    </span>
                    {isPresetLoading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-600 shrink-0" />
                    ) : (
                      <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-sky-600 transition-colors shrink-0" />
                    )}
                  </div>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500 font-medium">
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
