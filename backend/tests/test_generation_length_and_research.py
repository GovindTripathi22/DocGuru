import asyncio
from types import SimpleNamespace

import httpx
import pytest
import respx
from pydantic import ValidationError

from backend.app.ai.generation_budget import resolve_document_budget
from backend.app.errors import AppError, LLMInvalidResponse, LLMTruncated
from backend.app.models.generation import GenerationRequest
from backend.app.research.tavily import TavilyResearchService


def test_document_length_targets_are_exclusive_and_legacy_target_maps_to_pages():
    with pytest.raises(ValidationError):
        GenerationRequest(template_id="a" * 32, prompt="topic", target_pages=8, detail_level="high")
    with pytest.raises(ValidationError):
        GenerationRequest(template_id="a" * 32, prompt="topic", target_pages=51)
    with pytest.raises(ValidationError):
        GenerationRequest(
            template_id="a" * 32, prompt="topic", document_type="docx", target_slides=5
        )
    with pytest.raises(ValidationError):
        GenerationRequest(
            template_id="a" * 32, prompt="topic", document_type="pptx", target_pages=5
        )

    numeric = GenerationRequest(template_id="a" * 32, prompt="topic", target_pages=8)
    legacy = GenerationRequest(template_id="a" * 32, prompt="topic", target_pages_or_slides=4)
    default = GenerationRequest(template_id="a" * 32, prompt="topic")
    slides = GenerationRequest(
        template_id="a" * 32,
        prompt="topic",
        document_type="pptx",
        target_pages_or_slides=6,
    )
    assert numeric.target_pages == 8
    assert legacy.target_pages == 4
    assert default.detail_level == "medium"
    assert slides.target_slides == 6


def test_detail_presets_and_page_targets_create_monotonic_word_budgets():
    low = resolve_document_budget(target_pages=None, detail_level="low")
    medium = resolve_document_budget(target_pages=None, detail_level="medium")
    high = resolve_document_budget(target_pages=None, detail_level="high")
    two_pages = resolve_document_budget(target_pages=2, detail_level=None)
    five_pages = resolve_document_budget(target_pages=5, detail_level=None)

    assert (low.target_pages, medium.target_pages, high.target_pages) == (2, 5, 10)
    assert low.target_words < medium.target_words < high.target_words
    assert five_pages.target_pages == 5
    assert five_pages.section_count > two_pages.section_count
    assert five_pages.target_words > two_pages.target_words
    assert five_pages.target_words > low.target_words


def test_provider_calls_obey_global_concurrency_limit_without_blocking_event_loop(monkeypatch):
    import backend.app.ai.gemma_client as gemma_module
    from backend.app.ai.gemma_client import GemmaClient
    from backend.app.config import settings
    from backend.app.llm.base import LLMResult

    monkeypatch.setattr(settings, "LLM_MAX_CONCURRENCY", 3)
    active = 0
    max_active = 0

    class AsyncProvider:
        async def generate_json(self, **_kwargs):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.03)
            active -= 1
            return LLMResult(content='{"ok": true}', parsed={"ok": True}, model="scripted")

    provider = AsyncProvider()
    monkeypatch.setattr(gemma_module, "get_llm_provider", lambda _name: provider)

    async def run_probe():
        client = GemmaClient(provider="demo")
        finished = asyncio.Event()
        heartbeat_gaps = []
        loop = asyncio.get_running_loop()

        async def heartbeat():
            previous = loop.time()
            while not finished.is_set():
                await asyncio.sleep(0.01)
                now = loop.time()
                heartbeat_gaps.append(now - previous)
                previous = now

        pulse = asyncio.create_task(heartbeat())
        started = loop.time()
        results = await asyncio.gather(
            *[client.generate_structured_json("system", f"request {index}") for index in range(20)]
        )
        elapsed = loop.time() - started
        finished.set()
        await pulse
        return results, elapsed, heartbeat_gaps

    results, elapsed, heartbeat_gaps = asyncio.run(run_probe())

    assert len(results) == 20
    assert all(result == {"ok": True} for result in results)
    assert max_active == 3
    assert elapsed < 4.0
    assert max(heartbeat_gaps, default=0.0) <= 0.2


def test_demo_section_honors_explicit_comparison_table_request_without_fabricated_metrics():
    from backend.app.llm.demo import DemoProvider

    result = asyncio.run(
        DemoProvider().generate_json(
            "DOCGURU_TASK: DOCUMENT_SECTION\nWrite approximately 180 words.",
            "User request: Create a comparison table for grid resilience\n"
            "Section title: Purpose and Scope\nGoal: Frame the decision",
        )
    )

    table = result.parsed["section"]["table"]
    assert table["headers"] == ["Evaluation dimension", "What to compare", "Evidence to confirm"]
    assert all("%" not in cell for row in table["rows"] for cell in row)


@respx.mock
def test_tavily_search_returns_validated_citable_sources():
    route = respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": f"Source {i}",
                        "url": f"https://example.org/{i}",
                        "content": f"Evidence {i}",
                        "published_date": "2026-01-01",
                        "score": 0.9,
                    }
                    for i in range(1, 4)
                ]
            },
        )
    )
    service = TavilyResearchService(api_key="test-key")

    sources = asyncio.run(service.search("grid resilience", ["storage planning"]))

    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"
    assert [source.id for source in sources] == ["S1", "S2", "S3"]
    assert all(source.url.startswith("https://") for source in sources)


@respx.mock
def test_tavily_selects_highest_scoring_sources_first():
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Marginal result",
                        "url": "https://example.org/marginal",
                        "content": "Weak match",
                        "score": 0.05,
                    },
                    {
                        "title": "Strong match",
                        "url": "https://example.org/strong",
                        "content": "Relevant evidence",
                        "score": 0.98,
                    },
                    {
                        "title": "Useful match",
                        "url": "https://example.org/useful",
                        "content": "Relevant context",
                        "score": 0.75,
                    },
                    {
                        "title": "Another match",
                        "url": "https://example.org/another",
                        "content": "Relevant details",
                        "score": 0.61,
                    },
                ]
            },
        )
    )
    sources = asyncio.run(
        TavilyResearchService(api_key="test-key", max_sources=3).search("grid resilience", [])
    )
    assert [source.title for source in sources] == ["Strong match", "Useful match", "Another match"]


def test_tavily_opt_in_without_key_fails_clearly():
    with pytest.raises(AppError) as raised:
        asyncio.run(TavilyResearchService(api_key="").search("topic", []))
    assert raised.value.code == "RESEARCH_NOT_CONFIGURED"


def test_tavily_search_failure_does_not_silently_downgrade():
    service = TavilyResearchService(
        api_key="test-key", client_factory=lambda **_kwargs: _FailingClient()
    )
    with pytest.raises(AppError) as raised:
        asyncio.run(service.search("topic", []))
    assert raised.value.code == "RESEARCH_UNAVAILABLE"


class _FailingClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *_args, **_kwargs):
        raise httpx.ConnectError("network offline")


class _ScriptedClient:
    def __init__(self):
        self.calls = []

    async def generate_structured_json(
        self, system_prompt, user_prompt, response_schema=None, max_tokens=None
    ):
        self.calls.append((system_prompt, user_prompt, max_tokens))
        if "DOCUMENT_OUTLINE" in system_prompt:
            titles = ["Context", "Analysis", "Recommendations"]
            return {
                "title": "Grid Resilience",
                "sections": [
                    {
                        "title": title,
                        "goal": f"Explain {title.lower()} of grid resilience",
                        "target_words": 180,
                    }
                    for title in titles
                ],
            }
        if "DOCUMENT_SECTION_QUALITY" in system_prompt:
            return {"passed": True, "issues": []}
        if "DOCUMENT_SECTION" in system_prompt:
            title = _extract(user_prompt, "Section title:", "Goal:")
            body = _varied_body("grid resilience")
            return {
                "section": {"title": title, "paragraphs": [body], "bullets": [], "citations": []}
            }
        raise AssertionError("Unexpected LLM stage")


def _extract(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def _varied_body(topic, count=20):
    aspects = [
        "planning assumptions",
        "community priorities",
        "infrastructure needs",
        "risk ownership",
        "operational constraints",
        "maintenance planning",
        "evidence quality",
        "decision criteria",
        "funding choices",
        "staffing needs",
        "service continuity",
        "monitoring design",
        "coordination practices",
        "recovery sequencing",
        "public communication",
        "resource dependencies",
        "governance models",
        "evaluation methods",
        "implementation timing",
        "uncertainty management",
    ]
    return " ".join(
        f"A relevant discussion of {topic} should evaluate {aspect}, explain its implications for the intended audience, and identify evidence or decisions still needed."
        for aspect in aspects[:count]
    )


def test_document_planner_uses_outline_then_section_calls_and_reports_real_progress(monkeypatch):
    from backend.app.ai.planner import DocumentPlanner

    planner = DocumentPlanner()
    planner.client = _ScriptedClient()
    updates = []

    async def on_progress(stage, done, total):
        updates.append((stage, done, total))

    plan = asyncio.run(
        planner.plan_document(
            "Write about grid resilience",
            SimpleNamespace(
                available_heading_styles=["Heading 1"], extracted_rules=[], document_outline=[]
            ),
            target_pages=2,
            include_images=False,
            on_progress=on_progress,
        )
    )

    assert len(plan.sections) == 3
    assert [call[2] for call in planner.client.calls][0] >= 1200
    assert len(planner.client.calls) == 7
    assert updates[0] == ("writing_sections", 0, 3)
    assert updates[-1] == ("writing_sections", 3, 3)
    assert "about 2 pages" in planner.client.calls[0][0]
    assert "900 words total" in planner.client.calls[0][0]


def test_plan_citations_only_keep_known_source_ids():
    from backend.app.ai.planner import keep_known_citations

    assert keep_known_citations(["S1", "S99", "https://bad.test"], {"S1"}) == ["S1"]


class _TwelveSectionClient:
    def __init__(self, *, truncate_once=False):
        self.calls = []
        self.active_sections = 0
        self.max_active_sections = 0
        self.truncate_once = truncate_once

    async def generate_structured_json(
        self, system_prompt, user_prompt, response_schema=None, max_tokens=None
    ):
        self.calls.append((system_prompt, user_prompt, max_tokens))
        if "DOCUMENT_OUTLINE" in system_prompt:
            if self.truncate_once:
                self.truncate_once = False
                raise LLMTruncated("scripted truncation")
            return {
                "title": "Climate Adaptation",
                "target_audience": "Public sector planners",
                "sections": [
                    {
                        "title": f"Planning Area {index + 1}",
                        "goal": "Assess climate adaptation choices",
                    }
                    for index in range(12)
                ],
            }
        self.active_sections += 1
        self.max_active_sections = max(self.max_active_sections, self.active_sections)
        await asyncio.sleep(0.01)
        self.active_sections -= 1
        if "DOCUMENT_SECTION_QUALITY" in system_prompt:
            return {"passed": True, "issues": []}
        body = _varied_body("climate adaptation", 12)
        return {
            "section": {
                "title": "Planned section",
                "paragraphs": [body],
                "bullets": [],
                "conclusion": "Climate adaptation planning should follow the documented local goals and constraints.",
            }
        }


def test_twelve_sections_use_bounded_writer_and_quality_calls_with_real_progress(monkeypatch):
    from backend.app.ai.planner import DocumentPlanner
    from backend.app.config import settings

    monkeypatch.setattr(settings, "LLM_MAX_CONCURRENCY", 2)
    planner = DocumentPlanner()
    planner.client = _TwelveSectionClient()
    progress = []

    async def on_progress(stage, done, total):
        progress.append((stage, done, total))

    plan = asyncio.run(
        planner.plan_document(
            "Create a climate adaptation planning report",
            SimpleNamespace(available_heading_styles=[], extracted_rules=[], document_outline=[]),
            target_sections=12,
            target_pages=1,
            include_images=False,
            on_progress=on_progress,
        )
    )

    assert len(plan.sections) == 12
    assert len(planner.client.calls) == 25
    assert planner.client.max_active_sections == 2
    assert [done for stage, done, _total in progress if stage == "writing_sections"] == list(
        range(13)
    )
    assert all(total == 12 for _stage, _done, total in progress)


def test_truncated_outline_is_retried_and_empty_outline_is_rejected():
    from backend.app.ai.planner import DocumentPlanner

    planner = DocumentPlanner()
    planner.client = _TwelveSectionClient(truncate_once=True)
    plan = asyncio.run(
        planner.plan_document(
            "Create a climate adaptation planning report",
            SimpleNamespace(available_heading_styles=[], extracted_rules=[], document_outline=[]),
            target_sections=12,
            target_pages=1,
            include_images=False,
        )
    )
    assert len(plan.sections) == 12
    assert len(planner.client.calls) == 26
    assert planner.client.calls[1][2] > planner.client.calls[0][2]

    class EmptyClient:
        async def generate_structured_json(self, **_kwargs):
            return {}

    planner.client = EmptyClient()
    with pytest.raises(LLMInvalidResponse):
        asyncio.run(
            planner.plan_document(
                "Create a climate adaptation planning report",
                SimpleNamespace(
                    available_heading_styles=[], extracted_rules=[], document_outline=[]
                ),
                include_images=False,
            )
        )


def test_unsupported_numerical_claim_gets_one_targeted_section_repair():
    from backend.app.ai.planner import DocumentPlanner

    class RepairClient:
        def __init__(self):
            self.calls = []

        async def generate_structured_json(self, system_prompt, user_prompt, **_kwargs):
            self.calls.append((system_prompt, user_prompt))
            if "DOCUMENT_OUTLINE" in system_prompt:
                return {
                    "title": "Climate Adaptation",
                    "sections": [{"title": "Planning", "goal": "Discuss planning choices"}],
                }
            if "DOCUMENT_SECTION_QUALITY" in system_prompt:
                return {"passed": True, "issues": []}
            body = _varied_body("climate adaptation")
            if "REPAIR:" not in system_prompt:
                body = "In 2025, " + body
            section = {"title": "Planning", "paragraphs": [body], "bullets": []}
            if "For the final section" in system_prompt:
                section["conclusion"] = (
                    "Climate adaptation planning should follow the stated goals."
                )
            return {"section": section}

    planner = DocumentPlanner()
    planner.client = RepairClient()
    plan = asyncio.run(
        planner.plan_document(
            "Create a report about climate adaptation",
            SimpleNamespace(available_heading_styles=[], extracted_rules=[], document_outline=[]),
            target_sections=1,
            target_pages=1,
            include_images=False,
        )
    )
    assert len(planner.client.calls) == 4
    assert "REPAIR:" in planner.client.calls[2][0]
    assert "2025" not in plan.sections[0].paragraphs[0]


def test_failed_structured_quality_review_gets_one_targeted_repair():
    from backend.app.ai.planner import DocumentPlanner

    class ReviewRepairClient:
        def __init__(self):
            self.calls = []
            self.reviews = 0

        async def generate_structured_json(self, system_prompt, user_prompt, **_kwargs):
            self.calls.append((system_prompt, user_prompt))
            if "DOCUMENT_OUTLINE" in system_prompt:
                return {
                    "title": "Grid Resilience",
                    "sections": [
                        {"title": "Planning", "goal": "Explain grid resilience planning choices"}
                    ],
                }
            if "DOCUMENT_SECTION_QUALITY" in system_prompt:
                self.reviews += 1
                if self.reviews == 1:
                    return {
                        "passed": False,
                        "issues": [
                            "Connect the implementation choices to the stated planning goal."
                        ],
                    }
                return {"passed": True, "issues": []}
            body = _varied_body("grid resilience")
            if "REPAIR:" in system_prompt:
                body += " These implementation choices should be evaluated against the stated planning goal and its constraints."
            return {
                "section": {
                    "title": "Planning",
                    "paragraphs": [body],
                    "bullets": [],
                    "conclusion": "Grid resilience planning should follow the supplied goals and constraints.",
                }
            }

    planner = DocumentPlanner()
    planner.client = ReviewRepairClient()
    result = asyncio.run(
        planner.plan_document(
            "Write a detailed guide about grid resilience",
            SimpleNamespace(available_heading_styles=[], extracted_rules=[], document_outline=[]),
            target_sections=1,
            target_pages=1,
            include_images=False,
        )
    )
    assert len(result.sections) == 1
    assert planner.client.reviews == 2
    repair_calls = [system for system, _user in planner.client.calls if "REPAIR:" in system]
    assert len(repair_calls) == 1
    repair_user = next(user for system, user in planner.client.calls if "REPAIR:" in system)
    assert "Connect the implementation choices" in repair_user


def test_research_plan_citations_are_limited_to_returned_sources(monkeypatch):
    import backend.app.research.tavily as tavily_module
    from backend.app.ai.planner import DocumentPlanner
    from backend.app.models.generation import ResearchSource

    source = ResearchSource(
        id="S1",
        title="Climate adaptation guidance",
        url="https://example.org/climate",
        snippet="Guidance about planning.",
    )
    observed = {}

    class ResearchService:
        async def search(self, prompt, section_titles):
            observed["prompt"] = prompt
            observed["titles"] = section_titles
            return [source]

    class CitationClient:
        async def generate_structured_json(self, system_prompt, user_prompt, **_kwargs):
            if "DOCUMENT_OUTLINE" in system_prompt:
                return {
                    "title": "Climate Adaptation",
                    "sections": [{"title": "Planning", "goal": "Discuss planning choices"}],
                }
            if "DOCUMENT_SECTION_QUALITY" in system_prompt:
                return {"passed": True, "issues": []}
            body = _varied_body("climate adaptation")
            return {
                "section": {
                    "title": "Planning",
                    "paragraphs": [body],
                    "bullets": [],
                    "citations": ["S1", "S99", "https://unreturned.invalid"],
                    "conclusion": "Climate adaptation planning should follow the stated goals.",
                }
            }

    monkeypatch.setattr(tavily_module, "TavilyResearchService", ResearchService)
    planner = DocumentPlanner()
    planner.client = CitationClient()
    plan = asyncio.run(
        planner.plan_document(
            "Create a report about climate adaptation",
            SimpleNamespace(available_heading_styles=[], extracted_rules=[], document_outline=[]),
            target_sections=1,
            target_pages=1,
            include_images=False,
            research_enabled=True,
        )
    )
    assert observed["prompt"] == "Create a report about climate adaptation"
    assert observed["titles"] == ["Planning"]
    assert [item.id for item in plan.research_sources] == ["S1"]
    assert plan.sections[0].citations == ["S1"]
    assert any("not independently verified" in warning for warning in plan.warnings)


@respx.mock
def test_tavily_insufficient_sources_returns_explicit_error():
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Source 1", "url": "https://example.org/1", "content": "Evidence"},
                    {"title": "Source 2", "url": "https://example.org/2", "content": "Evidence"},
                ]
            },
        )
    )
    with pytest.raises(AppError) as raised:
        asyncio.run(TavilyResearchService(api_key="test-key").search("topic", []))
    assert raised.value.code == "RESEARCH_INSUFFICIENT"
