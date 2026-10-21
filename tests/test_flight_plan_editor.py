"""
Tests for flight_plan_editor's pure validation/sort logic - the functions
the editor's row-save path uses. Deliberately NOT testing the
FlightPlanEditor Tkinter class itself here: these tests must run without a
display (CI is headless), and importing tkinter/matplotlib (as
flight_plan_editor.py does at module level) is already proven CI-safe by
tests/test_path_parity.py's `import main` - only *instantiating* a real
Tk/Toplevel needs a display, and these tests never do that.
"""

import pytest

from flight_plan_editor import (
    find_duplicate_time,
    find_malformed_waypoint,
    parse_waypoint_fields,
    sorted_by_time,
)


class TestParseWaypointFields:
    def test_parses_valid_numbers(self):
        assert parse_waypoint_fields("10", "1.5", "-2.25", "100", "90") == [10.0, 1.5, -2.25, 100.0, 90.0]

    def test_rejects_non_numeric_time(self):
        with pytest.raises(ValueError):
            parse_waypoint_fields("soon", "1", "2", "3", "4")

    def test_rejects_non_numeric_x(self):
        with pytest.raises(ValueError):
            parse_waypoint_fields("1", "abc", "2", "3", "4")

    def test_rejects_empty_field(self):
        with pytest.raises(ValueError):
            parse_waypoint_fields("1", "", "2", "3", "4")


class TestFindDuplicateTime:
    def test_no_duplicate_returns_none(self):
        waypoints = [[0, 0, 0, 0, 0], [10, 1, 1, 1, 1]]
        assert find_duplicate_time(waypoints, 20) is None

    def test_finds_exact_duplicate(self):
        waypoints = [[0, 0, 0, 0, 0], [10, 1, 1, 1, 1]]
        assert find_duplicate_time(waypoints, 10) == 1

    def test_ignores_the_row_being_edited(self):
        waypoints = [[0, 0, 0, 0, 0], [10, 1, 1, 1, 1]]
        # Editing row 1 and keeping its own time (10) must not flag itself.
        assert find_duplicate_time(waypoints, 10, ignore_index=1) is None

    def test_still_catches_a_different_rows_duplicate_while_editing(self):
        waypoints = [[0, 0, 0, 0, 0], [10, 1, 1, 1, 1]]
        # Editing row 1 to take row 0's time (0) must still be caught.
        assert find_duplicate_time(waypoints, 0, ignore_index=1) == 0


class TestSortedByTime:
    def test_sorts_ascending(self):
        waypoints = [[50, 1, 1, 1, 1], [0, 0, 0, 0, 0], [25, 2, 2, 2, 2]]
        result = sorted_by_time(waypoints)
        assert [wp[0] for wp in result] == [0, 25, 50]

    def test_does_not_mutate_the_input_list(self):
        waypoints = [[50, 1, 1, 1, 1], [0, 0, 0, 0, 0]]
        original_order = [wp[0] for wp in waypoints]
        sorted_by_time(waypoints)
        assert [wp[0] for wp in waypoints] == original_order

    def test_already_sorted_is_unchanged(self):
        waypoints = [[0, 0, 0, 0, 0], [10, 1, 1, 1, 1]]
        assert sorted_by_time(waypoints) == waypoints


class TestFindMalformedWaypoint:
    def test_well_formed_data_returns_none(self):
        uav_data = {"0": [[0, 1, 2, 3, 4]], "1": [[0, 1, 2, 3, 4], [10, 5, 6, 7, 8]]}
        assert find_malformed_waypoint(uav_data, num_uavs=2) is None

    def test_too_few_fields_is_caught(self):
        uav_data = {"0": [[0, 1, 2, 3]]}  # missing yaw
        assert find_malformed_waypoint(uav_data, num_uavs=1) == (0, [0, 1, 2, 3])

    def test_too_many_fields_is_caught(self):
        uav_data = {"0": [[0, 1, 2, 3, 4, 5]]}
        assert find_malformed_waypoint(uav_data, num_uavs=1) == (0, [0, 1, 2, 3, 4, 5])

    def test_non_numeric_field_is_caught(self):
        uav_data = {"0": [[0, 1, 2, 3, "north"]]}
        assert find_malformed_waypoint(uav_data, num_uavs=1) == (0, [0, 1, 2, 3, "north"])

    def test_only_checks_uavs_within_num_uavs_range(self):
        # A malformed waypoint on a UAV id outside range(num_uavs) is never
        # displayed/used by the editor, so it's not this function's job to
        # flag it.
        uav_data = {"0": [[0, 1, 2, 3, 4]], "5": [[0, 1, 2]]}
        assert find_malformed_waypoint(uav_data, num_uavs=1) is None

    def test_identifies_which_uav_and_waypoint(self):
        uav_data = {"0": [[0, 1, 2, 3, 4]], "1": [[0, 1, 2, 3, 4], [10, 1, 2]]}
        assert find_malformed_waypoint(uav_data, num_uavs=2) == (1, [10, 1, 2])
