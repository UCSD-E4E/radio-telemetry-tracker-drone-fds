"""Configuration settings for the radio telemetry tracker drone."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class Config:
    """Configuration class for radio telemetry tracker drone settings."""

    def __init__(self) -> None:
        """Initialize the Config object with default values."""
        self.GPS_I2C_BUS = int(os.getenv("GPS_I2C_BUS", "1"))
        self.GPS_ADDRESS = int(os.getenv("GPS_ADDRESS", "0x42"), 16)

        self.PING_FINDER_CONFIG = self._load_ping_finder_config()

    def _load_ping_finder_config(self) -> dict[str, Any]:
        default_config = {
            "gain": 56.0,
            "sampling_rate": 2500000,
            "center_frequency": 173500000,
            "run_num": 1,
            "enable_test_data": False,
            "output_dir": str(self._get_output_dir()),
            "ping_width_ms": 25,
            "ping_min_snr": 25,
            "ping_max_len_mult": 1.5,
            "ping_min_len_mult": 0.5,
            "target_frequencies": [173043000],
        }

        user_config = json.loads(os.getenv("PING_FINDER_CONFIG", "{}"))
        return {**default_config, **user_config}

    def _get_output_dir(self) -> Path:
        for mount_point in ("/media", "/mnt"):
            for path in Path(mount_point).glob("*"):
                if path.is_mount():
                    return path / "rtt_output"
        return Path("./rtt_output")

    def to_dict(self) -> dict[str, Any]:
        """Convert the configuration to a dictionary."""
        return {
            "GPS_I2C_BUS": self.GPS_I2C_BUS,
            "GPS_ADDRESS": self.GPS_ADDRESS,
            "PING_FINDER_CONFIG": self.PING_FINDER_CONFIG,
        }


config = Config()
