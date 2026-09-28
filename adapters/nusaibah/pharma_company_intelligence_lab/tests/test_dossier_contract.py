from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

from dossier_contract import (  # noqa: E402
    CANONICAL_SECTIONS,
    canonical_section_ids,
    normalize_sections,
    render_empty_sections,
)


def _raw_sections() -> list[dict]:
    sections = render_empty_sections()
    for section in sections:
        section.pop("title", None)
        section["content"] = f"Content for {section['section_id']}"
        for subsection in section["subsections"]:
            subsection.pop("title", None)
            subsection["content"] = f"Content for {subsection['subsection_id']}"
    return sections


class CanonicalRenderingTests(unittest.TestCase):
    def test_empty_renderer_uses_exact_canonical_order_and_titles(self) -> None:
        rendered = render_empty_sections()

        self.assertEqual(
            [section["section_id"] for section in rendered],
            list(canonical_section_ids()),
        )
        self.assertEqual(
            [section["title"] for section in rendered],
            [section.title for section in CANONICAL_SECTIONS],
        )

    def test_provider_titles_cannot_override_canonical_titles(self) -> None:
        raw = _raw_sections()
        raw[2]["title"] = "Provider Renamed Company Section"
        raw[2]["subsections"][0]["title"] = "Provider Renamed Identity"

        normalized = normalize_sections(raw)

        self.assertEqual(normalized[2]["title"], "Company Profile")
        self.assertEqual(normalized[2]["subsections"][0]["title"], "Identity")


class SectionValidationTests(unittest.TestCase):
    def test_rejects_missing_section(self) -> None:
        raw = _raw_sections()[:-1]
        with self.assertRaises(ValueError):
            normalize_sections(raw)

    def test_rejects_unknown_section(self) -> None:
        raw = _raw_sections()
        raw[0]["section_id"] = "unknown_section"
        with self.assertRaises(ValueError):
            normalize_sections(raw)

    def test_rejects_duplicate_section(self) -> None:
        raw = _raw_sections()
        raw[1] = copy.deepcopy(raw[0])
        with self.assertRaises(ValueError):
            normalize_sections(raw)

    def test_rejects_reordered_sections(self) -> None:
        raw = _raw_sections()
        raw[0], raw[1] = raw[1], raw[0]
        with self.assertRaises(ValueError):
            normalize_sections(raw)


class SubsectionValidationTests(unittest.TestCase):
    def _company_profile(self, raw: list[dict]) -> dict:
        return next(section for section in raw if section["section_id"] == "company_profile")

    def test_rejects_missing_subsection(self) -> None:
        raw = _raw_sections()
        profile = self._company_profile(raw)
        profile["subsections"] = profile["subsections"][:-1]
        with self.assertRaises(ValueError):
            normalize_sections(raw)

    def test_rejects_unknown_subsection(self) -> None:
        raw = _raw_sections()
        profile = self._company_profile(raw)
        profile["subsections"][0]["subsection_id"] = "unknown_subsection"
        with self.assertRaises(ValueError):
            normalize_sections(raw)

    def test_rejects_duplicate_subsection(self) -> None:
        raw = _raw_sections()
        profile = self._company_profile(raw)
        profile["subsections"][1] = copy.deepcopy(profile["subsections"][0])
        with self.assertRaises(ValueError):
            normalize_sections(raw)

    def test_rejects_reordered_subsections(self) -> None:
        raw = _raw_sections()
        profile = self._company_profile(raw)
        profile["subsections"][0], profile["subsections"][1] = (
            profile["subsections"][1],
            profile["subsections"][0],
        )
        with self.assertRaises(ValueError):
            normalize_sections(raw)


if __name__ == "__main__":
    unittest.main()
