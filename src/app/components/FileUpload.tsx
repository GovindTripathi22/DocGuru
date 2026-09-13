"use client";

import React, { useState, useRef } from "react";
import { Upload, FileText, Presentation, FileCode, AlertCircle, Loader2 } from "lucide-react";
import { TemplateUploadResponse } from "@/types/template";

interface FileUploadProps {
  onTemplateLoaded: (templateData: TemplateUploadResponse) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

export function FileUpload({ onTemplateLoaded, isLoading, setIsLoading }: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setError(null);
    const validExtensions = [".docx", ".pptx", ".pdf"];
    const fileExt = "." + file.name.split(".").pop()?.toLowerCase();

    if (!validExtensions.includes(fileExt)) {
      setError(`Invalid file type "${fileExt}". Please upload a DOCX, PPTX, or PDF file.`);
      return;
    }

    setIsLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || "Failed to upload and analyze template.");
      }

      const data = await response.json();
      onTemplateLoaded(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An unexpected error occurred during upload.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="w-full">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 sm:p-8 text-center transition-all ${
          isDragOver
            ? "border-indigo-500 bg-indigo-50/50 dark:border-indigo-400 dark:bg-indigo-950/20"
            : "border-zinc-300 bg-zinc-50/50 hover:border-zinc-400 hover:bg-zinc-100/50 dark:border-zinc-700 dark:bg-zinc-900/40 dark:hover:border-zinc-600"
        } ${isLoading ? "pointer-events-none opacity-60" : ""}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx,.pptx,.pdf"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleFile(e.target.files[0]);
            }
          }}
        />

        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-md shadow-zinc-200/50 ring-1 ring-zinc-200 group-hover:scale-105 transition-transform dark:bg-zinc-800 dark:shadow-none dark:ring-zinc-700">
          {isLoading ? (
            <Loader2 className="h-7 w-7 animate-spin text-indigo-600 dark:text-indigo-400" />
          ) : (
            <Upload className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
          )}
        </div>

        <div className="mt-4">
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {isLoading ? "Analyzing template structure and styles..." : "Upload Base Template Artifact"}
          </p>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            Drag & drop your DOCX, PPTX, or PDF here, or click to browse
          </p>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-400">
            <FileText className="h-3.5 w-3.5" /> DOCX (Word)
          </span>
          <span className="inline-flex items-center gap-1 rounded-lg border border-orange-200 bg-orange-50 px-3 py-1.5 text-xs font-semibold text-orange-700 dark:border-orange-900/60 dark:bg-orange-950/40 dark:text-orange-400">
            <Presentation className="h-3.5 w-3.5" /> PPTX (PowerPoint)
          </span>
          <span className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-400">
            <FileCode className="h-3.5 w-3.5" /> PDF (Reference)
          </span>
        </div>
      </div>

      {error && (
        <div className="mt-3 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
