from typing import Optional
from pydantic import BaseModel, Field


class ImageCandidate(BaseModel):
    url: str
    width: int
    height: int
    license: str = "Public Domain / CC"
    author: Optional[str] = None
    source_url: Optional[str] = None
    download_location: Optional[str] = None
    attribution: Optional[str] = None
