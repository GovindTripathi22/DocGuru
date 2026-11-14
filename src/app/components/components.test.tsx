import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PromptData, TemplateSpec } from "@/types/template";
import { FileUpload } from "./FileUpload";
import { Header } from "./Header";
import { ModeBanner } from "./ModeBanner";
import { ProgressPanel } from "./ProgressPanel";
import { PromptInput } from "./PromptInput";
import { ResultPanel, type GenerationResultData } from "./ResultPanel";
import { TemplateLockDisplay } from "./TemplateLockDisplay";

function renderPromptInput(
  onGenerate = vi.fn<(data: PromptData) => void>(),
  props: Partial<React.ComponentProps<typeof PromptInput>> = {},
) {
  render(
    <PromptInput
      documentType="docx"
      researchAvailable
      researchCapabilityKnown
      imageSearchAvailable
      placeholdersAvailable={false}
      onGenerate={onGenerate}
      isGenerating={false}
      {...props}
    />,
  );
  return onGenerate;
}

function makeTemplateSpec(type: TemplateSpec["document_type"] = "docx"): TemplateSpec {
  return {
    filename: "template.docx",
    document_type: type,
    total_pages_or_slides: 4,
    style_hash: "abc123",
    page: {
      width_pt: 612,
      height_pt: 792,
      orientation: "portrait",
      margins: { top_pt: 72, bottom_pt: 72, left_pt: 72, right_pt: 72 },
    },
    slide_dimensions: { width_inches: 13.333, height_inches: 7.5, aspect_ratio: "16:9" },
    fonts: { default: "Aptos", all_detected_fonts: ["Aptos", "Aptos Display"] },
    available_heading_styles: ["Heading 1", "Heading 2"],
    available_layout_names: ["Title", "Content"],
    extracted_rules: ["Use numbered references."],
    document_outline: ["Introduction", "Conclusion"],
    table_rules: [{ rows: 2, cols: 3 }],
    header: { has_content: true, text_preview: "Organization" },
    footer: { has_content: true, text_preview: "Confidential" },
  };
}

function makeResult(overrides: Partial<GenerationResultData> = {}): GenerationResultData {
  return {
    success: true,
    output_filename: "report.docx",
    download_url: "/api/download/report.docx",
    template_id: "template-123",
    generation_mode: "live",
    plan_summary: [{ title: "Introduction" }, { title: "Conclusion" }],
    validation: { passed: true, status: "passed", original_style_hash: "source", generated_style_hash: "output" },
    execution_time_sec: 2.4,
    research_sources: [
      { id: "source-1", title: "Grid Integration Review", url: "https://example.test/grid", published_date: "2026-01-01" },
    ],
    warnings: ["Search results were not independently verified."],
    ...overrides,
  };
}

describe("PromptInput", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("starts at Medium and submits a detail-only request", async () => {
    const user = userEvent.setup();
    const onGenerate = renderPromptInput();

    expect(screen.getByRole("button", { name: /Medium.*5 pages/i })).toHaveAttribute("aria-pressed", "true");
    await user.type(screen.getByRole("textbox", { name: "Document prompt" }), "Grid integration risks");
    await user.click(screen.getByRole("button", { name: /High.*10 pages/i }));
    await user.click(screen.getByRole("checkbox", { name: /Research sources/i }));
    await user.click(screen.getByRole("button", { name: /Generate using this template/i }));

    expect(onGenerate).toHaveBeenCalledWith(expect.objectContaining({
      prompt: "Grid integration risks",
      detailLevel: "high",
      researchEnabled: true,
    }));
    expect(onGenerate.mock.calls[0][0]).not.toHaveProperty("targetPages");
  });

  it("submits a page target without a detail preset", async () => {
    const user = userEvent.setup();
    const onGenerate = renderPromptInput();

    await user.type(screen.getByRole("textbox", { name: "Document prompt" }), "A practical guide");
    await user.click(screen.getByRole("button", { name: "Choose pages" }));
    await user.clear(screen.getByLabelText(/Approximate page count/i));
    await user.type(screen.getByLabelText(/Approximate page count/i), "12");
    await user.click(screen.getByRole("button", { name: /Generate using this template/i }));

    expect(onGenerate.mock.calls[0][0]).toMatchObject({ targetPages: 12, researchEnabled: false });
    expect(onGenerate.mock.calls[0][0]).not.toHaveProperty("detailLevel");
  });

  it("lets the user choose which detected template rules are sent", async () => {
    const user = userEvent.setup();
    const onGenerate = renderPromptInput(vi.fn(), {
      extractedRules: ["Use numbered references.", "Include a glossary."],
    });

    const includeReferences = screen.getByRole("checkbox", { name: "Use numbered references." });
    const includeGlossary = screen.getByRole("checkbox", { name: "Include a glossary." });
    expect(includeReferences).toBeChecked();
    expect(includeGlossary).toBeChecked();
    await user.click(includeGlossary);
    await user.type(screen.getByRole("textbox", { name: "Document prompt" }), "Write a concise guide");
    await user.click(screen.getByRole("button", { name: /Generate using this template/i }));

    expect(onGenerate.mock.calls[0][0]).toMatchObject({ enabledRuleIndexes: [0] });
  });

  it("uses slide count for presentations and hides document length controls", async () => {
    const user = userEvent.setup();
    const onGenerate = renderPromptInput(vi.fn(), { documentType: "pptx" });

    expect(screen.queryByText("Document length")).not.toBeInTheDocument();
    await user.type(screen.getByRole("textbox"), "A 7-slide strategy deck");
    await user.clear(screen.getByLabelText("Target slide count"));
    await user.type(screen.getByLabelText("Target slide count"), "7");
    await user.click(screen.getByRole("button", { name: /Generate using this template/i }));

    expect(onGenerate.mock.calls[0][0]).toMatchObject({ targetSlides: 7, researchEnabled: false });
  });

  it("explains why unavailable research is disabled", () => {
    renderPromptInput(vi.fn(), { researchAvailable: false });
    expect(screen.getByRole("checkbox", { name: /Research sources/i })).toBeDisabled();
    expect(screen.getByText(/no Tavily API key configured/i)).toBeInTheDocument();
  });

  it("reports prompt enhancement failures and keeps the prompt editable", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    renderPromptInput();
    const prompt = screen.getByRole("textbox", { name: "Document prompt" });
    await user.type(prompt, "Quarterly outcomes");
    await user.click(screen.getByRole("button", { name: /Enhance/i }));

    expect(await screen.findByText(/Could not enhance prompt/i)).toBeInTheDocument();
    expect(prompt).toHaveValue("Quarterly outcomes");
  });

  it("sends optional audience instructions and image preference", async () => {
    const user = userEvent.setup();
    const onGenerate = renderPromptInput();
    await user.type(screen.getByRole("textbox", { name: "Document prompt" }), "A report for teams");
    await user.click(screen.getByRole("radio", { name: /No images/i }));
    await user.click(screen.getByRole("button", { name: /Show advanced options/i }));
    await user.type(screen.getByPlaceholderText(/Target audience/i), "Engineering managers");
    await user.click(screen.getByRole("button", { name: /Generate using this template/i }));

    expect(onGenerate.mock.calls[0][0]).toMatchObject({
      customInstructions: "Engineering managers",
      includeImages: false,
    });
  });

  it("supports switching between Document Rules (ON) and Custom Preferences (OFF)", async () => {
    const user = userEvent.setup();
    const onGenerate = renderPromptInput(vi.fn(), {
      hasEmbeddedRules: false,
    });

    // Defaults to custom when template has no embedded rules
    expect(screen.getByRole("button", { name: /Custom Preferences \(OFF\)/i })).toHaveAttribute("aria-pressed", "true");
    await user.selectOptions(screen.getByLabelText(/Font family/i), "Calibri");
    await user.selectOptions(screen.getByLabelText(/Line spacing/i), "2");
    await user.selectOptions(screen.getByLabelText(/Page size/i), "A4");

    await user.type(screen.getByRole("textbox", { name: "Document prompt" }), "System reliability handbook");
    await user.click(screen.getByRole("button", { name: /Generate using this template/i }));

    expect(onGenerate).toHaveBeenCalledWith(expect.objectContaining({
      ruleMode: "custom",
      customRules: expect.objectContaining({
        font_name: "Calibri",
        line_spacing: 2,
        page_size: "A4",
      }),
    }));

    // Toggle back to Document Rules mode when embedded rules are present
    cleanup();
    const onDocGenerate = vi.fn();
    renderPromptInput(onDocGenerate, {
      hasEmbeddedRules: true,
      detectedRuleCategories: ["typography", "margins"],
      parsedTypographyRules: {
        font_family: "Times New Roman",
        heading1: { size_pt: 14, alignment: "center" },
        body: { size_pt: 12, line_spacing: 1.5 },
      },
    });

    expect(screen.getByRole("button", { name: /Document Rules \(ON\)/i })).toHaveAttribute("aria-pressed", "true");
    await user.type(screen.getByRole("textbox", { name: "Document prompt" }), "Edge AI report");
    await user.click(screen.getByRole("button", { name: /Generate using this template/i }));

    expect(onDocGenerate).toHaveBeenCalledWith(expect.objectContaining({
      ruleMode: "document",
    }));
    expect(onDocGenerate.mock.calls[0][0]).not.toHaveProperty("customRules");
  });
});

describe("FileUpload", () => {
  it("rejects unsupported files before making a request", async () => {
    const onLoaded = vi.fn();
    const setLoading = vi.fn();
    const { container } = render(<FileUpload onTemplateLoaded={onLoaded} isLoading={false} setIsLoading={setLoading} />);
    const input = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).not.toBeNull();
    fireEvent.change(input!, { target: { files: [new File(["x"], "notes.txt")] } });

    expect(await screen.findByText(/Invalid file type/i)).toBeInTheDocument();
    expect(setLoading).not.toHaveBeenCalled();
    expect(onLoaded).not.toHaveBeenCalled();
  });

  it("opens the file chooser from the keyboard and exposes its instructions", async () => {
    const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    render(<FileUpload onTemplateLoaded={vi.fn()} isLoading={false} setIsLoading={vi.fn()} maxUploadMB={8} />);
    const button = screen.getByRole("button", { name: /Upload Base Template Artifact/i });
    expect(button).toHaveAttribute("aria-describedby", "upload-help");
    await userEvent.click(button);
    expect(click).toHaveBeenCalledOnce();
    expect(screen.getByText(/up to 8 MB/i)).toBeInTheDocument();
    click.mockRestore();
  });

  it("rejects uploads over the backend capability limit", async () => {
    const file = new File(["x"], "large.docx");
    Object.defineProperty(file, "size", { value: 9 * 1024 * 1024 });
    const setLoading = vi.fn();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(
      <FileUpload onTemplateLoaded={vi.fn()} isLoading={false} setIsLoading={setLoading} maxUploadMB={8} />,
    );
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });

    expect(await screen.findByRole("alert")).toHaveTextContent(/exceeds the 8 MB upload limit/i);
    expect(setLoading).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uploads supported templates and clears loading state", async () => {
    const onLoaded = vi.fn();
    const setLoading = vi.fn();
    const data = { template_id: "template-1", document_type: "docx" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => data }));
    const { container } = render(<FileUpload onTemplateLoaded={onLoaded} isLoading={false} setIsLoading={setLoading} />);
    const input = container.querySelector<HTMLInputElement>('input[type="file"]');
    fireEvent.change(input!, { target: { files: [new File(["doc"], "report.docx")] } });

    await waitFor(() => expect(onLoaded).toHaveBeenCalledWith(data));
    expect(setLoading.mock.calls).toEqual([[true], [false]]);
  });

  it("shows server upload errors and still clears loading state", async () => {
    const setLoading = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: "Rejected upload" }) }));
    const { container } = render(<FileUpload onTemplateLoaded={vi.fn()} isLoading={false} setIsLoading={setLoading} />);
    fireEvent.change(container.querySelector('input[type="file"]')!, {
      target: { files: [new File(["doc"], "report.pdf")] },
    });

    expect(await screen.findByText("Rejected upload")).toBeInTheDocument();
    expect(setLoading.mock.calls).toEqual([[true], [false]]);
  });

  it("extracts readable message from structured backend error objects and supports sample presets", async () => {
    const user = userEvent.setup();
    const onLoaded = vi.fn();
    const setLoading = vi.fn();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: { code: "INVALID_UPLOAD", message: "Template archive is corrupted." } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ template_id: "sample-1", document_type: "docx", template_spec: makeTemplateSpec("docx") }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<FileUpload onTemplateLoaded={onLoaded} isLoading={false} setIsLoading={setLoading} />);
    fireEvent.change(container.querySelector('input[type="file"]')!, {
      target: { files: [new File(["doc"], "broken.docx")] },
    });

    expect(await screen.findByText("Template archive is corrupted.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Executive Report \(\.docx\)/i }));
    await waitFor(() => expect(onLoaded).toHaveBeenCalledWith(expect.objectContaining({ template_id: "sample-1" })));
  });
});

describe("mode and template status components", () => {
  it("labels demo mode and explains misconfigured live mode", () => {
    const { rerender } = render(<ModeBanner mode="demo" />);
    expect(screen.getByText(/DEMO CONTENT MODE/i)).toBeInTheDocument();
    rerender(<ModeBanner mode="misconfigured" provider="google_ai" />);
    expect(screen.getByText(/PROVIDER MISCONFIGURED/i)).toBeInTheDocument();
    expect(screen.getByText(/google_ai provider/i)).toBeInTheDocument();
    rerender(<ModeBanner mode="live" />);
    expect(screen.queryByText(/DEMO CONTENT MODE/i)).not.toBeInTheDocument();
  });

  it.each(["docx", "pptx", "pdf"] as const)("renders detected %s template details", (documentType) => {
    render(<TemplateLockDisplay spec={makeTemplateSpec(documentType)} />);
    expect(screen.getByRole("heading", { name: "template.docx" })).toBeInTheDocument();
    expect(screen.getByText(/Template properties found/i)).toBeInTheDocument();
    expect(screen.getByText(/Use numbered references/i)).toBeInTheDocument();
    if (documentType === "pdf") expect(screen.getByText(/PDF Reference Mode/i)).toBeInTheDocument();
    if (documentType === "pptx") expect(screen.getByText(/Slide Dimensions/i)).toBeInTheDocument();
  });
});

describe("result preview availability", () => {
  it("explains when inline previews are unavailable", () => {
    render(
      <ResultPanel
        result={makeResult()}
        templateType="docx"
        previewAvailable={false}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText(/Inline preview is unavailable on this server/i)).toBeInTheDocument();
  });
});

describe("Header health status", () => {
  it.each([
    [{ mode: "demo", version: "2.0", model_provider: "demo", model_name: "local", ready: true }, "Demo Mode"],
    [{ mode: "live", version: "2.1", model_provider: "google_ai", model_name: "gemma", ready: true }, "Ready"],
    [{ mode: "misconfigured", model_provider: "google_ai", model_name: "gemma", ready: false }, "Misconfigured"],
  ] as const)("shows provider health for %s", async (data, status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => data }));
    const onHealthUpdate = vi.fn();
    render(<Header onHealthUpdate={onHealthUpdate} />);
    expect(await screen.findByText(status)).toBeInTheDocument();
    expect(screen.getByText(/Provider:/i)).toBeInTheDocument();
    expect(onHealthUpdate).toHaveBeenCalledWith(data);
  });

  it("reports offline health and notifies the parent", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    const onHealthUpdate = vi.fn();
    render(<Header onHealthUpdate={onHealthUpdate} />);
    expect(await screen.findByText("Offline")).toBeInTheDocument();
    expect(onHealthUpdate).toHaveBeenCalledWith(null);
  });
});

describe("ProgressPanel job lifecycle", () => {
  const result = makeResult();

  it("passes a succeeded job result to the parent", async () => {
    const onComplete = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ job_id: "job-1", status: "succeeded", stage: "done", progress: 1, message: "Ready", warnings: [], result }),
    }));
    render(<ProgressPanel jobId="job-1" onComplete={onComplete} onError={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(result));
  });

  it("passes a failed job error to the parent", async () => {
    const onError = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ job_id: "job-1", status: "failed", stage: "failed", progress: 0, message: "Failed", warnings: [], error: { code: "LLM_TIMEOUT", message: "Provider timed out" } }),
    }));
    render(<ProgressPanel jobId="job-1" onComplete={vi.fn()} onError={onError} onCancel={vi.fn()} />);
    await waitFor(() => expect(onError).toHaveBeenCalledWith({ code: "LLM_TIMEOUT", message: "Provider timed out" }));
  });

  it("reports missing jobs and allows cancelling a running job", async () => {
    const onError = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    const first = render(<ProgressPanel jobId="missing" onComplete={vi.fn()} onError={onError} onCancel={vi.fn()} />);
    await waitFor(() => expect(onError).toHaveBeenCalledWith({ message: "Job not found on server." }));
    first.unmount();

    const onCancel = vi.fn();
    const fetchMock = vi.fn().mockImplementation(async (_url: string, options?: RequestInit) => {
      if (options?.method === "DELETE") return { ok: true };
      return { ok: true, status: 200, json: async () => ({ job_id: "job-2", status: "running", stage: "writing_sections", progress: 0.4, message: "Writing", current: { done: 2, total: 5 }, warnings: ["One section is being retried."] }) };
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ProgressPanel jobId="job-2" onComplete={vi.fn()} onError={vi.fn()} onCancel={onCancel} />);
    expect(await screen.findByText("Items: 2 of 5")).toBeInTheDocument();
    expect(screen.getByText("One section is being retried.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel Job" }));
    await waitFor(() => expect(onCancel).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/jobs/job-2",
      expect.objectContaining({ method: "DELETE", signal: expect.any(AbortSignal) }),
    );
  });
});

describe("ResultPanel", () => {
  it("shows verification, research metadata, and warnings", () => {
    render(<ResultPanel result={makeResult()} templateType="docx" onReset={vi.fn()} />);
    expect(screen.getByRole("link", { name: /Download Artifact/i })).toHaveAttribute("href", "/api/download/report.docx");
    expect(screen.getByRole("heading", { name: "Research sources" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Grid Integration Review" })).toHaveAttribute("target", "_blank");
    expect(screen.getAllByText(/not independently verified/i)).toHaveLength(2);
    expect(screen.getByText("Search results were not independently verified.")).toBeInTheDocument();
  });

  it("disables normal download after drift and supports revalidation", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ passed: false, status: "failed", issues: ["Styles changed."] }) }));
    render(<ResultPanel result={makeResult({ validation: { passed: false, status: "failed", issues: ["Styles changed."] } })} templateType="docx" onReset={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Download Disabled/i })).toBeDisabled();
    expect(screen.getByText("Styles changed.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Re-verify/i }));
    expect(await screen.findByText(/Validation re-verified/i)).toBeInTheDocument();
  });

  it("uses the reference-mode result state for PDF templates", () => {
    render(<ResultPanel result={makeResult()} templateType="pdf" onReset={vi.fn()} />);
    expect(screen.getByRole("heading", { name: /Approximate layout/i })).toBeInTheDocument();
  });
});
