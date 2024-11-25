"""Configuration settings for the radio telemetry tracker drone."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Config:
    """Configuration class for radio telemetry tracker drone settings."""

    def __init__(self) -> None:
        """Initialize the Config object by loading hardware configuration."""
        hardware_config = self._load_hardware_config()
        self.GPS_I2C_BUS = hardware_config["GPS_I2C_BUS"]
        self.GPS_ADDRESS = int(hardware_config["GPS_ADDRESS"], 16)
        self.PING_FINDER_CONFIG = self._load_ping_finder_config()

    def _load_hardware_config(self) -> dict[str, Any]:
        """Load hardware configuration from JSON file.

        Raises:
            FileNotFoundError: If hardware_config.json is not found
            KeyError: If required configuration keys are missing
            ValueError: If configuration values are invalid
        """
        config_path = Path("./config/hardware_config.json")

        if not config_path.exists():
            msg = "Hardware configuration file not found at ./config/hardware_config.json"
            raise FileNotFoundError(
                msg,
            )

        with config_path.open() as f:
            config = json.load(f)

        # Validate required fields
        required_fields = ["GPS_I2C_BUS", "GPS_ADDRESS"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            msg = f"Missing required fields in hardware_config.json: {', '.join(missing_fields)}"
            raise KeyError(
                msg,
            )

        # Validate field types
        if not isinstance(config["GPS_I2C_BUS"], int):
            msg = "GPS_I2C_BUS must be an integer"
            raise TypeError(msg)

        if not isinstance(config["GPS_ADDRESS"], str):
            msg = "GPS_ADDRESS must be a string"
            raise TypeError(msg)

        try:
            int(config["GPS_ADDRESS"], 16)
        except ValueError as e:
            msg = "GPS_ADDRESS must be a valid hexadecimal string"
            raise ValueError(msg) from e

        return config

    def _load_ping_finder_config(self) -> dict[str, Any]:
        """Load PingFinder configuration from USB stick.

        Raises:
            FileNotFoundError: If ping_finder_config.json is not found
            KeyError: If required configuration keys are missing
            ValueError: If configuration values are invalid
        """
        config_path, _ = self._find_ping_finder_config()
        if not config_path:
            msg = "ping_finder_config.json not found in USB mount point (/media/usbstick)"
            raise FileNotFoundError(msg)

        with config_path.open() as f:
            config = json.load(f)

        self._validate_config_data(config)
        self._validate_target_frequencies(config)
        self._validate_numeric_ranges(config)

        return config

    def _validate_config_data(self, config_data: dict[str, Any]) -> None:
        """Validate configuration data.

        Args:
            config_data: Configuration dictionary to validate
        """
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
        }

        def validate_field(field: str, expected_type: type) -> None:
            if field not in config_data:
                msg = f"Missing required field: {field}"
                raise KeyError(msg)
            if not isinstance(config_data[field], expected_type):
                msg = f"Field {field} must be of type {expected_type.__name__}, got {type(config_data[field]).__name__}"
                raise TypeError(msg)

        for field, expected_type in required_fields.items():
            validate_field(field, expected_type)

        if not config_data["target_frequencies"]:
            msg = "target_frequencies list cannot be empty"
            raise ValueError(msg)
        if not all(isinstance(freq, int) for freq in config_data["target_frequencies"]):
            msg = "All target_frequencies must be integers"
            raise ValueError(msg)

    def _validate_target_frequencies(self, config: dict[str, Any]) -> None:
        """Validate target frequencies configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If target frequencies are invalid
        """
        if not config["target_frequencies"]:
            msg = "target_frequencies list cannot be empty"
            raise ValueError(msg)
        if not all(isinstance(freq, int) for freq in config["target_frequencies"]):
            msg = "All target_frequencies must be integers"
            raise ValueError(msg)

    def _validate_numeric_ranges(self, config: dict[str, Any]) -> None:
        """Validate numeric ranges in configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If any numeric value is not positive
        """
        positive_fields = [
            "gain",
            "sampling_rate",
            "center_frequency",
            "ping_width_ms",
            "ping_min_snr",
            "ping_max_len_mult",
            "ping_min_len_mult",
        ]

        for field in positive_fields:
            if config[field] <= 0:
                msg = f"{field} must be positive"
                raise ValueError(msg)

    def _find_ping_finder_config(self) -> tuple[Path | None, Path | None]:
        """Find ping_finder_config.json in /media directory.

        Returns:
            tuple[Path | None, Path | None]: Tuple of (config file path, output directory path) if found,
                                           else (None, None)
        """
        logger.debug("Starting search for ping_finder_config.json")

        media_path = Path("/media/usbstick")
        if not media_path.exists():
            logger.debug("Mount point /media/usbstick does not exist")
            return None, None

        config_file = media_path / "ping_finder_config.json"
        if config_file.exists():
            # Create output directory next to config file
            output_dir = config_file.parent / "rtt_output"
            logger.info("Found config file: %s", config_file)
            return config_file, output_dir

        # More detailed error message
        files = list(media_path.glob("*"))
        if files:
            logger.warning("Files found in /media/usbstick: %s", ", ".join(str(f) for f in files))
        else:
            logger.warning("/media/usbstick is empty")

        logger.warning("ping_finder_config.json not found in /media/usbstick")
        return None, None

    def to_dict(self) -> dict[str, Any]:
        """Convert the configuration to a dictionary."""
        return {
            "GPS_I2C_BUS": self.GPS_I2C_BUS,
            "GPS_ADDRESS": self.GPS_ADDRESS,
            "PING_FINDER_CONFIG": self.PING_FINDER_CONFIG,
        }


config = Config()
