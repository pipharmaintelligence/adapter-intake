from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adapters.base import Adapter


ASSET_KEY = "nusaibah.openmed_ner"
ASSET_VERSION = "0.1.0"
INPUT_ROLE = "text_records"
OUTPUT_ROLE = "ner_results"
EXPECTED_MODEL_REVISION = "d4259d05b0e924ad786f5c342ddedf46fe956331"

DEFAULT_MAX_RECORDS = 8
HARD_MAX_RECORDS = 32
DEFAULT_MAX_CHARACTERS = 4_000
HARD_MAX_CHARACTERS = 20_000
DEFAULT_MAX_LENGTH = 128
HARD_MAX_LENGTH = 512
DEFAULT_SCORE_THRESHOLD = 0.50

_ALLOWED_INPUT_FIELDS = {"records", "metadata", "provenance"}
_ALLOWED_RECORD_FIELDS = {"record_id", "text"}
_ALLOWED_DEVICES = {"auto", "cuda", "cpu"}

_CACHE_LOCK = threading.Lock()
_INFERENCE_LOCK = threading.Lock()
_RUNTIME_CACHE: dict[tuple[str, str, int], "OpenMedRuntime"] = {}


class OpenMedNerError(RuntimeError):
    """Fail safely when local model configuration or inference is invalid."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.safe_message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class OpenMedRuntime:
    """Loaded model resources cached for one process and one device profile."""

    torch: Any
    tokenizer: Any
    model: Any
    device: Any
    device_label: str
    dtype_name: str
    max_length: int


class OpenMedNerAdapter(Adapter):
    """Extract chemical and drug entities from bounded biomedical text records."""

    key = ASSET_KEY
    version = ASSET_VERSION

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Run offline token-classification inference over bounded input records.

        The adapter reads an immutable checkpoint prepared outside the repository.
        It does not download models, call provider services, publish outputs, or
        manage storage. The trusted runtime remains responsible for those concerns.
        """

        if not isinstance(inputs, dict):
            raise OpenMedNerError("inputs_invalid", "Adapter inputs must be an object.")
        if not isinstance(context, dict):
            raise OpenMedNerError("context_invalid", "Adapter context must be an object.")

        max_records = _bounded_int(
            context,
            "max_records",
            default=DEFAULT_MAX_RECORDS,
            minimum=1,
            maximum=HARD_MAX_RECORDS,
        )
        max_characters = _bounded_int(
            context,
            "max_characters",
            default=DEFAULT_MAX_CHARACTERS,
            minimum=1,
            maximum=HARD_MAX_CHARACTERS,
        )
        max_length = _bounded_int(
            context,
            "max_length",
            default=DEFAULT_MAX_LENGTH,
            minimum=8,
            maximum=HARD_MAX_LENGTH,
        )
        score_threshold = _bounded_float(
            context,
            "score_threshold",
            default=DEFAULT_SCORE_THRESHOLD,
            minimum=0.0,
            maximum=1.0,
        )

        records = _require_records(inputs, max_records=max_records, max_characters=max_characters)
        runtime = _get_runtime(max_length=max_length)

        output_records: list[dict[str, Any]] = []
        label_counts: dict[str, int] = {}
        total_entities = 0
        truncated_records = 0

        for record in records:
            entities, was_truncated, token_count = _infer_entities(
                runtime,
                record["text"],
                score_threshold=score_threshold,
            )
            if was_truncated:
                truncated_records += 1

            for entity in entities:
                label = entity["label"]
                label_counts[label] = label_counts.get(label, 0) + 1

            total_entities += len(entities)
            output_records.append(
                {
                    "record_id": record["record_id"],
                    "text_length": len(record["text"]),
                    "token_count": token_count,
                    "truncated": was_truncated,
                    "entity_count": len(entities),
                    "entities": entities,
                }
            )

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                OUTPUT_ROLE: {
                    "records": output_records,
                    "summary": {
                        "record_count": len(output_records),
                        "entity_count": total_entities,
                        "truncated_record_count": truncated_records,
                        "label_counts": dict(sorted(label_counts.items())),
                    },
                    "model": {
                        "revision": EXPECTED_MODEL_REVISION,
                        "task": "token-classification",
                        "entity_family": "chemical_or_drug",
                        "device": runtime.device_label,
                        "dtype": runtime.dtype_name,
                        "max_length": runtime.max_length,
                        "score_threshold": round(score_threshold, 6),
                    },
                }
            },
            "metrics": {
                "records_processed": len(output_records),
                "entities_detected": total_entities,
                "truncated_records": truncated_records,
            },
            "logs": [
                {
                    "level": "info",
                    "message": "OpenMed biomedical NER inference completed.",
                }
            ],
        }


def _require_records(
    inputs: dict[str, Any],
    *,
    max_records: int,
    max_characters: int,
) -> list[dict[str, str]]:
    value = inputs.get(INPUT_ROLE)
    if not isinstance(value, dict):
        raise OpenMedNerError(
            "text_records_invalid",
            f"{INPUT_ROLE} must be an object.",
        )

    unexpected_input_fields = sorted(set(value) - _ALLOWED_INPUT_FIELDS)
    if unexpected_input_fields:
        raise OpenMedNerError(
            "text_records_fields_invalid",
            f"{INPUT_ROLE} contains unsupported fields.",
        )

    raw_records = value.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise OpenMedNerError(
            "text_records_missing",
            f"{INPUT_ROLE}.records must be a non-empty array.",
        )
    if len(raw_records) > max_records:
        raise OpenMedNerError(
            "record_limit_exceeded",
            f"At most {max_records} records are allowed for this run.",
        )

    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, dict):
            raise OpenMedNerError(
                "record_invalid",
                "Each text record must be an object.",
            )

        if set(raw_record) - _ALLOWED_RECORD_FIELDS:
            raise OpenMedNerError(
                "record_fields_invalid",
                "Text records may contain only record_id and text.",
            )

        record_id = raw_record.get("record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise OpenMedNerError(
                "record_id_invalid",
                "Each text record requires a non-empty record_id.",
            )
        record_id = record_id.strip()
        if len(record_id) > 128:
            raise OpenMedNerError(
                "record_id_too_long",
                "record_id must contain at most 128 characters.",
            )
        if record_id in seen_ids:
            raise OpenMedNerError(
                "record_id_duplicate",
                "record_id values must be unique within one run.",
            )

        text = raw_record.get("text")
        if not isinstance(text, str) or not text.strip():
            raise OpenMedNerError(
                "record_text_invalid",
                "Each text record requires non-empty text.",
            )
        if len(text) > max_characters:
            raise OpenMedNerError(
                "record_text_too_long",
                f"Each text record must contain at most {max_characters} characters.",
            )

        seen_ids.add(record_id)
        normalized.append({"record_id": record_id, "text": text})

    return normalized


def _get_runtime(*, max_length: int) -> OpenMedRuntime:
    model_directory_value = os.environ.get("OPENMED_NER_MODEL_DIR", "").strip()
    if not model_directory_value:
        raise OpenMedNerError(
            "model_directory_missing",
            "OPENMED_NER_MODEL_DIR must identify the prepared local checkpoint.",
        )

    requested_device = os.environ.get("OPENMED_NER_DEVICE", "auto").strip().lower() or "auto"
    if requested_device not in _ALLOWED_DEVICES:
        raise OpenMedNerError(
            "device_policy_invalid",
            "OPENMED_NER_DEVICE must be auto, cuda, or cpu.",
        )

    model_directory = _resolve_model_directory(model_directory_value)
    _verify_model_revision(model_directory)
    cache_key = (str(model_directory), requested_device, max_length)

    with _CACHE_LOCK:
        cached = _RUNTIME_CACHE.get(cache_key)
        if cached is not None:
            return cached

        runtime = _load_runtime(
            model_directory=model_directory,
            requested_device=requested_device,
            max_length=max_length,
        )
        _RUNTIME_CACHE[cache_key] = runtime
        return runtime


def _resolve_model_directory(value: str) -> Path:
    try:
        resolved = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise OpenMedNerError(
            "model_directory_unavailable",
            "The prepared local checkpoint is unavailable.",
        ) from None

    if not resolved.is_dir():
        raise OpenMedNerError(
            "model_directory_invalid",
            "The prepared local checkpoint must be a directory.",
        )
    return resolved


def _verify_model_revision(model_directory: Path) -> None:
    revision_path = model_directory / "MODEL_REVISION.txt"
    try:
        revision = revision_path.read_text(encoding="utf-8").strip()
    except OSError:
        raise OpenMedNerError(
            "model_revision_missing",
            "The local checkpoint revision marker is missing.",
        ) from None

    if revision != EXPECTED_MODEL_REVISION:
        raise OpenMedNerError(
            "model_revision_mismatch",
            "The local checkpoint revision does not match the approved asset revision.",
        )


def _load_runtime(
    *,
    model_directory: Path,
    requested_device: str,
    max_length: int,
) -> OpenMedRuntime:
    try:
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError:
        raise OpenMedNerError(
            "inference_dependency_unavailable",
            "The approved OpenMed inference dependencies are unavailable.",
        ) from None

    if requested_device == "cuda":
        if not torch.cuda.is_available():
            raise OpenMedNerError(
                "cuda_unavailable",
                "CUDA was requested but no compatible GPU runtime is available.",
            )
        device = torch.device("cuda:0")
    elif requested_device == "cpu":
        device = torch.device("cpu")
    else:
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    dtype = torch.float16 if device.type == "cuda" else torch.float32

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_directory,
            local_files_only=True,
            use_fast=True,
            trust_remote_code=False,
        )
        if not getattr(tokenizer, "is_fast", False):
            raise OpenMedNerError(
                "fast_tokenizer_required",
                "The approved checkpoint requires a fast tokenizer with offset mappings.",
            )
        tokenizer.model_max_length = max_length

        model = AutoModelForTokenClassification.from_pretrained(
            model_directory,
            local_files_only=True,
            dtype=dtype,
            trust_remote_code=False,
        )
        model.to(device)
        model.eval()
    except OpenMedNerError:
        raise
    except Exception:
        raise OpenMedNerError(
            "model_load_failed",
            "The approved local checkpoint could not be loaded.",
        ) from None

    return OpenMedRuntime(
        torch=torch,
        tokenizer=tokenizer,
        model=model,
        device=device,
        device_label=str(device),
        dtype_name=str(dtype).replace("torch.", ""),
        max_length=max_length,
    )


def _infer_entities(
    runtime: OpenMedRuntime,
    text: str,
    *,
    score_threshold: float,
) -> tuple[list[dict[str, Any]], bool, int]:
    tokenizer = runtime.tokenizer
    torch = runtime.torch

    try:
        untruncated = tokenizer(
            text,
            add_special_tokens=True,
            truncation=False,
        )
        token_count = len(untruncated["input_ids"])

        encoded = tokenizer(
            text,
            add_special_tokens=True,
            truncation=True,
            max_length=runtime.max_length,
            return_offsets_mapping=True,
            return_special_tokens_mask=True,
            return_tensors="pt",
        )
        offsets = encoded.pop("offset_mapping")[0].tolist()
        special_tokens = encoded.pop("special_tokens_mask")[0].tolist()
        model_inputs = {
            key: value.to(runtime.device)
            for key, value in encoded.items()
        }

        with _INFERENCE_LOCK, torch.inference_mode():
            logits = runtime.model(**model_inputs).logits[0]
            probabilities = torch.softmax(logits, dim=-1)
            prediction_ids = torch.argmax(probabilities, dim=-1)
            prediction_scores = probabilities.gather(
                1,
                prediction_ids.unsqueeze(1),
            ).squeeze(1)

        labels = [
            str(runtime.model.config.id2label.get(int(prediction_id), prediction_id))
            for prediction_id in prediction_ids.detach().cpu().tolist()
        ]
        scores = [float(value) for value in prediction_scores.detach().cpu().tolist()]

        entities = _merge_bio_tokens(
            text=text,
            labels=labels,
            scores=scores,
            offsets=[(int(start), int(end)) for start, end in offsets],
            special_tokens=[bool(value) for value in special_tokens],
            score_threshold=score_threshold,
        )
        return entities, token_count > runtime.max_length, token_count
    except OpenMedNerError:
        raise
    except Exception as exc:
        out_of_memory = getattr(getattr(torch, "cuda", None), "OutOfMemoryError", ())
        if out_of_memory and isinstance(exc, out_of_memory):
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            raise OpenMedNerError(
                "cuda_out_of_memory",
                "The selected GPU profile does not have enough free memory for this request.",
            ) from None
        raise OpenMedNerError(
            "inference_failed",
            "OpenMed NER inference failed safely.",
        ) from None


def _merge_bio_tokens(
    *,
    text: str,
    labels: list[str],
    scores: list[float],
    offsets: list[tuple[int, int]],
    special_tokens: list[bool],
    score_threshold: float,
) -> list[dict[str, Any]]:
    if not (len(labels) == len(scores) == len(offsets) == len(special_tokens)):
        raise OpenMedNerError(
            "prediction_shape_invalid",
            "The model returned inconsistent token-classification output.",
        )

    entities: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        average_score = sum(current["scores"]) / len(current["scores"])
        if average_score >= score_threshold:
            start, end = _trim_entity_span(
                text,
                int(current["start"]),
                int(current["end"]),
            )
            if start < end:
                entities.append(
                    {
                        "text": text[start:end],
                        "label": str(current["label"]),
                        "score": round(float(average_score), 6),
                        "start": start,
                        "end": end,
                    }
                )
        current = None

    for label, score, (start, end), is_special in zip(
        labels,
        scores,
        offsets,
        special_tokens,
        strict=True,
    ):
        if is_special or start == end or label == "O":
            flush()
            continue

        if "-" in label:
            prefix, entity_label = label.split("-", 1)
        else:
            prefix, entity_label = "B", label

        start_new = (
            current is None
            or prefix == "B"
            or current["label"] != entity_label
            or start > int(current["end"]) + 1
        )
        if start_new:
            flush()
            current = {
                "label": entity_label,
                "start": start,
                "end": end,
                "scores": [score],
            }
            continue

        current["end"] = max(int(current["end"]), end)
        current["scores"].append(score)

    flush()
    return entities


def _trim_entity_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Remove tokenizer-owned boundary whitespace while preserving offsets."""
    bounded_start = max(0, min(start, len(text)))
    bounded_end = max(bounded_start, min(end, len(text)))

    while bounded_start < bounded_end and text[bounded_start].isspace():
        bounded_start += 1
    while bounded_end > bounded_start and text[bounded_end - 1].isspace():
        bounded_end -= 1

    return bounded_start, bounded_end


def _bounded_int(
    context: dict[str, Any],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = context.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise OpenMedNerError(
            "context_value_invalid",
            f"context.{key} must be an integer.",
        )
    if value < minimum or value > maximum:
        raise OpenMedNerError(
            "context_value_out_of_bounds",
            f"context.{key} must be between {minimum} and {maximum}.",
        )
    return value


def _bounded_float(
    context: dict[str, Any],
    key: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    value = context.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMedNerError(
            "context_value_invalid",
            f"context.{key} must be numeric.",
        )
    normalized = float(value)
    if normalized < minimum or normalized > maximum:
        raise OpenMedNerError(
            "context_value_out_of_bounds",
            f"context.{key} must be between {minimum} and {maximum}.",
        )
    return normalized
