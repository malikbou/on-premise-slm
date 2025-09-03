import os
import platform
from dataclasses import dataclass
from typing import Literal


ToggleDocProcEngine = Literal["hybrid", "docling_only", "legacy"]
ToggleOcrMode = Literal["auto", "off", "force"]
ToggleFallbackExtractor = Literal["off", "pdfplumber"]
ToggleChunkStrategy = Literal["hierarchical", "fixed"]
ToggleValidation = Literal["strict", "light"]
ToggleOutputStyle = Literal["gfm", "commonmark"]


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    value_norm = value.strip().lower()
    if value_norm in {"1", "true", "yes", "on"}:
        return True
    if value_norm in {"0", "false", "no", "off"}:
        return False
    return default


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


@dataclass(frozen=True)
class PlatformConfig:
    platform: Literal["mac_local", "vast_ai_gpu", "unknown"]
    doc_proc_engine: ToggleDocProcEngine
    table_ocr_mode: ToggleOcrMode
    table_fallback_extractor: ToggleFallbackExtractor
    chunk_strategy: ToggleChunkStrategy
    chunk_target_size: int
    validation_strictness: ToggleValidation
    save_intermediate: bool
    parallelism: Literal["low", "medium", "high"]
    output_md_style: ToggleOutputStyle


def get_platform_config() -> PlatformConfig:
    # Detect platform
    platform_override = os.getenv("PLATFORM", "auto").strip().lower()
    system_name = platform.system()

    if platform_override == "mac_local" or (platform_override == "auto" and system_name == "Darwin"):
        detected = "mac_local"
        defaults = {
            "DOC_PROC_ENGINE": "hybrid",
            "TABLE_OCR_MODE": "off",
            "TABLE_FALLBACK_EXTRACTOR": "off",
            "CHUNK_STRATEGY": "hierarchical",
            "CHUNK_TARGET_SIZE": 1000,
            "VALIDATION_STRICTNESS": "strict",
            "SAVE_INTERMEDIATE": False,
            "PARALLELISM": "low",
            "OUTPUT_MD_STYLE": "gfm",
        }
    elif platform_override == "vast_ai_gpu" or (platform_override == "auto" and system_name != "Darwin"):
        detected = "vast_ai_gpu"
        defaults = {
            "DOC_PROC_ENGINE": "hybrid",
            "TABLE_OCR_MODE": "auto",
            "TABLE_FALLBACK_EXTRACTOR": "off",
            "CHUNK_STRATEGY": "hierarchical",
            "CHUNK_TARGET_SIZE": 1400,
            "VALIDATION_STRICTNESS": "strict",
            "SAVE_INTERMEDIATE": False,
            "PARALLELISM": "high",
            "OUTPUT_MD_STYLE": "gfm",
        }
    else:
        detected = "unknown"
        defaults = {
            "DOC_PROC_ENGINE": "hybrid",
            "TABLE_OCR_MODE": "off",
            "TABLE_FALLBACK_EXTRACTOR": "off",
            "CHUNK_STRATEGY": "hierarchical",
            "CHUNK_TARGET_SIZE": 1000,
            "VALIDATION_STRICTNESS": "light",
            "SAVE_INTERMEDIATE": False,
            "PARALLELISM": "medium",
            "OUTPUT_MD_STYLE": "gfm",
        }

    def _get(name: str, cast=str):
        if cast is bool:
            return _get_env_bool(name, bool(defaults[name]))
        if cast is int:
            return _get_env_int(name, int(defaults[name]))
        return os.getenv(name, str(defaults[name]))

    return PlatformConfig(
        platform=detected,  # type: ignore
        doc_proc_engine=_get("DOC_PROC_ENGINE"),  # type: ignore
        table_ocr_mode=_get("TABLE_OCR_MODE"),  # type: ignore
        table_fallback_extractor=_get("TABLE_FALLBACK_EXTRACTOR"),  # type: ignore
        chunk_strategy=_get("CHUNK_STRATEGY"),  # type: ignore
        chunk_target_size=_get("CHUNK_TARGET_SIZE", int),
        validation_strictness=_get("VALIDATION_STRICTNESS"),  # type: ignore
        save_intermediate=_get("SAVE_INTERMEDIATE", bool),
        parallelism=os.getenv("PARALLELISM", str(defaults["PARALLELISM"])),  # low/medium/high
        output_md_style=_get("OUTPUT_MD_STYLE"),  # type: ignore
    )


__all__ = [
    "PlatformConfig",
    "get_platform_config",
]


