# Contributing to SUMO-UAV-Py

Thanks for your interest in improving SUMO-UAV-Py.

## Setting up a dev environment

1. Install [SUMO](https://sumo.dlr.de/docs/Installing/index.html) and set `SUMO_HOME`.
2. Clone the repo and install Python dependencies:
   ```bash
   git clone https://github.com/TsioutisCh/SUMO-UAV-Py.git
   cd SUMO-UAV-Py
   pip install -r requirements.txt
   ```
3. Verify the setup by running the bundled example scenario:
   ```bash
   python main.py
   ```
   This uses `config.json` and `BolognaScenario/` as shipped in the repo.

## Workflow

- Create a branch per change: `git checkout -b <type>/<short-description>` (e.g. `fix/battery-warning-timing`).
- Keep pull requests small and focused on one change — it makes them easier to review and to revert if something goes wrong.
- Write commit messages that explain *why* a change was made, not just what changed.
- Open a pull request against `main` and describe what you tested (there's no CI yet — see below).

## Testing changes

There's currently no automated test suite (that's tracked as a follow-up — see the README/roadmap). Until then, please manually verify:

- The script you touched still runs end-to-end against the bundled `BolognaScenario` example.
- If you changed anything in `utils.py` (UAV kinematics, FOV geometry), sanity-check the numbers by hand for at least one simple case (e.g. a straight-line move with no yaw change).
- If you changed `main_test.py`, note in your PR description whether the benchmark output (`Outputs/uav_output_test.csv`) changed, since others may rely on its numbers.

## Reporting issues

Please include: your SUMO version, Python version, OS, the relevant section of `config.json`, and the full traceback if there's a crash.
