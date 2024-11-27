"""Configuration settings for the radio telemetry tracker drone."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


class ConfigError(Exception):
    """Custom exception for configuration errors."""

@dataclass
class HardwareConfig:
    """Configuration for hardware components."""

    GPS_INTERFACE: str
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
            raise FileNotFoundError(msg)
        with path.open() as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HardwareConfig:
        """Load hardware configuration from a dictionary."""
        if "GPS_INTERFACE" not in data:
            msg = "Missing required field: GPS_INTERFACE"
            raise KeyError(msg)

        gps_interface = data["GPS_INTERFACE"].upper()
        if gps_interface == "I2C":
            return cls._create_i2c_config(data)
        if gps_interface == "SERIAL":
            return cls._create_serial_config(data)
        if gps_interface == "SIMULATED":
            return cls._create_simulation_config(data)
        msg = f"Unsupported GPS interface: {gps_interface}"
        raise ValueError(msg)

    @classmethod
    def _create_i2c_config(cls, data: dict[str, Any]) -> HardwareConfig:
        """Create I2C configuration from dictionary data."""
        required_fields = ["GPS_I2C_BUS", "GPS_ADDRESS"]
        cls._validate_required_fields(data, required_fields, "I2C")

        if not isinstance(data["GPS_I2C_BUS"], int):
            msg = "GPS_I2C_BUS must be an integer"
            raise TypeError(msg)
        if not isinstance(data["GPS_ADDRESS"], str):
            msg = "GPS_ADDRESS must be a string"
            raise TypeError(msg)

        try:
            gps_address = int(data["GPS_ADDRESS"], 16)
        except ValueError as e:
            msg = "GPS_ADDRESS must be a valid hexadecimal string"
            raise ValueError(msg) from e

        return cls(
            GPS_INTERFACE="I2C",
            GPS_I2C_BUS=data["GPS_I2C_BUS"],
            GPS_ADDRESS=gps_address,
        )

    @classmethod
    def _create_serial_config(cls, data: dict[str, Any]) -> HardwareConfig:
        """Create Serial configuration from dictionary data."""
        required_fields = ["GPS_SERIAL_PORT", "GPS_SERIAL_BAUDRATE"]
        cls._validate_required_fields(data, required_fields, "Serial")

        if not isinstance(data["GPS_SERIAL_PORT"], str):
            msg = "GPS_SERIAL_PORT must be a string"
            raise TypeError(msg)
        if not isinstance(data["GPS_SERIAL_BAUDRATE"], int):
            msg = "GPS_SERIAL_BAUDRATE must be an integer"
            raise TypeError(msg)

        return cls(
            GPS_INTERFACE="SERIAL",
            GPS_SERIAL_PORT=data["GPS_SERIAL_PORT"],
            GPS_SERIAL_BAUDRATE=data["GPS_SERIAL_BAUDRATE"],
        )

    @classmethod
    def _create_simulation_config(cls, data: dict[str, Any]) -> HardwareConfig:
        """Create Simulation configuration from dictionary data."""
        simulated_speed = data.get("GPS_SIMULATION_SPEED", 1.0)
        if not isinstance(simulated_speed, (int, float)):
            msg = "GPS_SIMULATION_SPEED must be a number"
            raise TypeError(msg)
        return cls(GPS_INTERFACE="SIMULATED", GPS_SIMULATION_SPEED=simulated_speed)

    @staticmethod
    def _validate_required_fields(data: dict[str, Any], required_fields: list[str], interface_type: str) -> None:
        """Validate that all required fields are present in the data."""
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            msg = f"Missing required fields for {interface_type} interface: {', '.join(missing_fields)}"
            raise KeyError(msg)

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
            raise FileNotFoundError(msg)
        with path.open() as f:
            data = json.load(f)
        # Add output_dir based on config file location
        data["output_dir"] = str(path.parent / "rtt_output")
        return cls.from_dict(data)

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
        }
        for field, expected_type in required_fields.items():
            if field not in data:
                msg = f"Missing required field: {field}"
                raise KeyError(msg)
            if not isinstance(data[field], expected_type):
                msg = f"Field {field} must be of type {expected_type.__name__}, got {type(data[field]).__name__}"
                raise TypeError(msg)
        if not data["target_frequencies"]:
            msg = "target_frequencies list cannot be empty"
            raise ValueError(msg)
        if not all(isinstance(freq, int) for freq in data["target_frequencies"]):
            msg = "All target_frequencies must be integers"
            raise ValueError(msg)
        return cls(**data)
