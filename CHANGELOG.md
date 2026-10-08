# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project intends to adopt [Semantic Versioning](https://semver.org/) starting from its first tagged release.

## [Unreleased]

### Changed
- Renamed `main_.py` → `main.py`, `_utils.py` → `utils.py`, `client_.py` → `client.py` for standard Python naming; updated all imports and script references accordingly.
- `main_test.py` now reuses `utils.Calculations` instead of carrying its own duplicate copies of the FOV/kinematics math.
- Rewrote `README.md` so its directory listing and example `config.json` match what the code actually expects.

### Fixed
- `requirements.txt` no longer lists standard-library modules (`threading`, `os`, `csv`, etc.) as pip packages — `pip install -r requirements.txt` now actually works.
- Tkinter windows no longer crash on startup on non-Windows systems when setting the `.ico` window icon.
- **Behavior change:** `main_test.py`'s `fov_calculation` was missing a factor of 2 present in `utils.Calculations.fov_calculation`, so its FOV footprint was half the size actually used by `main.py` during a live run. Benchmark output from `main_test.py` will now report more vehicles per UAV pass, matching `main.py`'s real FOV size.
- `uavpy_gui.py`'s **Run** button silently ignored any unsaved edits in the form (it launched `main.py` off the last-saved `config.json`, not the current form values) — it now always applies pending edits before launching.
- Typing an invalid value into a config field in `uavpy_gui.py` (non-numeric text, a malformed comma list) crashed the GUI with an unhandled `ValueError`; both **Apply** and **Run** now show a clear message listing which field(s) are invalid instead.

### Removed
- Dead, fully commented-out alternate `__main__` block at the bottom of `main.py`.
- `Outputs/uav_output.csv` and `BolognaScenario/{sumo_log.txt,tripinfos.xml,e1_output.xml}` are no longer version-controlled — they're regenerated on every run (see `.gitignore`).
- `update_config_run()` in `uavpy_gui.py`, a byte-for-byte duplicate of `update_config()` that was never called.

### Added
- `.gitignore` for generated simulation outputs, Python caches, and editor/OS files.
- `CONTRIBUTING.md` with dev setup and PR workflow.
- License / Python-version / repo-activity badges on the README.
- `tests/` — a `pytest` suite covering `utils.Calculations` (UAV kinematics, FOV geometry) and the new config loader (28 tests). Runs without a SUMO installation.
- `config.py` — shared, validated config loading used by both `main.py` and `main_test.py`, replacing ~60 lines of duplicated `read_config` logic in each. Missing/invalid fields now raise a clear `ConfigError` (e.g. "missing required field(s): Uav Model") instead of a bare `KeyError` or `FileNotFoundError` from deep inside the class.
- `.github/workflows/ci.yml` — runs `ruff check` and `pytest` on every push/PR to `main`, across Python 3.9/3.11/3.12.
- `pyproject.toml` — the project is now `pip install`-able (`pip install -e ".[dev]"` for a dev setup with test/lint tooling).
- "Paste X, Y from clipboard" in the in-run UAV position popup (`Local GUI` mode): copy a position in sumo-gui via right-click → *Copy cursor position*, then paste it straight into the popup instead of typing coordinates by hand. The popup also now uses five separate Time/X/Y/Z/Yaw fields instead of one hand-typed JSON tuple.
- The popup's Time field is now pre-filled with the current simulation time and falls back to it if left blank — leaving it empty means "start moving from now," instead of requiring you to know and type the exact current simulation time in seconds.
- `tests/test_path_parity.py` — a regression test that builds `main.py` and `main_test.py`'s `UAVSimulation` against the same config and asserts their computed flight paths are identical, so the kind of silent duplication-drift described below fails CI instead of shipping unnoticed.
- `uavpy_gui.py` now validates the config and checks `sumo`/`sumo-gui` is on `PATH` *before* launching a run (reusing `config.py`'s existing `load_uav_config`), showing a clear error dialog instead of letting the subprocess fail invisibly. The top-level `config.json` load on startup is wrapped the same way.
- `main.py`'s `__main__` now catches `ConfigError` on startup and `FileNotFoundError` when `sumo`/`sumo-gui` isn't on `PATH`, printing a clean message instead of a raw traceback — the safety net for direct `python main.py` usage, where `uavpy_gui.py`'s new preflight check above doesn't run.
- Each run's output CSV is now timestamped (`Outputs/uav_output_<timestamp>.csv`) with a copy of the `config.json` that produced it saved alongside (`Outputs/config_<timestamp>.json`), instead of always overwriting the same `Outputs/uav_output.csv`.

### Fixed
- Removed an unused `import time` in `client.py` (caught by `ruff`).
- `update_uav_path()` crashed (`TypeError: 'NoneType' object cannot be interpreted as an integer`) whenever a new UAV waypoint was scheduled at or after every existing waypoint's time — the normal case for a live "update position now" edit. Pre-existing bug, independent of the paste-position feature above; it just took actually exercising that code path to surface it.
- `main_test.py`'s hand-duplicated copy of `uav_path_data()` had drifted from `main.py`'s: for a waypoint requiring only a height/yaw change (no horizontal movement), it appended the UAV's *starting* position instead of the position it had already moved to, silently reporting the wrong height for the rest of that segment. `main.py` was always correct; `main_test.py` is now fixed to match, and `tests/test_path_parity.py` (above) guards against it happening again.
- `uavpy_gui.py`'s Run button tracked the running simulation via `simulation_process = threading.Thread(...).start()` — but `Thread.start()` always returns `None`, so this tracking never actually worked. Fixed to store the real thread object; Run now warns and refuses to launch a second simulation while one is already in progress, instead of silently allowing multiple concurrent `sumo`/`sumo-gui` processes.

### Removed
- Dead `self.mode`/`'Input Mode'` config field (superseded by `'Movement'`, grep-confirmed to have zero readers) from `config.py`, `main.py`, and `main_test.py`.
- A no-op guard in `main.py` (`if step % 1 == 0 and ...`) that was always true and never throttled anything despite looking like a performance check.
- `utils.py`'s commented-out old `calculate_rotate_steps_` implementation, superseded by the live version right below it.
