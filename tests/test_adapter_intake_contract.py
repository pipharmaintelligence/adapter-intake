from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTERS_ROOT = REPO_ROOT / "adapters"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,80}$")


def _adapter_yaml_scalars(path: Path) -> dict[str, str]:
    """Read the strict top-level scalar fields needed by the intake guard."""
    wanted = {"asset_key", "asset_version", "manifest"}
    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[:1].isspace() or ":" not in raw_line:
            continue

        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        if key not in wanted:
            continue

        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value

    missing = sorted(wanted - values.keys())
    if missing:
        raise AssertionError(
            f"{path.relative_to(REPO_ROOT)} is missing required scalar(s): {', '.join(missing)}"
        )

    return values


def _optional_top_level_scalar(path: Path, key: str) -> str | None:
    """Read one optional strict top-level scalar from adapter.yaml."""

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[:1].isspace() or ":" not in raw_line:
            continue
        raw_key, raw_value = raw_line.split(":", 1)
        if raw_key.strip() != key:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value or None
    return None


def _skill_refs(raw: object, *, field: str, manifest_path: Path) -> list[dict[str, str]]:
    """Validate one ordered Skill reference list and return normalized entries."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AssertionError(
            f"{manifest_path.relative_to(REPO_ROOT)} field {field} must be a list"
        )

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise AssertionError(
                f"{manifest_path.relative_to(REPO_ROOT)} {field}[{index}] must be an object"
            )

        if set(item) != {"skill_ref", "version", "digest"}:
            raise AssertionError(
                f"{manifest_path.relative_to(REPO_ROOT)} {field}[{index}] must define "
                "exactly skill_ref, version, and digest"
            )

        skill_ref = item["skill_ref"]
        version = item["version"]
        digest = item["digest"]

        if not isinstance(skill_ref, str) or not skill_ref.strip() or "." not in skill_ref:
            raise AssertionError(
                f"{manifest_path.relative_to(REPO_ROOT)} {field}[{index}] has invalid skill_ref"
            )
        if not isinstance(version, str) or VERSION_RE.fullmatch(version) is None:
            raise AssertionError(
                f"{manifest_path.relative_to(REPO_ROOT)} {field}[{index}] has invalid version"
            )
        if not isinstance(digest, str) or DIGEST_RE.fullmatch(digest) is None:
            raise AssertionError(
                f"{manifest_path.relative_to(REPO_ROOT)} {field}[{index}] has invalid digest"
            )
        if skill_ref in seen:
            raise AssertionError(
                f"{manifest_path.relative_to(REPO_ROOT)} {field} duplicates {skill_ref}"
            )

        seen.add(skill_ref)
        normalized.append(
            {"skill_ref": skill_ref, "version": version, "digest": digest}
        )

    return normalized


class AdapterIntakeContractTests(unittest.TestCase):
    def test_all_adapter_intakes_are_promotion_shape_safe(self) -> None:
        adapter_yamls = sorted(ADAPTERS_ROOT.glob("*/*/adapter.yaml"))
        self.assertTrue(adapter_yamls, "No adapter.yaml contracts were discovered")

        for adapter_yaml in adapter_yamls:
            with self.subTest(adapter_yaml=str(adapter_yaml.relative_to(REPO_ROOT))):
                contract = _adapter_yaml_scalars(adapter_yaml)
                adapter_dir = adapter_yaml.parent
                manifest_path = adapter_dir / contract["manifest"]

                self.assertTrue(
                    manifest_path.is_file(),
                    f"Missing manifest declared by {adapter_yaml.relative_to(REPO_ROOT)}",
                )

                dependency_name = _optional_top_level_scalar(
                    adapter_yaml,
                    "dependency_manifest",
                )
                if dependency_name is not None:
                    dependency_path = adapter_dir / dependency_name
                    self.assertTrue(
                        dependency_path.is_file(),
                        f"Missing dependency manifest declared by {adapter_yaml.relative_to(REPO_ROOT)}",
                    )
                    dependency = json.loads(
                        dependency_path.read_text(encoding="utf-8-sig")
                    )
                    self.assertEqual(
                        "adapter_dependencies.v1",
                        dependency.get("schema_version"),
                    )
                    runtime_package = dependency.get("runtime_package")
                    if runtime_package is not None:
                        self.assertIsInstance(runtime_package, dict)
                        self.assertEqual(
                            "pi-obs-python-runtime",
                            runtime_package.get("name"),
                        )
                        minimum_version = runtime_package.get("minimum_version")
                        self.assertIsInstance(minimum_version, str)
                        self.assertRegex(
                            minimum_version,
                            r"^\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.-]+)?$",
                        )

                manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
                self.assertIsInstance(manifest, dict)
                self.assertEqual(manifest.get("key"), contract["asset_key"])
                self.assertEqual(manifest.get("default"), contract["asset_version"])

                versions = manifest.get("versions")
                self.assertIsInstance(versions, dict)
                self.assertIn(contract["asset_version"], versions)

                version_manifest = versions[contract["asset_version"]]
                self.assertIsInstance(version_manifest, dict)

                bundled = _skill_refs(
                    version_manifest.get("skills"),
                    field="skills",
                    manifest_path=manifest_path,
                )
                published = _skill_refs(
                    version_manifest.get("published_skills"),
                    field="published_skills",
                    manifest_path=manifest_path,
                )

                bundled_refs = {item["skill_ref"] for item in bundled}
                published_refs = {item["skill_ref"] for item in published}
                overlap = sorted(bundled_refs & published_refs)
                self.assertFalse(
                    overlap,
                    "The same skill_ref cannot be declared in both skills and "
                    f"published_skills: {overlap}",
                )

                runtime_skills_root = adapter_dir / "skills"
                bundled_names = {item["skill_ref"].rsplit(".", 1)[-1] for item in bundled}
                published_names = {
                    item["skill_ref"].rsplit(".", 1)[-1] for item in published
                }

                for item in bundled:
                    skill_name = item["skill_ref"].rsplit(".", 1)[-1]
                    self.assertTrue(
                        (runtime_skills_root / skill_name / "SKILL.md").is_file(),
                        f"Bundled Skill {item['skill_ref']} must provide skills/{skill_name}/SKILL.md",
                    )

                for skill_name in sorted(published_names):
                    self.assertFalse(
                        (runtime_skills_root / skill_name).exists(),
                        "Publication-backed Skill bytes must not remain under the runtime "
                        f"intake skills/ directory: {skill_name}. Move deterministic copies "
                        "to tests/fixtures/skills instead.",
                    )

                if runtime_skills_root.exists():
                    undeclared_runtime_skills = sorted(
                        child.name
                        for child in runtime_skills_root.iterdir()
                        if child.is_dir() and child.name not in bundled_names
                    )
                    self.assertFalse(
                        undeclared_runtime_skills,
                        "Runtime skills/ contains directories that are not declared by "
                        f"skills[]: {undeclared_runtime_skills}",
                    )


if __name__ == "__main__":
    unittest.main()
