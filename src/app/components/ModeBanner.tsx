"use client";

import React from "react";
import { AlertTriangle, AlertCircle } from "lucide-react";

interface ModeBannerProps {
  mode?: "live" | "demo" | "misconfigured";
  provider?: string;
}

export function ModeBanner({ mode, provider }: ModeBannerProps) {
  if (mode === "demo") {
    return (
      <div className="bg-amber-950/80 border-b border-amber-500/40 px-6 py-2 text-xs text-amber-200 flex items-center justify-between">
        <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
          <span>
            <strong>DEMO CONTENT MODE:</strong> Generated documents will use deterministic sample text labeled as demo content. To enable live AI writing, configure an API key in your server environment.
          </span>
        </div>
      </div>
    );
  }

  if (mode === "misconfigured") {
    return (
      <div className="bg-red-950/90 border-b border-red-500/50 px-6 py-3 text-xs text-red-200 flex items-center justify-between">
        <div className="flex items-center gap-2.5 max-w-7xl mx-auto w-full">
          <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
          <span>
            <strong>PROVIDER MISCONFIGURED:</strong> The {provider || "LLM"} provider is active but required API credentials or server endpoints are not configured. Generation requests will return 503 until credentials are provided.
          </span>
        </div>
      </div>
    );
  }

  return null;
}
