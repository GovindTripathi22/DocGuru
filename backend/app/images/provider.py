"""Image search providers for Wikimedia Commons, Unsplash, and Pexels (IMG-02)."""

import abc
import logging
from typing import List, Optional
import httpx

from .models import ImageCandidate

logger = logging.getLogger(__name__)


class ImageProvider(abc.ABC):
    @abc.abstractmethod
    async def search(
        self,
        query: str,
        width: int = 800,
        height: int = 450,
        orientation: str = "landscape",
    ) -> List[ImageCandidate]:
        pass


class WikimediaProvider(ImageProvider):
    API_URL = "https://commons.wikimedia.org/w/api.php"
    USER_AGENT = "DocGuru-TemplateEngine/1.0 (https://github.com/GovindTripathi22/DocGuru; bot@docguru.local)"

    async def search(
        self,
        query: str,
        width: int = 800,
        height: int = 450,
        orientation: str = "landscape",
    ) -> List[ImageCandidate]:
        clean_query = query.strip()
        if not clean_query:
            return []

        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"{clean_query} filetype:bitmap",
            "gsrnamespace": "6",  # File namespace
            "gsrlimit": "5",
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime",
            "iiurlwidth": str(width),
            "format": "json",
        }
        headers = {"User-Agent": self.USER_AGENT}

        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                resp = await client.get(self.API_URL, params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                candidates = []

                for page in pages.values():
                    imageinfo = page.get("imageinfo", [])
                    if not imageinfo:
                        continue
                    info = imageinfo[0]
                    mime = info.get("mime", "")
                    if not mime.startswith("image/"):
                        continue

                    url = info.get("thumburl") or info.get("url")
                    if not url:
                        continue

                    w = info.get("thumbwidth") or info.get("width") or width
                    h = info.get("thumbheight") or info.get("height") or height
                    meta = info.get("extmetadata", {})
                    author = meta.get("Artist", {}).get("value")
                    license_name = meta.get("LicenseShortName", {}).get("value", "CC / Public Domain")

                    candidates.append(
                        ImageCandidate(
                            url=url,
                            width=int(w),
                            height=int(h),
                            license=license_name,
                            author=author,
                            source_url=info.get("descriptionurl"),
                            attribution=f"Wikimedia Commons / {author or 'Public Domain'}",
                        )
                    )
                return candidates
        except Exception as e:
            logger.warning("Wikimedia search failed for '%s': %s", query, e)
            return []


class UnsplashProvider(ImageProvider):
    API_URL = "https://api.unsplash.com/search/photos"

    def __init__(self, access_key: str):
        self.access_key = access_key

    async def search(
        self,
        query: str,
        width: int = 800,
        height: int = 450,
        orientation: str = "landscape",
    ) -> List[ImageCandidate]:
        if not self.access_key:
            return []

        headers = {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1",
        }
        params = {
            "query": query,
            "per_page": 5,
            "orientation": orientation,
        }

        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                resp = await client.get(self.API_URL, params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = data.get("results", [])
                candidates = []

                for item in results:
                    urls = item.get("urls", {})
                    user = item.get("user", {})
                    links = item.get("links", {})
                    author_name = user.get("name") or user.get("username") or "Unsplash Contributor"

                    candidates.append(
                        ImageCandidate(
                            url=urls.get("regular") or urls.get("full") or urls.get("small"),
                            width=item.get("width", width),
                            height=item.get("height", height),
                            license="Unsplash License",
                            author=author_name,
                            source_url=links.get("html"),
                            download_location=links.get("download_location"),
                            attribution=f"Photo by {author_name} on Unsplash",
                        )
                    )
                return candidates
        except Exception as e:
            logger.warning("Unsplash search failed for '%s': %s", query, e)
            return []


class PexelsProvider(ImageProvider):
    API_URL = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self,
        query: str,
        width: int = 800,
        height: int = 450,
        orientation: str = "landscape",
    ) -> List[ImageCandidate]:
        if not self.api_key:
            return []

        headers = {"Authorization": self.api_key}
        params = {
            "query": query,
            "per_page": 5,
            "orientation": orientation,
        }

        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                resp = await client.get(self.API_URL, params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                photos = data.get("photos", [])
                candidates = []

                for item in photos:
                    src = item.get("src", {})
                    photographer = item.get("photographer", "Pexels Contributor")

                    candidates.append(
                        ImageCandidate(
                            url=src.get("large") or src.get("medium") or src.get("original"),
                            width=item.get("width", width),
                            height=item.get("height", height),
                            license="Pexels License",
                            author=photographer,
                            source_url=item.get("url"),
                            attribution=f"Photo by {photographer} on Pexels",
                        )
                    )
                return candidates
        except Exception as e:
            logger.warning("Pexels search failed for '%s': %s", query, e)
            return []
