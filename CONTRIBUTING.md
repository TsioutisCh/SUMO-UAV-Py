# Contributing to SUMO-UAV-Py

Thanks for your interest in improving SUMO-UAV-Py.

## Setting up a dev environment

1. Install [SUMO](https://sumo.dlr.de/docs/Installing/index.html) and set `SUMO_HOME`.
2. Clone the repo and install it in editable mode with the dev extras (tests + linter):
   ```bash
   git clone https://github.com/TsioutisCh/SUMO-UAV-Py.git
   cd SUMO-UAV-Py
   pip install -e ".[dev]"
   ```
   (`pip install -r requirements.txt` still works too, if you don't need the test/lint tooling.)
3. Verify the setup by running the bundled example scenario:
   ```bash
   python main.py
   ```
   This uses `config.json` and `BolognaScenario/` as shipped in the repo.

## Workflow

- Create a branch per change: `git checkout -b <type>/<short-description>` (e.g. `fix/battery-warning-timing`).
- Keep pull requests small and focused on one change — it makes them easier to review and to revert if something goes wrong.
- Write commit messages that explain *why* a change was made, not just what changed.
- Open a pull request against `main`. CI (GitHub Actions) runs tests and linting automatically on every PR — see below for running the same checks locally first.

## Testing changes

Run the automated test suite (pure Python, no SUMO installation required):
```bash
pytest -v
```

Also run the linter, since CI checks it too:
```bash
ruff check .
```

`tests/test_calculations.py` and `tests/test_config.py` cover the UAV kinematics/FOV math and config loading/validation. If you touch either of those, add or update a test alongside your change rather than only checking it by hand.

For anything that can't be unit tested (the live SUMO/TraCI loop, the Tkinter GUIs), please still manually verify:

- The script you touched still runs end-to-end against the bundled `BolognaScenario` example.
- If you changed `main_test.py`, note in your PR description whether the benchmark output (`Outputs/uav_output_test.csv`) changed, since others may rely on its numbers.

## Reporting issues

Please include: your SUMO version, Python version, OS, the relevant section of `config.json`, and the full traceback if there's a crash.
