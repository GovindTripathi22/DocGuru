"""Bounded Tavily Search API client used only for explicit research requests."""

import asyncio
import logging
import math
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from ..config import settings
from ..errors import AppError
from ..models.generation import ResearchSource
from ..planning.normalize import sanitize_text

logger = logging.getLogger(__name__)
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyResearchService:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_sec: int | None = None,
        max_sources: int | None = None,
        client_factory: Callable[..., httpx.AsyncClient] | None = None,
    ):
        self.api_key = settings.TAVILY_API_KEY if api_key is None else api_key
        self.timeout_sec = timeout_sec or settings.RESEARCH_TIMEOUT_SEC
        self.max_sources = max_sources or settings.RESEARCH_MAX_SOURCES
        self.client_factory = client_factory or httpx.AsyncClient

    async def search(self, prompt: str, section_titles: list[str]) -> list[ResearchSource]:
        if not self.api_key:
            raise AppError(
                code="RESEARCH_NOT_CONFIGURED",
                http_status=503,
                message="Web research is not configured. Set TAVILY_API_KEY or turn off Research sources.",
            )

        queries = self._build_queries(prompt, section_titles)
        semaphore = asyncio.Semaphore(3)
        try:
            async with self.client_factory(timeout=self.timeout_sec) as client:

                async def run_query(query: str) -> dict:
                    async with semaphore:
                        response = await client.post(
                            TAVILY_SEARCH_URL,
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json={
                                "query": query,
                                "search_depth": "basic",
                                "max_results": 5,
                                "include_answer": False,
                                "include_raw_content": False,
                                "safe_search": True,
                            },
                        )
                        if response.status_code == 401:
                            raise AppError(
                                "RESEARCH_NOT_CONFIGURED",
                                503,
                                "The configured research key was rejected.",
                            )
                        if response.status_code == 429:
                            raise AppError(
                                "RESEARCH_RATE_LIMITED",
                                429,
                                "The research provider is rate limiting requests.",
                            )
                        response.raise_for_status()
                        return response.json()

                payloads = await asyncio.gather(*(run_query(query) for query in queries))
        except AppError:
            raise
        except (httpx.TimeoutException, httpx.HTTPError, ValueError) as error:
            logger.warning("Research provider request failed (%s)", type(error).__name__)
            raise AppError(
                code="RESEARCH_UNAVAILABLE",
                http_status=502,
                message="Web research could not be completed. Retry later or turn off Research sources.",
            ) from error

        sources_by_url: dict[str, ResearchSource] = {}
        for payload in payloads:
            raw_results = payload.get("results", [])
            if not isinstance(raw_results, list):
                continue
            for result in raw_results:
                if not isinstance(result, dict):
                    continue
                url = str(result.get("url") or "").strip()
                parsed_url = urlparse(url)
                if (
                    len(url) > 2048
                    or parsed_url.scheme not in {"http", "https"}
                    or not parsed_url.netloc
                    or parsed_url.username
                    or any(ord(character) < 32 for character in url)
                ):
                    continue
                title = sanitize_text(result.get("title"), max_len=300, field_name="research_title")
                snippet = sanitize_text(
                    result.get("content"), max_len=2500, field_name="research_snippet"
                )
                if not title or not snippet:
                    continue
                try:
                    score = float(result["score"]) if result.get("score") is not None else None
                except (TypeError, ValueError):
                    score = None
                if score is not None and (not math.isfinite(score) or not 0.0 <= score <= 1.0):
                    score = None
                candidate = ResearchSource(
                    id="",
                    title=title,
                    url=url,
                    snippet=snippet,
                    published_date=sanitize_text(
                        result["published_date"], max_len=100, field_name="research_date"
                    )
                    if result.get("published_date")
                    else None,
                    score=score,
                )
                previous = sources_by_url.get(url)
                if previous is None or (
                    score is not None and (previous.score is None or score > previous.score)
                ):
                    sources_by_url[url] = candidate

        ranked_sources = sorted(
            sources_by_url.values(),
            key=lambda source: (
                source.score is None,
                -(source.score or 0.0),
                source.title.casefold(),
            ),
        )
        sources = [
            source.model_copy(update={"id": f"S{index}"})
            for index, source in enumerate(ranked_sources[: self.max_sources], start=1)
        ]

        if len(sources) < 3:
            raise AppError(
                code="RESEARCH_INSUFFICIENT",
                http_status=422,
                message="Research returned fewer than three usable sources. Refine the topic or turn off Research sources.",
            )
        return sources

    @staticmethod
    def _build_queries(prompt: str, section_titles: list[str]) -> list[str]:
        clean_prompt = " ".join(prompt.split())[:350]
        queries = [clean_prompt]
        for title in section_titles:
            query = f"{clean_prompt} {title}".strip()[:450]
            if query not in queries:
                queries.append(query)
            if len(queries) == 4:
                break
        return queries
