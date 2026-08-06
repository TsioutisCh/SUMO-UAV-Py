import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
import json
import subprocess
import sys
import threading

# Load config.json
config_file_path = 'config.json'  # Adjust the path if necessary
with open(config_file_path, 'r') as f:
    config_data = json.load(f)

# Track the running simulation process or thread
simulation_process = None

# Update config.json
def update_config(show_confirmation=True):
    with open(config_file_path, 'w') as f:
        json.dump(config_data, f, indent=4)
    if show_confirmation:
        messagebox.showinfo("Info", "Configuration Applied Successfully")

# Read every GUI field and validate it against config_data's existing type
# for that key. Returns (new_values, errors) without touching config_data -
# callers decide what to do once they know whether validation passed.
def _collect_entry_values():
    new_values = {}
    errors = []
    for key, entry in entries.items():
        if isinstance(entry, ttk.Combobox):
            value = entry.get()
        elif isinstance(entry, tk.IntVar):  # Checkbutton uses IntVar (1 for True, 0 for False)
            value = bool(entry.get())
        else:
            value = entry.get()

        if key not in config_data:
            continue

        current = config_data[key]
        try:
            if isinstance(current, list):
                new_values[key] = list(map(float, value.split(',')))
            elif isinstance(current, bool):
                new_values[key] = value
            elif isinstance(current, int):
                new_values[key] = int(value)
            elif isinstance(current, float):
                new_values[key] = float(value)
            else:
                new_values[key] = value
        except ValueError:
            errors.append(f"{key}: '{value}' is not a valid value")

    return new_values, errors

# Run the main.py file in a separate thread (avoid blocking the main sim thread)
def run_main_exp():
    global simulation_process

    new_values, errors = _collect_entry_values()
    if errors:
        messagebox.showerror(
            "Invalid Input",
            "Please fix the following field(s) before running:\n\n" + "\n".join(errors)
        )
        return

    # Always apply pending edits before running, so Run never launches a
    # stale config just because Apply wasn't clicked first.
    config_data.update(new_values)
    update_config(show_confirmation=False)

    script_path = 'main.py'  # Adjust the path if necessary
    simulation_process = threading.Thread(target=subprocess.run, args=([sys.executable, script_path],)).start()

# Change/update config.json
def apply_changes():
    new_values, errors = _collect_entry_values()
    if errors:
        messagebox.showerror(
            "Invalid Input",
            "Please fix the following field(s):\n\n" + "\n".join(errors)
        )
        return
    config_data.update(new_values)
    update_config()

# Close pop-upstop SUMO
def cancel():    
    root.destroy()

# Show or hide fields based on "Uav Model" selection
def toggle_manual_fields(*args):
    uav_model = entries["Uav Model"].get()
    if uav_model == "Manual":
        for field in manual_fields:
            field[0].grid()
            field[1].grid()
    else:
        for field in manual_fields:
            field[0].grid_remove()
            field[1].grid_remove()

# Create main window
root = tk.Tk()
root.title("UAV Configuration")

# Set the window icon
icon_path = "images/kiosLogo.ico"  # Make sure the .ico file is in the correct path
try:
    root.iconbitmap(icon_path)
except tk.TclError:
    pass  # .ico icons are only supported on Windows

# Set the window size and make it non-resizable
root.geometry("400x700")
root.resizable(False, False)

# Apply a dark theme
root.configure(bg='#2E2E2E')

style = ttk.Style()
style.theme_use('alt')  # Using 'alt' as a base theme for customization

# Configure the style to match a dark theme
style.configure('TButton', font=('Helvetica', 12), padding=6, background='#2E2E2E', foreground='#FFFFFF')
style.configure('TLabel', font=('Helvetica', 12), padding=5, background='#2E2E2E', foreground='#FFFFFF')
style.configure('TEntry', font=('Helvetica', 12), padding=5, fieldbackground='#3C3F41', foreground='#FFFFFF')

# Create a frame to hold the grid of labels and entries
frame = tk.Frame(root, bg='#2E2E2E')
frame.pack(pady=20)

# Predefined options for specific fields
options = {
    "Uav Model": ["Mavic 2e", "Mini 3 pro", "Manual"],
    "Movement": ["Continuous", "Discrete"],  # Renamed "Input Mode" to "Movement"
    "Uav Mode": ["Hovering", "Spinning", "Sampling"]
}

# Fields that should be displayed as checkboxes
checkbox_fields = ["Battery Mode", "GUI Option"]  # Correctly handling checkboxes like "Battery Mode" and "GUI Option"

# Fields that only appear when "Uav Model" is "Manual"
manual_fields = []

# Create fields for each configurable entry in config.json
entries = {}
row = 0

# Add "Online" label and options for Remote Server and Local GUI above "Battery Mode"
online_label = tk.Label(frame, text="Online", bg='#2E2E2E', fg='#FFFFFF')
online_label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)

# Checkbuttons for Remote Server and Local GUI
remote_server_var = tk.IntVar(value=config_data.get("Remote Server", False))
local_gui_var = tk.IntVar(value=config_data.get("Local GUI", False))

remote_server_cb = tk.Checkbutton(frame, text="Remote Server", variable=remote_server_var, bg='#2E2E2E', fg='#FFFFFF', selectcolor='#3C3F41')
remote_server_cb.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
entries["Remote Server"] = remote_server_var

local_gui_cb = tk.Checkbutton(frame, text="Local GUI", variable=local_gui_var, bg='#2E2E2E', fg='#FFFFFF', selectcolor='#3C3F41')
local_gui_cb.grid(row=row+1, column=1, sticky=tk.W, padx=5, pady=5)
entries["Local GUI"] = local_gui_var

row += 2  # Increment the row counter for other entries to follow

for key, value in config_data.items():
    # Skip "Remote Server" and "Local GUI" here to avoid duplicate checkboxes
    if key == "Remote Server" or key == "Local GUI":
        continue

    if key in options:  # Use a Combobox for fields with predefined options
        label = tk.Label(frame, text=key, bg='#2E2E2E', fg='#FFFFFF')
        label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        entry = ttk.Combobox(frame, values=options[key], state="readonly")
        entry.set(value)
        entry.grid(row=row, column=1, padx=5, pady=5)
        entries[key] = entry
        if key == "Uav Model":
            entry.bind("<<ComboboxSelected>>", toggle_manual_fields)
    elif key in checkbox_fields:  # Use a Checkbutton for boolean fields
        label = tk.Label(frame, text=key, bg='#2E2E2E', fg='#FFFFFF')
        label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        var = tk.IntVar(value=int(value))
        entry = tk.Checkbutton(frame, variable=var, bg='#2E2E2E', fg='#FFFFFF', activebackground='#2E2E2E', selectcolor='#3C3F41')
        entry.grid(row=row, column=1, padx=5, pady=5)
        entries[key] = var
    elif isinstance(value, (str, int, float)):
        if key in ["Network file", "Sumocfg file"]:
            label = tk.Label(frame, text=key, bg='#2E2E2E', fg='#FFFFFF')
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            # Create a frame to hold the entry and button
            entry_frame = tk.Frame(frame, bg='#2E2E2E')
            entry_frame.grid(row=row, column=1, padx=5, pady=5)
            entry = tk.Entry(entry_frame, bg='#3C3F41', fg='#FFFFFF', insertbackground='#FFFFFF', width=18)
            entry.pack(side=tk.LEFT)
            entry.insert(0, str(value))
            # Define the browse function
            def browse_file(e=entry):
                file_path = filedialog.askopenfilename()
                if file_path:
                    e.delete(0, tk.END)
                    e.insert(0, file_path)
            # Use a Unicode arrow symbol as the button text
            browse_button = tk.Button(entry_frame, text='\u2026', command=browse_file, bg='#4CAF50', fg='#FFFFFF', activebackground='#45A049',height=1 ,width=2)
            browse_button.pack(side=tk.LEFT, padx=(5, 0))
            entries[key] = entry
        else:
            label = tk.Label(frame, text=key, bg='#2E2E2E', fg='#FFFFFF')
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            entry = tk.Entry(frame, bg='#3C3F41', fg='#FFFFFF', insertbackground='#FFFFFF')
            entry.insert(0, str(value))
            entry.grid(row=row, column=1, padx=5, pady=5)
            entries[key] = entry
            if key in ["Battery life (s)", "FOV (deg)", "UAV Speed", "Yaw Speed"]:
                manual_fields.append((label, entry))
    elif isinstance(value, list):
        label = tk.Label(frame, text=key, bg='#2E2E2E', fg='#FFFFFF')
        label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        entry = tk.Entry(frame, bg='#3C3F41', fg='#FFFFFF', insertbackground='#FFFFFF')
        entry.insert(0, ', '.join(map(str, value)))
        entry.grid(row=row, column=1, padx=5, pady=5)
        entries[key] = entry
        if key == "FOV (deg)":  # Ensure FOV (deg) is included in the manual_fields
            manual_fields.append((label, entry))
    row += 1

# Run, Apply, and Cancel buttons
button_frame = tk.Frame(root, bg='#2E2E2E')
button_frame.pack(pady=20)

run_button = tk.Button(button_frame, text="Run", command=run_main_exp, bg='#4CAF50', fg='#FFFFFF', activebackground='#45A049')
run_button.grid(row=0, column=0, padx=10)

apply_button = tk.Button(button_frame, text="Apply", command=apply_changes, bg='#4CAF50', fg='#FFFFFF', activebackground='#45A049')
apply_button.grid(row=0, column=1, padx=10)

cancel_button = tk.Button(button_frame, text="Cancel", command=cancel, bg='#F44336', fg='#FFFFFF', activebackground='#E57373')
cancel_button.grid(row=0, column=2, padx=10)

# Initially hide manual fields if "Uav Model" is not "Manual"
toggle_manual_fields()

# make appear in front
root.attributes('-topmost', True)

# Start the Tkinter loop
root.mainloop()
