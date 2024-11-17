"""Configuration settings for the radio telemetry tracker drone."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from configparser import ConfigParser

class Config:
    """Configuration class for radio telemetry tracker drone settings."""

    def __init__(self) -> None:
        """Initialize the Config object with default values."""
        self.GPS_I2C_BUS = int(os.getenv("GPS_I2C_BUS", "1"))
        self.GPS_ADDRESS = int(os.getenv("GPS_ADDRESS", "0x42"), 16)
        self.WAIT_TO_START_TIMER = int(os.getenv("WAIT_TO_START_TIMER", "60"))
        self.RUN_TIMER = int(os.getenv("RUN_TIMER", "3600"))

        self.PING_FINDER_CONFIG = self._load_ping_finder_config()

    conf = ConfigParser()
    conf.read(str(self.get_config_path()))

    def _load_ping_finder_config(self) -> dict[str, Any]:
        default_config = {
            "gain": conf.getfloat("signal", "gain"),
            "sampling_rate": conf.getint("signal", "sampling_rate"),
            "center_frequency": conf.getint("signal", "center_frequency"),
            "run_num": conf.getint("signal", "run_num"),
            "enable_test_data": conf.getboolean("signal", "enable_test_data"),
            "ping_width_ms": conf.get("ping", "ping_width_ms"),
            "ping_min_snr": conf.get("ping", "ping_min_snr"),
            "ping_max_len_mult": conf.get("ping", "ping_max_len_mult"),
            "ping_min_len_mult": conf.get("ping", "ping_min_len_mult"),
            "target_frequencies": conf.get("ping", "target_frequencies"),
            "output_dir": str(self._get_output_dir()),
        }

        user_config = json.loads(os.getenv("PING_FINDER_CONFIG", "{}"))
        return {**default_config, **user_config}

    def get_config_path(self) -> Path:
        for mount_point in ("/media", "/mnt"):
            for path in Path(mount_point).glob("*"):
                if path.is_mount():
                    file_path = path / config_file.ini
                    if file_path.exists() and file_path.is_file():
                        return file_path
        return None

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
            "WAIT_TO_START_TIMER": self.WAIT_TO_START_TIMER,
            "RUN_TIMER": self.RUN_TIMER,
            "PING_FINDER_CONFIG": self.PING_FINDER_CONFIG,
        }


config = Config()
