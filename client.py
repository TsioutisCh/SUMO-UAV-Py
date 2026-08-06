import socket
import time
import json
import numpy as np

def generate_waypoints(init_time=500, uav_x = 1150, uav_y = 1385, uav_z = 300, num_points=700):
    """
    Parameters:
    init_time (int): Initial time for the UAV path.
    uav_x (float): Initial x-coordinate.
    uav_y (float): Initial y-coordinate.
    z (float): Constant z-coordinate (altitude).
    yaw (float): Initial yaw angle.
    num_points (int): Number of waypoints to generate.
    s=radius power parameter

    Returns:
    list: A list of waypoints, each containing [time, x, y, z, yaw].
    """
    waypoints = []
    x = np.zeros(num_points)
    y = np.zeros(num_points)
    z = np.zeros(num_points)
    yaw = np.zeros(num_points)
    
    for i in range(1, num_points): 
        x[i] = uav_x + (i**1.1) * np.cos(np.radians(i))
        y[i] = uav_y + (i) * np.sin(np.radians(i))
        yaw[i] = (np.degrees(np.arctan2(x[i] - x[i-1], y[i] - y[i-1])) + 360) % 360
        if z[i-1] < uav_z:
            z[i] = z[i-1] + 5
        else:
            z[i] = uav_z # + (np.random.randint(3) - 1)
        

    times = np.arange(init_time, init_time + num_points, 1)
    
    for i in range(num_points):
        waypoint = [int(times[i]), float(x[i]), float(y[i]), float(z[i]), float(yaw[i])]
        waypoints.append(waypoint)
    
    return waypoints

def start_client(waypoints):
    
    """
    Establish a TCP connection to a server and send a series of waypoints.
    
    This function connects to a server running on 'localhost' at port 1024,
    sends each waypoint in the `waypoints` list to the server, and prints
    the server's response. Each waypoint is formatted and sent as a JSON string.
    
    Parameters:
    waypoints (list): A list of waypoints, where each waypoint is a list in the format [time, x, y, z, yaw].
    
    Notes:
    - The server must be running and listening on 'localhost' at port 1024 for the connection to succeed.
    - The function handles common socket connection errors and ensures the socket is closed properly.
    - Uncomment the `time.sleep(1)` line if you want to send waypoints with a delay.
    
    """


    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 1024)) #TCP connection
    print("Connected to the server")
    
    try:
        for waypoint in waypoints:
            try:
                message = f"0: {json.dumps(waypoint)}"  
                client_socket.sendall(message.encode())
                data = client_socket.recv(1024)
                print(f"Sent: {message}")
                print(f"Received from server: {data.decode()}")
                #time.sleep(1)  # if i want to send a waypoint every second
            except (ConnectionResetError, ConnectionAbortedError) as e:
                print(f"Connection error: {e}")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                break
    finally:
        client_socket.close()
        print("Client socket closed")

if __name__ == "__main__":
    waypoints = generate_waypoints()
    start_client(waypoints)

