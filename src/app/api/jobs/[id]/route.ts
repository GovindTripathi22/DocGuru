import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { CancelJobSchema, JobProgressSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";
import { cancelStandaloneJob, getStandaloneJob } from "@/lib/standalone-engine";

function hasExternalBackendEnv(): boolean {
  const url = process.env.BACKEND_URL?.trim();
  const secret = process.env.SESSION_SECRET?.trim();
  return Boolean(url && secret && secret.length >= 32 && !secret.toLowerCase().includes("replace-with"));
}

export async function GET(
  req: NextRequest,
  props: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await props.params;
    const standaloneJob = getStandaloneJob(id);
    if (standaloneJob) {
      return NextResponse.json(standaloneJob, { status: 200 });
    }

    if (hasExternalBackendEnv()) {
      const res = await backendFetch(`/api/jobs/${encodeURIComponent(id)}`);
      return proxyJsonResponse(res, JobProgressSchema);
    }

    return NextResponse.json(
      { error: { code: "JOB_NOT_FOUND", message: "Job not found on server." } },
      { status: 404 },
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to fetch job";
    return NextResponse.json({ error: { code: "JOB_ERROR", message }, detail: message }, { status: 500 });
  }
}

export async function DELETE(
  req: NextRequest,
  props: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await props.params;
    const cancelled = cancelStandaloneJob(id);
    if (cancelled) {
      return NextResponse.json(
        {
          job_id: cancelled.job_id,
          status: cancelled.status,
          message: "Job cancelled successfully.",
        },
        { status: 200 },
      );
    }

    if (hasExternalBackendEnv()) {
      const res = await backendFetch(`/api/jobs/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      return proxyJsonResponse(res, CancelJobSchema);
    }

    return NextResponse.json(
      { error: { code: "JOB_NOT_FOUND", message: "Job not found on server." } },
      { status: 404 },
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to cancel job";
    return NextResponse.json({ error: { code: "JOB_ERROR", message }, detail: message }, { status: 500 });
  }
}
