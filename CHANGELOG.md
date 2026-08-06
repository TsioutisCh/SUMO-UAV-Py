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
