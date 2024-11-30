"""Configuration settings for the radio telemetry tracker drone."""

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
class HardwareConfig:
    """Configuration for hardware components."""

    GPS_INTERFACE: str
    EPSG_CODE: int
    GPS_I2C_BUS: int | None = None
    GPS_ADDRESS: int | None = None
    GPS_SERIAL_PORT: str | None = None
    GPS_SERIAL_BAUDRATE: int | None = None
    GPS_SIMULATION_SPEED: float = 1.0

    @classmethod
    def load_from_file(cls, path: Path) -> HardwareConfig:
        """Load hardware configuration from a JSON file."""
        if not path.exists():
            msg = f"Hardware configuration file not found at {path}"
            logger.error(msg)
            raise FileNotFoundError(msg)
        try:
            with path.open() as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            logger.exception("Invalid JSON in hardware configuration file.")
            msg = "Invalid JSON in hardware configuration file."
            raise ConfigError(msg) from e

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HardwareConfig:
        """Load hardware configuration from a dictionary."""
        try:
            gps_interface = data["GPS_INTERFACE"].upper()
            if gps_interface == "I2C":
                return cls._create_i2c_config(data)
            if gps_interface == "SERIAL":
                return cls._create_serial_config(data)
            if gps_interface == "SIMULATED":
                return cls._create_simulation_config(data)
            msg = f"Unsupported GPS interface: {gps_interface}"
            logger.error(msg)
            raise ValueError(msg)
        except KeyError as e:
            msg = f"Missing required field: {e.args[0]}"
            logger.exception(msg)
            raise ConfigError(msg) from e

    @classmethod
    def _create_i2c_config(cls, data: dict[str, Any]) -> HardwareConfig:
        """Create I2C configuration from dictionary data."""
        required_fields = ["GPS_I2C_BUS", "GPS_ADDRESS", "EPSG_CODE"]
        cls._validate_required_fields(data, required_fields, "I2C")

        try:
            gps_i2c_bus = int(data["GPS_I2C_BUS"])
            gps_address = int(data["GPS_ADDRESS"], 16)
            epsg_code = int(data["EPSG_CODE"])
        except ValueError as e:
            msg = "Invalid value in I2C configuration"
            logger.exception(msg)
            raise ConfigError(msg) from e

        return cls(
            GPS_INTERFACE="I2C",
            GPS_I2C_BUS=gps_i2c_bus,
            GPS_ADDRESS=gps_address,
            EPSG_CODE=epsg_code,
        )

    @classmethod
    def _create_serial_config(cls, data: dict[str, Any]) -> HardwareConfig:
        """Create Serial configuration from dictionary data."""
        required_fields = ["GPS_SERIAL_PORT", "GPS_SERIAL_BAUDRATE", "EPSG_CODE"]
        cls._validate_required_fields(data, required_fields, "Serial")

        try:
            gps_serial_baudrate = int(data["GPS_SERIAL_BAUDRATE"])
            epsg_code = int(data["EPSG_CODE"])
        except ValueError as e:
            msg = "Invalid value in Serial configuration"
            logger.exception(msg)
            raise ConfigError(msg) from e

        return cls(
            GPS_INTERFACE="SERIAL",
            GPS_SERIAL_PORT=data["GPS_SERIAL_PORT"],
            GPS_SERIAL_BAUDRATE=gps_serial_baudrate,
            EPSG_CODE=epsg_code,
        )

    @classmethod
    def _create_simulation_config(cls, data: dict[str, Any]) -> HardwareConfig:
        """Create Simulation configuration from dictionary data."""
        required_fields = ["EPSG_CODE"]
        cls._validate_required_fields(data, required_fields, "Simulation")

        simulated_speed = data.get("GPS_SIMULATION_SPEED", 1.0)
        if not isinstance(simulated_speed, (int, float)):
            msg = "GPS_SIMULATION_SPEED must be a number"
            logger.error(msg)
            raise TypeError(msg)
        try:
            epsg_code = int(data["EPSG_CODE"])
        except ValueError as e:
            msg = "Invalid EPSG_CODE in Simulation configuration"
            logger.exception(msg)
            raise ConfigError(msg) from e

        return cls(
            GPS_INTERFACE="SIMULATED",
            GPS_SIMULATION_SPEED=simulated_speed,
            EPSG_CODE=epsg_code,
        )

    @staticmethod
    def _validate_required_fields(data: dict[str, Any], required_fields: list[str], interface_type: str) -> None:
        """Validate that all required fields are present in the data."""
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            msg = f"Missing required fields for {interface_type} interface: {', '.join(missing_fields)}"
            logger.error(msg)
            raise ConfigError(msg)


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
            # Always set output_dir based on config file location, ignoring any value in the JSON
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
