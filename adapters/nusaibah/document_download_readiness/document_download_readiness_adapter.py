from __future__ import annotations

from typing import Any

from adapters.base import Adapter
from system import CrawlerCapabilityContract


DOCUMENT_DOWNLOAD_CAPABILITY: CrawlerCapabilityContract = {
    "handle": "@crawler.document_download",
    "kind": "crawler",
    "mode": "governed_runtime_authority_crawl_mode",
    "auth": {"mode": "runtime_authority", "capability_ref": "crawler.document_download"},
    "runtime_profile": "document_download_extract",
    "operation": "download_document",
    "expected_input_role": "documents",
    "expected_output_role": "readiness",
}


class DocumentDownloadReadinessAdapter(Adapter):
    """Prepare safe document-download intent summaries for local validation.

    The adapter receives already-sanitized input rows. It does not accept target
    URLs, credentials, storage paths, buckets, object keys, cookies, raw HTML,
    or downloaded bytes. Live download authority belongs to Assets/Core.
    """

    key = "nusaibah.document_download_readiness"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Return a standard OBS adapter response envelope."""

        documents = self._records(inputs, "documents")
        accepted = [row for row in documents if self._safe_document_ref(row)]

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "readiness": {
                    "documents_seen": len(documents),
                    "documents_with_safe_ref": len(accepted),
                    "crawler_handle": DOCUMENT_DOWNLOAD_CAPABILITY["handle"],
                    "runtime_profile": DOCUMENT_DOWNLOAD_CAPABILITY["runtime_profile"],
                    "operation": DOCUMENT_DOWNLOAD_CAPABILITY["operation"],
                    "live_download_authority": "server_owned",
                }
            },
            "logs": [
                {
                    "level": "info",
                    "message": "Prepared safe document-download readiness summary.",
                }
            ],
            "metrics": {
                "document_count": len(documents),
                "safe_document_ref_count": len(accepted),
            },
        }

    @staticmethod
    def _records(inputs: dict[str, Any], role: str) -> list[dict[str, Any]]:
        value = inputs.get(role)
        if not isinstance(value, dict):
            raise ValueError(f"{role} input must be an object.")
        records = value.get("records")
        if not isinstance(records, list):
            raise ValueError(f"{role}.records must be a list.")
        return [row for row in records if isinstance(row, dict)]

    @staticmethod
    def _safe_document_ref(row: dict[str, Any]) -> str:
        value = row.get("document_ref")
        if not isinstance(value, str):
            return ""
        candidate = value.strip()
        if not candidate or "://" in candidate or "/" in candidate or "\\" in candidate:
            return ""
        return candidate


if __name__ == "__main__":
    import json
    from pathlib import Path

    fixture = Path(__file__).resolve().parent / "fixtures" / "document_download_readiness.inputs.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    print(json.dumps(DocumentDownloadReadinessAdapter().invoke(payload, {"mode": "direct_script_smoke"}), ensure_ascii=False, indent=2))
