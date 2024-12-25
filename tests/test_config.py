"""Tests for the configuration module."""
import json
from pathlib import Path
from typing import Any

import pytest

from radio_telemetry_tracker_drone_fds.config import ConfigError, HardwareConfig, PingFinderConfig


def test_hardware_config_load_from_file(tmp_path: Path, hardware_config_data: dict[str, Any]) -> None:
    """Test loading hardware configuration from a JSON file.

    Args:
        tmp_path: Fixture providing a temporary directory.
        hardware_config_data: Fixture providing test configuration data.
    """
    config_file = tmp_path / "hardware_config.json"
    config_file.write_text(json.dumps(hardware_config_data))
    config = HardwareConfig.load_from_file(config_file)
    assert hardware_config_data["GPS_INTERFACE"] == config.GPS_INTERFACE  # noqa: S101
    assert hardware_config_data["EPSG_CODE"] == config.EPSG_CODE  # noqa: S101
    assert hardware_config_data["USE_USB_STORAGE"] == config.USE_USB_STORAGE  # noqa: S101
    assert hardware_config_data["SDR_TYPE"] == config.SDR_TYPE  # noqa: S101
    assert hardware_config_data["OPERATION_MODE"] == config.OPERATION_MODE  # noqa: S101


def test_hardware_config_missing_file() -> None:
    """Test that attempting to load from a non-existent file raises an error."""
    with pytest.raises(FileNotFoundError):
        HardwareConfig.load_from_file(Path("non_existent_file.json"))


def test_hardware_config_invalid_json(tmp_path: Path) -> None:
    """Test that attempting to load invalid JSON raises a ConfigError."""
    invalid_json_file = tmp_path / "invalid_hardware_config.json"
    invalid_json_file.write_text("Invalid JSON")
    with pytest.raises(ConfigError):
        HardwareConfig.load_from_file(invalid_json_file)


def test_ping_finder_config_load_from_file(tmp_path: Path, ping_finder_config_data: dict[str, Any]) -> None:
    """Test loading ping finder configuration from a JSON file."""
    config_file = tmp_path / "ping_finder_config.json"
    config_file.write_text(json.dumps(ping_finder_config_data))
    config = PingFinderConfig.load_from_file(config_file)
    assert config.gain == ping_finder_config_data["gain"]
    assert config.sampling_rate == ping_finder_config_data["sampling_rate"]
    assert config.target_frequencies == ping_finder_config_data["target_frequencies"]
    assert config.output_dir == ping_finder_config_data["output_dir"]


def test_ping_finder_config_missing_file() -> None:
    """Test that attempting to load from a non-existent file raises an error."""
    with pytest.raises(FileNotFoundError):
        PingFinderConfig.load_from_file(Path("non_existent_file.json"))


def test_ping_finder_config_invalid_json(tmp_path: Path) -> None:
    """Test that attempting to load invalid JSON raises a ConfigError."""
    invalid_json_file = tmp_path / "invalid_ping_finder_config.json"
    invalid_json_file.write_text("Invalid JSON")
    with pytest.raises(ConfigError):
        PingFinderConfig.load_from_file(invalid_json_file)


def test_ping_finder_config_missing_field(ping_finder_config_data: dict[str, Any]) -> None:
    """Test that missing required fields raise a ConfigError.

    Args:
        ping_finder_config_data: Fixture providing test configuration data.
    """
    del ping_finder_config_data["gain"]
    with pytest.raises(ConfigError):
        PingFinderConfig.from_dict(ping_finder_config_data)


def test_ping_finder_config_invalid_field_type(ping_finder_config_data: dict[str, Any]) -> None:
    """Test that invalid field types raise a TypeError.

    Args:
        ping_finder_config_data: Fixture providing test configuration data.
    """
    ping_finder_config_data["gain"] = "should be a float"
    with pytest.raises(TypeError):
        PingFinderConfig.from_dict(ping_finder_config_data)
