"""Tests for configuration functionality."""
import yaml
from pathlib import Path

import pytest

from radio_telemetry_tracker_drone_fds.config import PingFinderConfig


@pytest.fixture
def ping_finder_config_data() -> dict:
    """Fixture for PingFinderConfig test data."""
    return {
        "gain": 50.0,
        "sampling_rate": 2048000,
        "center_frequency": 173043000,
        "run_num": 1,
        "enable_test_data": True,
        "ping_width_ms": 20,
        "ping_min_snr": 10,
        "ping_max_len_mult": 1.5,
        "ping_min_len_mult": 0.5,
        "target_frequencies": [173043000],
        "output_dir": "test_output",
    }


@pytest.fixture
def ping_finder_config(ping_finder_config_data: dict) -> PingFinderConfig:
    """Fixture for PingFinderConfig."""
    return PingFinderConfig.from_dict(ping_finder_config_data)


def test_ping_finder_config_from_dict(ping_finder_config_data: dict) -> None:
    """Test PingFinderConfig creation from dictionary."""
    config = PingFinderConfig.from_dict(ping_finder_config_data)
    assert config.gain == ping_finder_config_data["gain"]  # noqa: S101
    assert config.sampling_rate == ping_finder_config_data["sampling_rate"]  # noqa: S101
    assert config.target_frequencies == ping_finder_config_data["target_frequencies"]  # noqa: S101
    assert config.output_dir == ping_finder_config_data["output_dir"]  # noqa: S101


def test_ping_finder_config_from_file(tmp_path: Path, ping_finder_config_data: dict) -> None:
    """Test PingFinderConfig creation from file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dumps(ping_finder_config_data))
    config = PingFinderConfig.load_from_file(config_file)
    assert config.gain == ping_finder_config_data["gain"]  # noqa: S101
    assert config.sampling_rate == ping_finder_config_data["sampling_rate"]  # noqa: S101
    assert config.target_frequencies == ping_finder_config_data["target_frequencies"]  # noqa: S101
    assert config.output_dir == ping_finder_config_data["output_dir"]  # noqa: S101
