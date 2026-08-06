"""
Tests for utils.Calculations - the UAV kinematics and FOV geometry math.

These are pure functions (no SUMO/TraCI connection needed), so they're a
cheap, fast way to catch regressions like the missing factor-of-2 bug that
was previously found in a duplicate copy of fov_calculation.
"""

import numpy as np
import pytest

from utils import Calculations


@pytest.fixture
def calc():
    return Calculations(uav_speed=10, simulation_step_length=1, yaw_speed=10)


class TestCalculateYawAngle:
    def test_facing_north_is_zero(self, calc):
        yaw = calc.calculate_yaw_angle(np.array([0, 0, 0]), np.array([0, 1, 0]))
        assert yaw == pytest.approx(0.0)

    def test_facing_east_is_ninety(self, calc):
        yaw = calc.calculate_yaw_angle(np.array([0, 0, 0]), np.array([1, 0, 0]))
        assert yaw == pytest.approx(90.0)

    def test_facing_south_is_180(self, calc):
        yaw = calc.calculate_yaw_angle(np.array([0, 0, 0]), np.array([0, -1, 0]))
        assert yaw == pytest.approx(180.0)


class TestCalculateMoveSteps:
    def test_exact_division(self, calc):
        # 100m at 10 m/s, 1s steps -> 10 steps
        steps = calc.calculate_move_steps(np.array([0, 0, 0]), np.array([100, 0, 0]))
        assert steps == 10

    def test_rounds_down(self, calc):
        # 105m at 10 m/s -> 10.5 steps, truncated to 10
        steps = calc.calculate_move_steps(np.array([0, 0, 0]), np.array([105, 0, 0]))
        assert steps == 10


class TestCalculateRotateSteps:
    def test_zero_difference_still_takes_one_step(self, calc):
        # By design: even a 0-degree "rotation" costs a minimum of 1 step.
        assert calc.calculate_rotate_steps(0) == 1

    def test_simple_positive_difference(self, calc):
        # 45 degrees at 10 deg/s-step -> ceil(45/10) = 5
        assert calc.calculate_rotate_steps(45) == 5

    def test_takes_the_shorter_direction_over_180(self, calc):
        # 200 degrees normalizes to the 160-degree turn the other way
        assert calc.calculate_rotate_steps(200) == 16

    def test_negative_difference(self, calc):
        # -30 degrees normalizes to a 30-degree turn -> ceil(30/10) = 3
        assert calc.calculate_rotate_steps(-30) == 3

    def test_full_turn_still_takes_one_step(self, calc):
        assert calc.calculate_rotate_steps(360) == 1


class TestFovCalculation:
    def test_90_degree_fov_at_10m_height(self, calc):
        # tan(45deg) == 1, so a 90deg FOV footprint is exactly 2x the height.
        size = calc.fov_calculation([90, 90], 10)
        assert size[0] == pytest.approx(20.0)
        assert size[1] == pytest.approx(20.0)

    def test_footprint_scales_linearly_with_height(self, calc):
        size_10 = calc.fov_calculation([68.0643, 40.0455], 10)
        size_100 = calc.fov_calculation([68.0643, 40.0455], 100)
        assert size_100[0] == pytest.approx(size_10[0] * 10)
        assert size_100[1] == pytest.approx(size_10[1] * 10)


class TestCalculateFovCorners:
    def test_axis_aligned_rectangle_at_zero_yaw(self, calc):
        corners = calc.calculate_fov_corners([0, 0, 100], [10, 20], 0)
        expected = [[-5, -10], [5, -10], [5, 10], [-5, 10]]
        assert np.allclose(corners, expected)

    def test_rotating_90_degrees_swaps_width_and_height_axes(self, calc):
        corners = calc.calculate_fov_corners([0, 0, 100], [10, 20], 90)
        # After a 90-degree rotation, the footprint's extent along x
        # should match the original height extent (20), and vice versa.
        corners = np.array(corners)
        x_extent = corners[:, 0].max() - corners[:, 0].min()
        y_extent = corners[:, 1].max() - corners[:, 1].min()
        assert x_extent == pytest.approx(20.0)
        assert y_extent == pytest.approx(10.0)

    def test_corners_are_centered_on_uav_position(self, calc):
        corners = np.array(calc.calculate_fov_corners([50, 30, 100], [10, 20], 37))
        centroid = corners.mean(axis=0)
        assert centroid == pytest.approx([50, 30], abs=1e-6)


class TestGetVehiclesInFov:
    def test_only_vehicles_inside_the_footprint_are_returned(self, calc):
        # A vehicle at (0, 0) is inside a 10x10 box centered on the origin;
        # a vehicle at (100, 100) is far outside it.
        subscribed_data = {
            'inside_veh': {66: (2.0, -3.0), 64: 12.5},   # VAR_POSITION=66, VAR_SPEED=64
            'outside_veh': {66: (100.0, 100.0), 64: 5.0},
        }
        result = calc.get_vehicles_in_fov(
            subscribed_data, uav_position=[0, 0, 100], fov_size=[10, 10], yaw_angle=0
        )
        assert result['vehicle_ids'] == ['inside_veh']
        assert result['positions'] == [(2.0, -3.0)]
        assert result['speeds'] == [12.5]
