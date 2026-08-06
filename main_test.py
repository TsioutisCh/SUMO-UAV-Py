"""
Code used for benchmark. In this code we use post-analysis to replicate UAV-based sensing of traffic. 
"""

import json
import numpy as np
import xml.etree.ElementTree as ET
import csv
import time
import traci 
from functools import wraps
from utils import Calculations
import os


timing_data = {}
call_counts = {}

def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        if func.__name__ not in timing_data:
            timing_data[func.__name__] = 0
            call_counts[func.__name__] = 0
        timing_data[func.__name__] += elapsed_time
        call_counts[func.__name__] += 1
        
        return result
    return wrapper



class UAVSimulation:
    @timing_decorator
    def __init__(self, config_file):
        self.read_config(config_file)
        self.timing_data = {}
        self.stop_flag = False
        self.calc = Calculations(self.uav_speed, self.simulation_step_length, self.yaw_speed)
        self.uav_positions_list, self.time_list, self.uav_yaw_angles_list = self.uav_path_data()
    
    @timing_decorator
    def read_config(self, config_file):
        try:
            with open(config_file, 'r') as file:
                config = json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file {config_file} not found.")
        except json.JSONDecodeError:
            raise ValueError("Configuration file is not a valid JSON.")
        
        self.UavModel = config['Uav Model']
        self.GuiOption = config['GUI Option']
        self.battery_mode = config.get('Battery Mode', False)
        self.num_UAVs = config['Number of UAVs']
        self.UavMode = config.get('Uav Mode', 'Hovering')
        
        self.mode = config.get('Input Mode', 'Offline')
        self.movement = config.get('Movement', 'Continuous')
        
        self.server_option = config.get('Remote Server', False)
        self.local_gui = config.get('Local GUI', False)
        
        self.delay_option = config.get('Delay', 0 )
        
        self.simulation_step_length = float(config['Step length (s)'])
        self.total_simulation_steps = int(config['Total time (s)'] / self.simulation_step_length)
        
        if self.UavModel == 'Mavic 2e':
            self.fov_degrees = [68.0643, 40.0455]
            self.uav_speed = 13.8
            self.yaw_speed = 10
            self.battery_life = int(1500 / self.simulation_step_length) # 25 minutes 
        elif self.UavModel == 'Mini 3 pro':
            self.fov_degrees = [66.9161, 40.2499]
            self.uav_speed = 10
            self.yaw_speed = 10
            self.battery_life = int(1800 / self.simulation_step_length) # 30 minutes 
        elif self.UavModel == 'Manual':
            self.fov_degrees = list(map(float, config['FOV (deg)']))
            self.uav_speed = float(config['UAV Speed'])
            self.yaw_speed = float(config['Yaw Speed'])
            self.battery_life = int(config.get('Battery life (s)',1800)/self.simulation_step_length) # 30 minutes if not stated 
        else:
            raise ValueError('UAV model does not exist')

        self.network_file = config['Network file']
        self.sumocfg_file = config['Sumocfg file']
        
        if not os.path.exists(self.sumocfg_file):
            raise FileNotFoundError(f"SUMO configuration file {self.sumocfg_file} not found.")
        if not os.path.exists(self.network_file):
            raise FileNotFoundError(f"SUMO configuration file {self.network_file} not found.")
    
        self.uav_data = config['uav_data']
        
        if self.server_option:
            self.uav_data = {str(i): [[0] * 5] for i in range(self.num_UAVs)}
            
        
        print(f' Number of Uavs: {self.num_UAVs} \n Uav Model: {self.UavModel} \n Uav Speed: {self.uav_speed} m/s \n Yaw Speed: {self.yaw_speed} \n Battery Life: {self.battery_life/60*self.simulation_step_length} minutes ')

    @timing_decorator
    def start_sumo(self):
        sumo_cmd = ['sumo-gui' if self.GuiOption else 'sumo', "-c", 
                    self.sumocfg_file, 
                    "--step-length", str(self.simulation_step_length), 
                    "--fcd-output", "Outputs/fcdOutput.out.xml",
                    "--tripinfo-output", "Outputs/tripinfo.out.xml",
                    "--delay","0",
                    "--quit-on-end", "True"]
        
        traci.start(sumo_cmd)

    @timing_decorator
    def run_sumo_simulation(self):
        self.start_sumo()
        for step in range(self.total_simulation_steps):
            traci.simulationStep()
        traci.close()

    @timing_decorator
    def uav_path_data(self):
        uav_positions_list = []
        time_list = []
        uav_yaw_angles_list = []
    
        for uav_id in range(self.num_UAVs):
            data_points = self.uav_data[str(uav_id)]
            
            positions = [[point[1], point[2], point[3]] for point in data_points]
            yaw_angles = [point[4] for point in data_points]
            times = [int(point[0] / self.simulation_step_length) for point in data_points]
    
            if self.movement == 'Discrete': # and self.server_updated_paths:
                # when server or script is on we do not follow the simple dynamics (rotate-hover-rotate)
                uav_positions_list.append(positions)
                time_list.append(times)
                uav_yaw_angles_list.append(yaw_angles)
            else:
                uav_positions = []
                step_times = []
                uav_yaw_angles = []
                total_steps = times[0]  # start of counting
    
                for i in range(len(positions) - 1):
                    init_pos = np.array(positions[i])
                    next_pos = np.array(positions[i + 1])
                    current_yaw_angle = yaw_angles[i]
                    target_yaw_angle = yaw_angles[i + 1]
                    next_step = times[i + 1]
    
                    move_yaw_angle = self.calc.calculate_yaw_angle(init_pos, next_pos) # angle between the two 'move' positions  
                    move_steps = self.calc.calculate_move_steps(init_pos, next_pos) # steps needed to move from A to B
                    rotate_to_move_steps = self.calc.calculate_rotate_steps(move_yaw_angle - current_yaw_angle) # steps needed to rotate before start moving
                    rotate_to_target_steps =  self.calc.calculate_rotate_steps(target_yaw_angle - move_yaw_angle) # steps needed to rotate after reaching position but not yaw angle
                        
                    while total_steps < next_step: # HOVER PARALLELS
                        uav_positions.append(init_pos)
                        step_times.append(total_steps)
                        if self.UavMode == 'Hovering' or self.UavMode == 'Sampling':
                            uav_yaw_angles.append(current_yaw_angle)
                        elif self.UavMode == 'Spinning':
                            current_yaw_angle += self.yaw_speed * self.simulation_step_length
                            uav_yaw_angles.append(current_yaw_angle)
                        total_steps += 1
                        
                        
                    if self.UavMode == 'Spinning':
                        current_yaw_angle = current_yaw_angle % 360  # fast spinning fix.
                        rotate_to_move_steps = self.calc.calculate_rotate_steps(move_yaw_angle - current_yaw_angle) 
                    
                    if np.array_equal(init_pos[:2], next_pos[:2]):
                        
                        # No horizontal movement, only change in height or yaw
                        rotate_to_target_steps = self.calc.calculate_rotate_steps(target_yaw_angle - current_yaw_angle)
                        move_steps = self.calc.calculate_move_steps(init_pos, next_pos)                  
                        
                        # Move to the new height, no yaw change
                        for step in range(move_steps):
                            position = init_pos + (next_pos - init_pos) * (step + 1) / move_steps
                            uav_positions.append(position)
                            step_times.append(total_steps)
                            uav_yaw_angles.append(current_yaw_angle)  # Keep the same yaw while changing height
                            total_steps += 1                        
                        
                        for step in range(rotate_to_target_steps):
                            yaw = current_yaw_angle + (target_yaw_angle - current_yaw_angle) * (step + 1) / rotate_to_target_steps
                            uav_positions.append(init_pos)
                            step_times.append(total_steps)
                            uav_yaw_angles.append(yaw)
                            total_steps += 1
                            
                    else:
                        for step in range(rotate_to_move_steps):
                            yaw = current_yaw_angle + (move_yaw_angle - current_yaw_angle) * (step + 1) / rotate_to_move_steps
                            uav_positions.append(init_pos)
                            step_times.append(total_steps)
                            uav_yaw_angles.append(yaw)
                            total_steps += 1
        
                        for step in range(move_steps):
                            position = init_pos + (next_pos - init_pos) * (step + 1) / move_steps
                            uav_positions.append(position)
                            step_times.append(total_steps)
                            uav_yaw_angles.append(move_yaw_angle) # uav_yaw_angles.append(current_yaw_angle)
                            total_steps += 1
        
                        if self.UavMode != 'Spinning':
                            for step in range(rotate_to_target_steps):
                                yaw = move_yaw_angle + (target_yaw_angle - move_yaw_angle) * (step + 1) / rotate_to_target_steps
                                uav_positions.append(next_pos)
                                step_times.append(total_steps)
                                uav_yaw_angles.append(yaw)
                                total_steps += 1

                final_pos = np.array(positions[-1])
                final_yaw_angle = yaw_angles[-1]
    
                # hovering at the final position until the end of simulation
                while total_steps < self.total_simulation_steps:
                    uav_positions.append(final_pos)
                    step_times.append(total_steps)
                    if self.UavMode =='Spinning':
                        final_yaw_angle += self.yaw_speed * self.simulation_step_length
                    uav_yaw_angles.append(final_yaw_angle)
                    total_steps += 1
    
                uav_positions_list.append(uav_positions)
                time_list.append(step_times)
                uav_yaw_angles_list.append(uav_yaw_angles)
    
        return uav_positions_list, time_list, uav_yaw_angles_list

    @timing_decorator
    def calculate_yaw_angle(self, start, end):
        direction = np.degrees(np.arctan2(end[1] - start[1], end[0] - start[0]))
        return 90 - direction

    @timing_decorator
    def calculate_move_steps(self, start_pos, end_pos):
        distance = np.linalg.norm(end_pos - start_pos)
        return int(distance / (self.uav_speed * self.simulation_step_length))

    @timing_decorator
    def calculate_rotate_steps(self, yaw_difference):
        return int(abs(yaw_difference) / self.yaw_speed)

    @timing_decorator
    def fov_calculation(self, fov_degrees, height):
        a, b = fov_degrees
        return np.array([height * np.tan(np.radians(a * 0.5)), height * np.tan(np.radians(b * 0.5))])

    @timing_decorator
    def calculate_fov_corners(self, uav_position, fov_size, yaw_angle):
        uav_x, uav_y, _ = uav_position
        L1, L2 = fov_size

        corners = np.array([
            [uav_x - L1 * 0.5, uav_y - L2 * 0.5],
            [uav_x + L1 * 0.5, uav_y - L2 * 0.5],
            [uav_x + L1 * 0.5, uav_y + L2 * 0.5],
            [uav_x - L1 * 0.5, uav_y + L2 * 0.5]
        ])

        theta = np.radians(yaw_angle)
        rotation_matrix = np.array([
            [np.cos(theta), -np.sin(theta)],
            [np.sin(theta), np.cos(theta)]
        ])

        rotated_corners = np.dot(corners - np.array([uav_x, uav_y]), rotation_matrix) + np.array([uav_x, uav_y])
        points = [(x, y) for x, y in rotated_corners]

        return points

    @timing_decorator
    def get_vehicles_in_fov(self, vehicles, uav_position, fov_size, yaw_angle):
        vehicles_in_view = []

        fov_corners = self.calculate_fov_corners(uav_position, fov_size, yaw_angle) 
        fov_corners = np.array(fov_corners)

        min_x, max_x = np.min(fov_corners[:, 0]), np.max(fov_corners[:, 0])
        min_y, max_y = np.min(fov_corners[:, 1]), np.max(fov_corners[:, 1]) 

        for vehicle in vehicles:
            x = float(vehicle.get('x'))
            y = float(vehicle.get('y'))
            if min_x <= x <= max_x and min_y <= y <= max_y:
                vehicles_in_view.append(vehicle)

        return vehicles_in_view

    @timing_decorator
    def process_fcd_output(self, fcd_file):
        tree = ET.parse(fcd_file)
        root = tree.getroot()

        results = []

        for timestep in root.findall('timestep'):
            time = float(timestep.get('time'))
            vehicles = timestep.findall('vehicle')

            for uav_id in range(self.num_UAVs):
                if time in self.time_list[uav_id]:
                    index = self.time_list[uav_id].index(time)
                    uav_position = self.uav_positions_list[uav_id][index]
                    yaw_angle = self.uav_yaw_angles_list[uav_id][index]
                    fov_size = self.fov_calculation(self.fov_degrees, uav_position[2])

                    vehicles_in_fov = self.get_vehicles_in_fov(vehicles, uav_position, fov_size, yaw_angle)
                    for vehicle in vehicles_in_fov:
                        results.append({
                            'time': time,
                            'uav_id': uav_id,
                            'uav_position': uav_position.tolist(),
                            'vehicle_id': vehicle.get('id'),
                            'vehicle_position': (vehicle.get('x'), vehicle.get('y')),
                            'vehicle_speed': vehicle.get('speed')
                        })
        return results

    @timing_decorator
    def write_results_to_csv(self, results, output_file='Outputs/uav_output_test.csv'):
        with open(output_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Seconds', 'UAV_ID', 'UAV_X', 'UAV_Y', 'UAV_Z', 'VehicleID', 'X', 'Y', 'Vehicle_Speed'])
            for result in results:
                writer.writerow([
                    result['time'], result['uav_id'],
                    result['uav_position'][0], result['uav_position'][1], result['uav_position'][2],
                    result['vehicle_id'], result['vehicle_position'][0], result['vehicle_position'][1],
                    result['vehicle_speed']
                ])

if __name__ == "__main__":
    t0 = time.time()
    
    sim = UAVSimulation('config.json')
    sim.run_sumo_simulation()
    results = sim.process_fcd_output('Outputs/fcdOutput.out.xml')
    sim.write_results_to_csv(results)
    
    t1 = time.time()
    print(f"Elapsed time: {t1 - t0} seconds")


    #print("Function timing data:")
    #for func_name, total_time in timing_data.items():
    #    print(f"{func_name}: {total_time:.4f} seconds, called {call_counts[func_name]} times \n")