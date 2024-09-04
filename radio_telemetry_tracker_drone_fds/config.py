"""Configuration settings for the radio telemetry tracker drone."""

import json
import os

GPS_I2C_BUS = int(os.getenv("GPS_I2C_BUS", "1"))
GPS_ADDRESS = int(os.getenv("GPS_ADDRESS", "0x42"), 16)

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
PING_FINDER_CONFIG = json.loads(os.getenv("PING_FINDER_CONFIG", "{}"))
PING_FINDER_CONFIG = {**DEFAULT_PING_FINDER_CONFIG, **PING_FINDER_CONFIG}

# Load WAIT_TIME from environment variable if set, otherwise use default
DEFAULT_WAIT_TIME = 60  # seconds
WAIT_TIME = int(os.getenv("WAIT_TIME", str(DEFAULT_WAIT_TIME)))
