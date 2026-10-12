"""Fixture-only inert values; this stub has no network transport or authority."""
from dataclasses import dataclass

class PublicReferenceError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)

@dataclass(frozen=True)
class ReferenceTarget:
    url: str
    source_kind: str='input_business_url'
    title: str | None=None
    @classmethod
    def business_url(cls,url,title=None):
        return cls(url,title=title)
