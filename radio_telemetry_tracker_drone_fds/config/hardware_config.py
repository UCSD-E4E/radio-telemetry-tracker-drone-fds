"""Hardware configuration management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from radio_telemetry_tracker_drone_fds.config.errors import ConfigError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HardwareConfig:
    """Configuration for hardware components."""

    GPS_INTERFACE: str
    EPSG_CODE: int
    CHECK_USB_FOR_CONFIG: bool
    SDR_TYPE: str
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
                config = cls._create_i2c_config(data)
            elif gps_interface == "SERIAL":
                config = cls._create_serial_config(data)
            elif gps_interface == "SIMULATED":
                config = cls._create_simulation_config(data)
            else:
                msg = f"Unsupported GPS interface: {gps_interface}"
                raise ValueError(msg)

            # Ensure CHECK_USB_FOR_CONFIG and SDR_TYPE are present
            if "CHECK_USB_FOR_CONFIG" not in data:
                msg = "Missing required field: CHECK_USB_FOR_CONFIG"
                raise ConfigError(msg)
            config.CHECK_USB_FOR_CONFIG = data["CHECK_USB_FOR_CONFIG"]

            if "SDR_TYPE" not in data:
                msg = "Missing required field: SDR_TYPE"
                raise ConfigError(msg)
            valid_sdr_types = ["USRP", "AIRSPY", "HACKRF", "GENERATOR"]
            config.SDR_TYPE = data["SDR_TYPE"].upper()
            if config.SDR_TYPE not in valid_sdr_types:
                msg = f"Invalid SDR_TYPE: {config.SDR_TYPE}. Valid options: {', '.join(valid_sdr_types)}"
                raise ValueError(msg)

        except KeyError as e:
            msg = f"Missing required field: {e.args[0]}"
            raise ConfigError(msg) from e
        else:
            return config

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
            CHECK_USB_FOR_CONFIG=data["CHECK_USB_FOR_CONFIG"],
            SDR_TYPE=cls._validate_sdr_type(data["SDR_TYPE"]),
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
            CHECK_USB_FOR_CONFIG=data["CHECK_USB_FOR_CONFIG"],
            SDR_TYPE=cls._validate_sdr_type(data["SDR_TYPE"]),
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
            CHECK_USB_FOR_CONFIG=data["CHECK_USB_FOR_CONFIG"],
            SDR_TYPE=cls._validate_sdr_type(data["SDR_TYPE"]),
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

    @staticmethod
    def _validate_sdr_type(sdr_type: str) -> str:
        """Validate the SDR type."""
        valid_sdr_types = ["USRP", "AIRSPY", "HACKRF", "GENERATOR"]
        sdr_type_upper = sdr_type.upper()
        if sdr_type_upper not in valid_sdr_types:
            msg = f"Invalid SDR_TYPE: {sdr_type_upper}. Valid options are: {', '.join(valid_sdr_types)}"
            logger.error(msg)
            raise ConfigError(msg)
        return sdr_type_upper
