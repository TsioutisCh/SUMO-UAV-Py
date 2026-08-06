"""
Tests for config.py - loading and validating config.json.

Covers the cases that used to fail with a raw KeyError/FileNotFoundError
deep inside main.py, to make sure they now fail with a clear ConfigError
message instead.
"""

import json

import pytest

from config import ConfigError, load_uav_config


def _write_config(tmp_path, overrides=None, remove=None):
    """Write a minimal-but-valid config.json (plus a dummy network/sumocfg
    file next to it) into tmp_path, and return its path as a string."""
    network_file = tmp_path / "network.net.xml"
    sumocfg_file = tmp_path / "run.sumocfg"
    network_file.write_text("<net/>")
    sumocfg_file.write_text("<configuration/>")

    config = {
        "Uav Model": "Mavic 2e",
        "GUI Option": False,
        "Number of UAVs": 1,
        "Step length (s)": 1,
        "Total time (s)": 100,
        "Network file": str(network_file),
        "Sumocfg file": str(sumocfg_file),
        "uav_data": {"0": [[0, 0, 0, 0, 0]]},
    }
    if overrides:
        config.update(overrides)
    if remove:
        for key in remove:
            config.pop(key, None)

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    return str(config_path)


class TestValidConfigs:
    def test_loads_a_known_preset(self, tmp_path):
        cfg = load_uav_config(_write_config(tmp_path))
        assert cfg["UavModel"] == "Mavic 2e"
        assert cfg["uav_speed"] == 13.8
        assert cfg["fov_degrees"] == [68.0643, 40.0455]
        assert cfg["total_simulation_steps"] == 100

    def test_battery_life_defaults_from_preset(self, tmp_path):
        cfg = load_uav_config(_write_config(tmp_path))
        # Mavic 2e defaults to 1500s battery life, at 1s steps -> 1500 steps.
        assert cfg["battery_life"] == 1500

    def test_explicit_battery_life_overrides_preset(self, tmp_path):
        path = _write_config(tmp_path, overrides={"Battery life (s)": 300})
        cfg = load_uav_config(path)
        assert cfg["battery_life"] == 300

    def test_manual_model_reads_custom_fields(self, tmp_path):
        path = _write_config(tmp_path, overrides={
            "Uav Model": "Manual",
            "FOV (deg)": [50, 30],
            "UAV Speed": 7,
            "Yaw Speed": 12,
        })
        cfg = load_uav_config(path)
        assert cfg["fov_degrees"] == [50.0, 30.0]
        assert cfg["uav_speed"] == 7.0
        assert cfg["yaw_speed"] == 12.0

    def test_remote_server_generates_placeholder_uav_data(self, tmp_path):
        path = _write_config(tmp_path, overrides={
            "Remote Server": True,
            "Number of UAVs": 3,
        })
        cfg = load_uav_config(path)
        assert set(cfg["uav_data"].keys()) == {"0", "1", "2"}
        assert cfg["uav_data"]["0"] == [[0, 0, 0, 0, 0]]

    def test_defaults_are_applied_for_optional_fields(self, tmp_path):
        cfg = load_uav_config(_write_config(tmp_path))
        assert cfg["UavMode"] == "Hovering"
        assert cfg["movement"] == "Continuous"
        assert cfg["battery_mode"] is False
        assert cfg["server_option"] is False
        assert cfg["local_gui"] is False
        assert cfg["delay_option"] == 0


class TestInvalidConfigs:
    def test_missing_file_raises_config_error(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_uav_config(str(tmp_path / "does_not_exist.json"))

    def test_malformed_json_raises_config_error(self, tmp_path):
        bad_path = tmp_path / "config.json"
        bad_path.write_text("{not valid json")
        with pytest.raises(ConfigError, match="not valid JSON"):
            load_uav_config(str(bad_path))

    def test_missing_required_key_lists_it_by_name(self, tmp_path):
        path = _write_config(tmp_path, remove=["Uav Model"])
        with pytest.raises(ConfigError, match="Uav Model"):
            load_uav_config(path)

    def test_unknown_uav_model_lists_valid_choices(self, tmp_path):
        path = _write_config(tmp_path, overrides={"Uav Model": "Quadrocopter X"})
        with pytest.raises(ConfigError, match="Mavic 2e"):
            load_uav_config(path)

    def test_manual_model_missing_fields_is_reported(self, tmp_path):
        path = _write_config(tmp_path, overrides={"Uav Model": "Manual"})
        with pytest.raises(ConfigError, match="FOV \\(deg\\)"):
            load_uav_config(path)

    def test_missing_network_file_is_reported(self, tmp_path):
        path = _write_config(tmp_path, overrides={
            "Network file": str(tmp_path / "nope.net.xml"),
        })
        with pytest.raises(ConfigError, match="network file"):
            load_uav_config(path)
