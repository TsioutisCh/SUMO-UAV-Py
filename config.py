"""
Loading and validation for config.json.

Shared by main.py (live simulation) and main_test.py (post-processing
benchmark) so config handling only lives in one place.
"""

import os
import ujson as json


class ConfigError(Exception):
    """Raised when config.json is missing, malformed, or invalid."""


# Built-in flight envelopes. "Manual" instead reads FOV (deg)/UAV Speed/Yaw Speed
# straight out of config.json.
UAV_PRESETS = {
    'Mavic 2e': {
        'fov_degrees': [68.0643, 40.0455],
        'uav_speed': 13.8,
        'yaw_speed': 10,
        'default_battery_life_s': 1500,  # 25 minutes
    },
    'Mini 3 pro': {
        'fov_degrees': [66.9161, 40.2499],
        'uav_speed': 10,
        'yaw_speed': 10,
        'default_battery_life_s': 1800,  # 30 minutes
    },
}

REQUIRED_KEYS = [
    'Uav Model', 'GUI Option', 'Number of UAVs', 'Step length (s)',
    'Total time (s)', 'Network file', 'Sumocfg file', 'uav_data',
]

MANUAL_REQUIRED_KEYS = ['FOV (deg)', 'UAV Speed', 'Yaw Speed']


def load_uav_config(config_file):
    """Load, validate, and resolve config.json into a plain dict.

    Raises ConfigError with a clear message on anything invalid, instead of
    letting a raw KeyError/FileNotFoundError surface from deep in the code.
    """
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        raise ConfigError(f"Configuration file {config_file} not found.")
    except ValueError as e:
        # ujson raises ValueError (not json.JSONDecodeError) on bad JSON.
        raise ConfigError(f"Configuration file {config_file} is not valid JSON: {e}")

    missing = [key for key in REQUIRED_KEYS if key not in config]
    if missing:
        raise ConfigError(
            f"Configuration file {config_file} is missing required field(s): "
            f"{', '.join(missing)}"
        )

    uav_model = config['Uav Model']
    if uav_model in UAV_PRESETS:
        preset = UAV_PRESETS[uav_model]
        fov_degrees = preset['fov_degrees']
        uav_speed = preset['uav_speed']
        yaw_speed = preset['yaw_speed']
        battery_life_s = config.get('Battery life (s)', preset['default_battery_life_s'])
    elif uav_model == 'Manual':
        missing_manual = [key for key in MANUAL_REQUIRED_KEYS if key not in config]
        if missing_manual:
            raise ConfigError(
                f"Uav Model is 'Manual' but missing required field(s): "
                f"{', '.join(missing_manual)}"
            )
        fov_degrees = list(map(float, config['FOV (deg)']))
        uav_speed = float(config['UAV Speed'])
        yaw_speed = float(config['Yaw Speed'])
        battery_life_s = config.get('Battery life (s)', 1800)  # 30 minutes if not stated
    else:
        raise ConfigError(
            f"Unknown Uav Model '{uav_model}'. Choose one of: "
            f"{', '.join(list(UAV_PRESETS) + ['Manual'])}."
        )

    network_file = config['Network file']
    sumocfg_file = config['Sumocfg file']
    if not os.path.exists(sumocfg_file):
        raise ConfigError(f"SUMO configuration file {sumocfg_file} not found.")
    if not os.path.exists(network_file):
        raise ConfigError(f"SUMO network file {network_file} not found.")

    step_length = float(config['Step length (s)'])
    num_uavs = config['Number of UAVs']
    server_option = config.get('Remote Server', False)

    return {
        'UavModel': uav_model,
        'GuiOption': config['GUI Option'],
        'battery_mode': config.get('Battery Mode', False),
        'num_UAVs': num_uavs,
        'UavMode': config.get('Uav Mode', 'Hovering'),
        'mode': config.get('Input Mode', 'Offline'),
        'movement': config.get('Movement', 'Continuous'),
        'server_option': server_option,
        'local_gui': config.get('Local GUI', False),
        'delay_option': config.get('Delay', 0),
        'simulation_step_length': step_length,
        'total_simulation_steps': int(config['Total time (s)'] / step_length),
        'fov_degrees': fov_degrees,
        'uav_speed': uav_speed,
        'yaw_speed': yaw_speed,
        'battery_life': int(battery_life_s / step_length),
        'network_file': network_file,
        'sumocfg_file': sumocfg_file,
        'uav_data': (
            {str(i): [[0] * 5] for i in range(num_uavs)}
            if server_option else config['uav_data']
        ),
    }
