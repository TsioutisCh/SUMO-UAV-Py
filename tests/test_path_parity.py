"""
Parity test between main.py and main_test.py's uav_path_data().

Both files carry their own hand-duplicated copy of this method, and they
have already drifted apart once (see CHANGELOG.md: main_test.py was
silently appending init_pos instead of next_pos for height/yaw-only
waypoints). This test builds both UAVSimulation classes against the same
config and asserts their computed flight paths are identical, so a future
drift fails here instead of shipping a silently-wrong benchmark.
"""

import json

import numpy as np

import main
import main_test


def _write_config(tmp_path, uav_data):
    """Write a minimal config.json (plus dummy network/sumocfg files) with
    the given uav_data, and return its path as a string."""
    network_file = tmp_path / "network.net.xml"
    sumocfg_file = tmp_path / "run.sumocfg"
    network_file.write_text("<net/>")
    sumocfg_file.write_text("<configuration/>")

    config = {
        "Uav Model": "Mavic 2e",
        "GUI Option": False,
        "Number of UAVs": 1,
        "Step length (s)": 1,
        "Total time (s)": 20,
        "Network file": str(network_file),
        "Sumocfg file": str(sumocfg_file),
        "uav_data": {"0": uav_data},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    return str(config_path)


def _assert_identical_paths(sim_a, sim_b):
    """Compare uav_positions_list/time_list/uav_yaw_angles_list for UAV 0
    across both simulation objects."""
    positions_a = np.array(sim_a.uav_positions_list[0])
    positions_b = np.array(sim_b.uav_positions_list[0])
    assert positions_a.shape == positions_b.shape
    assert np.array_equal(positions_a, positions_b)

    assert sim_a.time_list[0] == sim_b.time_list[0]

    yaw_a = np.array(sim_a.uav_yaw_angles_list[0])
    yaw_b = np.array(sim_b.uav_yaw_angles_list[0])
    assert np.array_equal(yaw_a, yaw_b)


class TestPathParity:
    def test_height_and_yaw_only_change(self, tmp_path):
        # No horizontal movement, only a height + yaw change - the exact
        # case that exposed the main_test.py drift bug.
        uav_data = [[0, 100, 100, 0, 0], [10, 100, 100, 50, 90]]
        config_path = _write_config(tmp_path, uav_data)

        sim_main = main.UAVSimulation(config_path)
        sim_bench = main_test.UAVSimulation(config_path)

        _assert_identical_paths(sim_main, sim_bench)

    def test_horizontal_move(self, tmp_path):
        # A normal horizontal move with a yaw change, to confirm parity
        # isn't limited to the height/yaw-only branch.
        uav_data = [[0, 0, 0, 100, 0], [10, 200, 300, 100, 0]]
        config_path = _write_config(tmp_path, uav_data)

        sim_main = main.UAVSimulation(config_path)
        sim_bench = main_test.UAVSimulation(config_path)

        _assert_identical_paths(sim_main, sim_bench)

    def test_yaw_wraparound_takes_the_short_way(self, tmp_path):
        # A yaw change that crosses the 0/360 boundary (10deg -> 350deg):
        # the raw difference is +340 (the long way around), but the
        # shortest path is only -20. Both the number of rotate steps AND
        # the per-step interpolated yaw values must reflect the short path,
        # not an over-rotation through the long one (see D-005).
        uav_data = [[0, 100, 100, 50, 10], [10, 100, 100, 50, 350]]
        config_path = _write_config(tmp_path, uav_data)

        sim_main = main.UAVSimulation(config_path)
        sim_bench = main_test.UAVSimulation(config_path)

        _assert_identical_paths(sim_main, sim_bench)

        # Not just identical to each other - actually correct. No
        # intermediate yaw value should ever jump by more than yaw_speed
        # degrees (circularly - e.g. -10 and 350 are 0 degrees apart, not
        # 360) in a single step, which an over-rotation through the long
        # way around would violate.
        yaws = np.array(sim_main.uav_yaw_angles_list[0])
        raw_deltas = np.diff(yaws)
        circular_deltas = np.abs((raw_deltas + 180) % 360 - 180)
        assert circular_deltas.max() <= sim_main.yaw_speed * sim_main.simulation_step_length + 1e-6
