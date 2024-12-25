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
    USE_USB_STORAGE: bool
    SDR_TYPE: str
    OPERATION_MODE: str
    GPS_I2C_BUS: int | None = None
    GPS_ADDRESS: int | None = None
    GPS_SERIAL_PORT: str | None = None
    GPS_SERIAL_BAUDRATE: int | None = None
    GPS_SIMULATION_SPEED: float = 1.0
    RADIO_INTERFACE: str | None = None
    RADIO_PORT: str | None = None
    RADIO_BAUDRATE: int | None = None
    RADIO_HOST: str | None = None
    RADIO_TCP_PORT: int | None = None
    RADIO_SERVER_MODE: bool = False

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
    def _validate_operation_mode(cls, data: dict[str, Any]) -> str:
        """Validate operation mode configuration."""
        if "OPERATION_MODE" not in data:
            msg = "Missing required field: OPERATION_MODE"
            raise ConfigError(msg)

        operation_mode = data["OPERATION_MODE"].upper()
        if operation_mode not in ["OFFLINE", "ONLINE"]:
            msg = f"Invalid OPERATION_MODE: {operation_mode}. Must be 'OFFLINE' or 'ONLINE'"
            raise ConfigError(msg)
        return operation_mode

    @classmethod
    def _configure_radio_settings(cls, config: HardwareConfig, data: dict[str, Any]) -> None:
        """Configure radio settings for online mode."""
        config.RADIO_INTERFACE = data["RADIO_INTERFACE"]
        if config.RADIO_INTERFACE.lower() == "serial":
            config.RADIO_PORT = data["RADIO_PORT"]
            config.RADIO_BAUDRATE = int(data["RADIO_BAUDRATE"])
        elif config.RADIO_INTERFACE.lower() == "simulated":
            config.RADIO_HOST = data["RADIO_HOST"]
            config.RADIO_TCP_PORT = int(data["RADIO_TCP_PORT"])
        config.RADIO_SERVER_MODE = data.get("RADIO_SERVER_MODE", False)

    @classmethod
    def _create_gps_config(cls, data: dict[str, Any]) -> HardwareConfig:
        """Create GPS configuration based on interface type."""
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
    def from_dict(cls, data: dict[str, Any]) -> HardwareConfig:
        """Load hardware configuration from a dictionary."""
        try:
            operation_mode = cls._validate_operation_mode(data)
            config = cls._create_gps_config(data)

            # Set operation mode and validate radio config if online
            config.OPERATION_MODE = operation_mode
            if operation_mode == "ONLINE":
                cls._validate_radio_config(data, operation_mode)
                cls._configure_radio_settings(config, data)

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
            USE_USB_STORAGE=data["USE_USB_STORAGE"],
            SDR_TYPE=cls._validate_sdr_type(data["SDR_TYPE"]),
            GPS_I2C_BUS=gps_i2c_bus,
            GPS_ADDRESS=gps_address,
            EPSG_CODE=epsg_code,
            OPERATION_MODE=data["OPERATION_MODE"],
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
            USE_USB_STORAGE=data["USE_USB_STORAGE"],
            SDR_TYPE=cls._validate_sdr_type(data["SDR_TYPE"]),
            GPS_SERIAL_PORT=data["GPS_SERIAL_PORT"],
            GPS_SERIAL_BAUDRATE=gps_serial_baudrate,
            EPSG_CODE=epsg_code,
            OPERATION_MODE=data["OPERATION_MODE"],
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
            USE_USB_STORAGE=data["USE_USB_STORAGE"],
            SDR_TYPE=cls._validate_sdr_type(data["SDR_TYPE"]),
            GPS_SIMULATION_SPEED=simulated_speed,
            EPSG_CODE=epsg_code,
            OPERATION_MODE=data["OPERATION_MODE"],
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

    @classmethod
    def _validate_radio_config(cls, data: dict[str, Any], operation_mode: str) -> None:
        """Validate radio communication configuration."""
        if operation_mode == "OFFLINE":
            return

        if "RADIO_INTERFACE" not in data:
            msg = "Missing required field: RADIO_INTERFACE"
            raise ConfigError(msg)

        radio_interface = data["RADIO_INTERFACE"].lower()
        if radio_interface not in ["serial", "simulated"]:
            msg = f"Invalid RADIO_INTERFACE: {radio_interface}. Must be 'serial' or 'simulated'"
            raise ConfigError(msg)

        if radio_interface == "serial":
            required_fields = ["RADIO_PORT", "RADIO_BAUDRATE"]
            cls._validate_required_fields(data, required_fields, "Serial Radio")
            try:
                int(data["RADIO_BAUDRATE"])
            except ValueError as e:
                msg = "RADIO_BAUDRATE must be an integer"
                raise ConfigError(msg) from e

        elif radio_interface == "simulated":
            required_fields = ["RADIO_HOST", "RADIO_TCP_PORT"]
            cls._validate_required_fields(data, required_fields, "Simulated Radio")
            try:
                int(data["RADIO_TCP_PORT"])
            except ValueError as e:
                msg = "RADIO_TCP_PORT must be an integer"
                raise ConfigError(msg) from e

        if "RADIO_SERVER_MODE" in data and not isinstance(data["RADIO_SERVER_MODE"], bool):
            msg = "RADIO_SERVER_MODE must be a boolean"
            raise ConfigError(msg)
