from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlsplit

from adapters.base import Adapter

try:
    from .linkedin_post_capabilities import LINKEDIN_POST_CAPABILITIES
except ImportError:  # Local external adapter root mode.
    from linkedin_post_capabilities import LINKEDIN_POST_CAPABILITIES


CAPABILITY_REF = "linkedin.posts.extract"
TOOL_ROLE = "linkedin_post_extract"
TOOL_HANDLE = "@tool.linkedin_post_extract"
TOOL_SERVER_REF = "mcp.linkedin"
MAX_POST_TEXT_LENGTH = 20_000
MAX_POST_URL_LENGTH = 2_048

# LinkedIn activity/share identifiers are currently decimal values. Requiring a
# long bounded number avoids treating unrelated years or slug numbers as posts.
POST_ID_PATTERN = r"(?P<post_id>\d{10,25})"
URN_PATTERN = re.compile(
    rf"urn:li:(?P<kind>activity|share|ugcpost):{POST_ID_PATTERN}",
    re.IGNORECASE,
)
POSTS_ACTIVITY_PATTERN = re.compile(
    rf"(?:^|[_-])(?P<kind>activity|share|ugcpost)-{POST_ID_PATTERN}(?:[-_/]|$)",
    re.IGNORECASE,
)


class LinkedinPostExtractAdapter(Adapter):
    """Extract text from a LinkedIn post through a governed runtime MCP tool.

    The adapter validates a user-supplied public LinkedIn post URL and converts
    it to a bounded LinkedIn post reference before crossing the runtime tool
    boundary. It does not perform HTTP requests, browser automation,
    authentication, cookie handling, or provider-specific dispatch.
    """

    key = "nusaibah.linkedin_post_extract"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Process one or more LinkedIn post URL requests."""

        post_request = inputs.get("post_request", {})
        records = post_request.get("records", []) if isinstance(post_request, dict) else []

        if not isinstance(records, list) or not records:
            results = [
                {
                    "status": "failed",
                    "reason_code": "post_request_missing",
                    "message": "post_request.records must contain at least one record.",
                    "post_text": None,
                }
            ]
        else:
            results = [self._handle_record(record, inputs) for record in records]

        completed_count = sum(1 for result in results if result.get("status") == "completed")
        blocked_count = sum(1 for result in results if result.get("status") == "blocked")
        failed_count = len(results) - completed_count - blocked_count

        if completed_count == 0:
            all_blocked = blocked_count == len(results)
            return {
                "response_version": "1",
                "status": "error",
                "error": {
                    "code": "runtime_tool_unavailable" if all_blocked else "linkedin_post_extract_not_completed",
                    "message": (
                        "The governed LinkedIn MCP runtime tool is unavailable."
                        if all_blocked
                        else "No LinkedIn post text was extracted."
                    ),
                },
            }

        result_state = "completed" if completed_count == len(results) else "partial"
        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "post_text": {
                    "format": "json",
                    "records": results,
                }
            },
            "logs": [
                {
                    "level": "info" if result_state == "completed" else "warning",
                    "message": "Evaluated LinkedIn post extraction through the governed runtime tool bridge.",
                }
            ],
            "metrics": {
                "result_state": result_state,
                "request_count": len(results),
                "completed_count": completed_count,
                "blocked_count": blocked_count,
                "failed_count": failed_count,
            },
        }

    def _handle_record(self, record: Any, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate one request, invoke the runtime tool, and normalize its text."""

        if not isinstance(record, dict):
            return self._failed(
                "post_request_record_invalid",
                "Each post_request record must be an object.",
            )

        post_reference = self._extract_linkedin_post_reference(record.get("post_url"))
        if post_reference is None:
            return self._failed(
                "linkedin_post_url_invalid",
                "post_url must identify a public LinkedIn /posts/ or /feed/update/ post.",
            )

        capability = LINKEDIN_POST_CAPABILITIES[CAPABILITY_REF]
        invoke_tool = getattr(inputs, "invoke_tool", None)
        if not callable(invoke_tool):
            return {
                "status": "blocked",
                "reason_code": "runtime_tool_unavailable",
                "message": "Assets/Core must provide the governed LinkedIn MCP runtime tool.",
                "capability_ref": CAPABILITY_REF,
                "tool": capability["tool"],
                "binding": self._binding(),
                "authority": "server_authorized_intent_only",
                "post_reference": post_reference,
                "post_text": None,
            }

        # Only the bounded business reference crosses the generic MCP bridge.
        # Core remains responsible for connector selection, credentials, request
        # transport, provider execution, and response sanitization.
        tool_result = invoke_tool(
            TOOL_ROLE,
            input={"text": post_reference},
            on_error="none",
        )
        if tool_result is None:
            return {
                "status": "blocked",
                "reason_code": "runtime_tool_unavailable",
                "message": "The governed LinkedIn MCP runtime tool is unavailable.",
                "capability_ref": CAPABILITY_REF,
                "tool": capability["tool"],
                "binding": self._binding(),
                "authority": "server_authorized_intent_only",
                "post_reference": post_reference,
                "post_text": None,
            }

        post_text = self._extract_post_text(tool_result)
        if post_text is None:
            return self._failed(
                "post_text_not_found",
                "The runtime tool completed without a usable post_text value.",
                authority="assets_core_runtime_lease",
                post_reference=post_reference,
            )

        return {
            "status": "completed",
            "capability_ref": CAPABILITY_REF,
            "tool": capability["tool"],
            "binding": self._binding(),
            "authority": "assets_core_runtime_lease",
            "source_kind": "linkedin_post",
            "post_reference": post_reference,
            "post_text": post_text,
            "character_count": len(post_text),
        }

    @staticmethod
    def _binding() -> dict[str, str]:
        """Return safe metadata for the declared runtime tool binding."""

        return {
            "tool_handle": TOOL_HANDLE,
            "tool_server_ref": TOOL_SERVER_REF,
            "binding_ref": TOOL_SERVER_REF,
            "capability_ref": CAPABILITY_REF,
        }

    @staticmethod
    def _extract_linkedin_post_reference(value: Any) -> str | None:
        """Extract a bounded LinkedIn URN from a supported public post URL.

        Supported examples include ``/feed/update/urn:li:activity:<id>`` and
        ``/posts/<slug>_activity-<id>-<suffix>``. Query parameters and fragments
        are ignored and never cross the runtime tool boundary.
        """

        if not isinstance(value, str):
            return None

        candidate = value.strip()
        if not candidate or len(candidate) > MAX_POST_URL_LENGTH:
            return None

        try:
            parsed = urlsplit(candidate)
            port = parsed.port
        except ValueError:
            return None

        host = (parsed.hostname or "").lower().rstrip(".")
        is_linkedin_host = host == "linkedin.com" or host.endswith(".linkedin.com")

        if parsed.scheme.lower() != "https" or not is_linkedin_host:
            return None
        if parsed.username or parsed.password:
            return None
        if port not in (None, 443):
            return None

        path = unquote(parsed.path).rstrip("/")
        if not (path.startswith("/posts/") or path.startswith("/feed/update/")):
            return None

        urn_match = URN_PATTERN.search(path)
        if urn_match is not None:
            return LinkedinPostExtractAdapter._canonical_urn(
                urn_match.group("kind"),
                urn_match.group("post_id"),
            )

        if path.startswith("/posts/"):
            activity_match = POSTS_ACTIVITY_PATTERN.search(path)
            if activity_match is not None:
                return LinkedinPostExtractAdapter._canonical_urn(
                    activity_match.group("kind"),
                    activity_match.group("post_id"),
                )

        return None

    @staticmethod
    def _canonical_urn(kind: str, post_id: str) -> str:
        """Return a canonical safe LinkedIn URN for a validated identifier."""

        normalized_kind = kind.lower()
        canonical_kind = "ugcPost" if normalized_kind == "ugcpost" else normalized_kind
        return f"urn:li:{canonical_kind}:{post_id}"

    def _extract_post_text(self, value: Any, *, depth: int = 0) -> str | None:
        """Find a bounded text value in common MCP result shapes."""

        if depth > 3:
            return None

        if isinstance(value, str):
            text = value.strip()
            return text[:MAX_POST_TEXT_LENGTH] if text else None

        if isinstance(value, list):
            for item in value[:10]:
                text = self._extract_post_text(item, depth=depth + 1)
                if text is not None:
                    return text
            return None

        if not isinstance(value, dict):
            return None

        for key in ("post_text", "text", "content", "commentary"):
            text = self._extract_post_text(value.get(key), depth=depth + 1)
            if text is not None:
                return text

        for key in ("record", "records", "result", "data", "output"):
            text = self._extract_post_text(value.get(key), depth=depth + 1)
            if text is not None:
                return text

        return None

    @staticmethod
    def _failed(
        reason_code: str,
        message: str,
        *,
        authority: str = "adapter_validation",
        post_reference: str | None = None,
    ) -> dict[str, Any]:
        """Build a stable failed result record."""

        result: dict[str, Any] = {
            "status": "failed",
            "reason_code": reason_code,
            "message": message,
            "capability_ref": CAPABILITY_REF,
            "authority": authority,
            "post_text": None,
        }
        if post_reference is not None:
            result["post_reference"] = post_reference
        return result
