"""Ping Finder configuration management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Custom exception for configuration errors."""


@dataclass
class PingFinderConfig:
    """Configuration for the ping finder."""

    gain: float
    sampling_rate: int
    center_frequency: int
    run_num: int
    enable_test_data: bool
    ping_width_ms: int
    ping_min_snr: int
    ping_max_len_mult: float
    ping_min_len_mult: float
    target_frequencies: list[int]
    output_dir: str

    @classmethod
    def load_from_file(cls, path: Path) -> PingFinderConfig:
        """Load ping finder configuration from a JSON file."""
        if not path.exists():
            msg = f"PingFinder configuration file not found at {path}"
            logger.error(msg)
            raise FileNotFoundError(msg)
        try:
            with path.open() as f:
                data = json.load(f)
            # Always set output_dir based on config file location
            data["output_dir"] = str(path.parent / "rtt_output")
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            logger.exception("Invalid JSON in ping finder configuration file.")
            msg = "Invalid JSON in ping finder configuration file."
            raise ConfigError(msg) from e

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PingFinderConfig:
        """Load ping finder configuration from a dictionary."""
        required_fields = {
            "gain": float,
            "sampling_rate": int,
            "center_frequency": int,
            "run_num": int,
            "enable_test_data": bool,
            "ping_width_ms": int,
            "ping_min_snr": int,
            "ping_max_len_mult": float,
            "ping_min_len_mult": float,
            "target_frequencies": list,
            "output_dir": str,
        }
        for field, expected_type in required_fields.items():
            if field not in data:
                msg = f"Missing required field: {field}"
                logger.error(msg)
                raise ConfigError(msg)
            if not isinstance(data[field], expected_type):
                msg = f"Field {field} must be of type {expected_type.__name__}, got {type(data[field]).__name__}"
                logger.error(msg)
                raise TypeError(msg)
        if not data["target_frequencies"]:
            msg = "target_frequencies list cannot be empty"
            logger.error(msg)
            raise ValueError(msg)
        if not all(isinstance(freq, int) for freq in data["target_frequencies"]):
            msg = "All target_frequencies must be integers"
            logger.error(msg)
            raise ValueError(msg)
        return cls(**data)
