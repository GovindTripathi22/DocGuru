from pydantic import BaseModel


class ImageCandidate(BaseModel):
    url: str
    width: int
    height: int
    license: str = "Public Domain / CC"
    author: str | None = None
    source_url: str | None = None
    download_location: str | None = None
    attribution: str | None = None
