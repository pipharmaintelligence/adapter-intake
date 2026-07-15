from __future__ import annotations

from typing import Final

LINKEDIN_POST_CAPABILITIES: Final[dict[str, dict[str, str]]] = {
    "linkedin.posts.extract": {
        "tool": "extract_linkedin_post",
        "response_format": "json",
        "authority": "server_authorized",
    }
}
