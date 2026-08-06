import numpy as np
import traci
from functools import wraps
import time


timing_data_utils = {}
call_counts_utils = {}

def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        if func.__name__ not in timing_data_utils:
            timing_data_utils[func.__name__] = 0
            call_counts_utils[func.__name__] = 0
        timing_data_utils[func.__name__] += elapsed_time
        call_counts_utils[func.__name__] += 1
        
        return result

    return wrapper

class Calculations:

    def __init__(self, uav_speed, simulation_step_length, yaw_speed):
        self.uav_speed = uav_speed
        self.simulation_step_length = simulation_step_length
        self.yaw_speed = yaw_speed
        
    @timing_decorator    
    def calculate_yaw_angle(self, start, end): # We ignore the pitch angle here.
        direction = np.degrees(np.arctan2(end[1] - start[1], end[0] - start[0]))
        return 90 - direction
    
    @timing_decorator
    def calculate_move_steps(self, start_pos, end_pos):
        distance = np.linalg.norm(end_pos - start_pos)
        return int(distance / (self.uav_speed * self.simulation_step_length))
    
    # @timing_decorator
    # def calculate_rotate_steps_(self, yaw_difference):
    #     yaw_difference = (yaw_difference + 360) % 360  # to choose the correct rotation angle
    #     yaw_difference = abs(yaw_difference)
    #     return int((yaw_difference / (self.yaw_speed * self.simulation_step_length)))  
    
    @timing_decorator
    def calculate_rotate_steps(self, yaw_difference):
        # Normalize the yaw difference to the minimal angle [0, 180]
        yaw_difference = (yaw_difference + 360) % 360
        if yaw_difference > 180:
            yaw_difference = 360 - yaw_difference
        step_angle = self.yaw_speed * self.simulation_step_length
        steps = int(np.ceil(yaw_difference / step_angle))
        return steps if steps > 0 else 1
    
    @timing_decorator
    def calculate_fov_corners(self, uav_position, fov_size, yaw_angle):
        uav_x, uav_y, _ = uav_position
        L1, L2 = fov_size

        corners = np.array([
            [uav_x - L1 * 0.5 , uav_y - L2 * 0.5],
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

        return rotated_corners.tolist()
    
    @timing_decorator
    def fov_calculation(self, fov_degrees, height):
        a, b = fov_degrees
        x = 2 * height * np.tan(np.radians(a * 0.5))
        y = 2 * height * np.tan(np.radians(b * 0.5))
        return np.array([x, y]) 
    
    @timing_decorator
    def get_vehicles_in_fov(self, subscribed_data, uav_position, fov_size, yaw_angle, return_info=('positions', 'speeds')):
        vehicles_in_view = []
        positions_in_view = []
        speeds_in_view = []

        fov_corners = self.calculate_fov_corners(uav_position, fov_size, yaw_angle) 
        fov_corners = np.array(fov_corners)

        min_x, max_x = np.min(fov_corners[:, 0]), np.max(fov_corners[:, 0])
        min_y, max_y = np.min(fov_corners[:, 1]), np.max(fov_corners[:, 1]) 

        for vehicle_id, data in subscribed_data.items():
            position = data[traci.constants.VAR_POSITION]
            if min_x <= position[0] <= max_x and min_y <= position[1] <= max_y:
                vehicles_in_view.append(vehicle_id)
                if 'positions' in return_info:
                    positions_in_view.append(position)
                if 'speeds' in return_info:
                    speeds_in_view.append(data[traci.constants.VAR_SPEED])

        result = {'vehicle_ids': vehicles_in_view}
        if 'positions' in return_info:
            result['positions'] = positions_in_view
        if 'speeds' in return_info:
            result['speeds'] = speeds_in_view

        return result
     
    @timing_decorator
    def update_fov_polygon(self,uav_position, fov_size, yaw_angle, polygon_id, border_polygon_id):
        points = self.calculate_fov_corners(uav_position, fov_size, yaw_angle)
        border_points = points + [points[0]]
        traci.polygon.setShape(polygon_id, points)
        traci.polygon.setShape(border_polygon_id, border_points)
        
        
    @timing_decorator
    def add_fov_polygon(self,uav_position, fov_size, yaw_angle, polygon_id, border_polygon_id):
        points = self.calculate_fov_corners(uav_position, fov_size, yaw_angle)
        border_points = points + [points[0]]
        traci.polygon.add(polygon_id, points, (160, 160, 255, 128), layer=-1, fill=True)  
        traci.polygon.add(border_polygon_id, border_points, (200, 200, 255, 255), layer=0, fill=False, lineWidth=1)  
          
    @timing_decorator  
    def remove_fov_polygon(self, polygon_id, border_polygon_id):
        try:
            traci.polygon.remove(polygon_id)
            traci.polygon.remove(border_polygon_id)
        except traci.TraCIException: # as e:
            pass #logger.error(f"Error removing polygons: {e}")
    
    def remove_poi(self, polygon_id):
        try:
            traci.poi.remove(polygon_id)
        except traci.TraCIException: #as e:
            pass #logger.error(f"Error removing POI: {e}")

    @timing_decorator
    def add_poi(self, poi_id, position, yaw_angle, icon_path):
        x, y, _ = position
        traci.poi.add(poi_id, x, y, (255, 255, 255, 255), layer=999, angle=yaw_angle, imgFile=icon_path)
        
    @timing_decorator
    def update_poi(self, poi_id, position, yaw_angle):
        x, y, z = position        
        traci.poi.setPosition(poi_id, x, y)
        traci.poi.setAngle(poi_id, yaw_angle)
        size = z * 0.25
        traci.poi.setHeight(poi_id, size)
        traci.poi.setWidth(poi_id, size)

