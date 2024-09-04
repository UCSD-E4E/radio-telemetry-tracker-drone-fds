"""Configuration settings for the radio telemetry tracker drone."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import psutil

GPS_I2C_BUS = int(os.getenv("GPS_I2C_BUS", "1"))
GPS_ADDRESS = int(os.getenv("GPS_ADDRESS", "0x42"), 16)


def get_mounted_drive() -> str | None:
    """Return the mountpoint of the first mounted external drive, or None."""
    partitions = psutil.disk_partitions()
    for partition in partitions:
        if partition.mountpoint.startswith(
            "/media/",
        ) or partition.mountpoint.startswith("/mnt/"):
            return partition.mountpoint
    return None


# Default PING_FINDER_CONFIG
DEFAULT_PING_FINDER_CONFIG = {
    "gain": 56.0,
    "sampling_rate": 2500000,
    "center_frequency": 173500000,
    "run_num": 1,
    "enable_test_data": False,
    "output_dir": "./deleteme/",
    "ping_width_ms": 25,
    "ping_min_snr": 25,
    "ping_max_len_mult": 1.5,
    "ping_min_len_mult": 0.5,
    "target_frequencies": [173043000],
}

# Load PING_FINDER_CONFIG from environment variable if set, otherwise use default
mounted_drive = get_mounted_drive()
if mounted_drive:
    output_dir = Path(mounted_drive) / "rtt_output"
else:
    output_dir = Path("./rtt_output")

# Default configuration if environment variable is not set or invalid
DEFAULT_PING_FINDER_CONFIG = {
    "gain": 56.0,
    "sampling_rate": 2500000,
    "center_frequency": 173500000,
    "run_num": 1,
    "enable_test_data": False,
    "output_dir": str(output_dir),
    "ping_width_ms": 25,
    "ping_min_snr": 25,
    "ping_max_len_mult": 1.5,
    "ping_min_len_mult": 0.5,
    "target_frequencies": [173043000],
}

try:
    PING_FINDER_CONFIG = json.loads(os.getenv("PING_FINDER_CONFIG", "{}"))
    # Merge with default config, keeping user-specified values
    PING_FINDER_CONFIG = {**DEFAULT_PING_FINDER_CONFIG, **PING_FINDER_CONFIG}
except json.JSONDecodeError:
    logging.warning("Invalid JSON in PING_FINDER_CONFIG. Using default configuration.")
    PING_FINDER_CONFIG = DEFAULT_PING_FINDER_CONFIG
