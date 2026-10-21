"""
Flight-plan editor: a combined map + table view of each UAV's planned
waypoints, opened from uavpy_gui.py's "Flight Plan..." button.

Edits only touch an in-memory working copy of uav_data; the real
config_data dict (and config.json on disk) are only updated when the user
clicks Apply. Closing without Apply leaves config_data completely
untouched - persisting to config.json is still uavpy_gui.py's own job via
its existing update_config()/apply_changes() machinery.
"""

import copy
import json
import os
import re
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import main
from config import ConfigError
from network_geometry import NetworkGeometryError, parse_network_geometry

# Matches a (possibly negative, possibly decimal) number - same pattern as
# main.py's live-popup "paste X,Y from clipboard" feature.
_COORD_PATTERN = re.compile(r'-?\d+\.?\d*')

_BG = '#2E2E2E'
_FIELD_BG = '#3C3F41'
_FG = '#FFFFFF'

# Matches the Helvetica convention already established by main.py's live
# popup (the closest existing precedent - a secondary Toplevel, not the
# main config form's slightly larger uavpy_gui.py convention).
_FONT = ('Helvetica', 11)
_FONT_SMALL = ('Helvetica', 9)
_FONT_BUTTON = ('Helvetica', 10)

# Plot colors chosen so the matplotlib figure reads as part of the same
# dark theme as the surrounding Tkinter widgets, instead of a plain white
# rectangle dropped into a dark window.
_PLOT_GRID = '#555555'
_PLOT_NETWORK = '#8A8A8A'
_PLOT_MARKER = '#FFD54F'

_UAV_COLORS = [
    'tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple',
    'tab:brown', 'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan',
]


def parse_waypoint_fields(time_text, x_text, y_text, z_text, yaw_text):
    """Parse 5 raw text field values into a [time, x, y, z, yaw] waypoint.

    Raises ValueError with a human-readable message if any field isn't a
    valid number - pure, Tkinter-free, so it's unit-testable directly.
    """
    try:
        return [
            float(time_text), float(x_text), float(y_text),
            float(z_text), float(yaw_text),
        ]
    except ValueError:
        raise ValueError("Time, X, Y, Z and Yaw must all be numbers.")


def find_duplicate_time(waypoints, new_time, ignore_index=None):
    """Return the index of another waypoint sharing new_time exactly, or None.

    ignore_index excludes the waypoint currently being edited, so editing a
    row's other fields while keeping its own time unchanged doesn't flag
    itself as a duplicate.
    """
    for i, wp in enumerate(waypoints):
        if i != ignore_index and wp[0] == new_time:
            return i
    return None


def sorted_by_time(waypoints):
    """uav_path_data() assumes each UAV's waypoints are in ascending time
    order - this is the single choke point that guarantees it."""
    return sorted(waypoints, key=lambda wp: wp[0])


def find_malformed_waypoint(uav_data, num_uavs):
    """Return (uav_id, waypoint) for the first waypoint that isn't exactly
    5 numeric values, or None if every UAV's waypoints are well-formed.

    Catches hand-edited config.json data that reaches this editor without
    having gone through its own 5-field save path (which always produces a
    valid shape) - without this, a malformed waypoint crashes deep inside
    the unpacking/plotting code instead of showing a clear message.
    """
    for uav_id in range(num_uavs):
        for wp in uav_data.get(str(uav_id), []):
            if len(wp) != 5:
                return uav_id, wp
            try:
                for v in wp:
                    float(v)
            except (TypeError, ValueError):
                return uav_id, wp
    return None


def open_flight_plan_editor(parent, config_data):
    """Open the Flight Plan editor against the live config_data dict.

    Edits are only committed into config_data when the user clicks Apply;
    closing without Apply leaves config_data untouched.
    """
    FlightPlanEditor(parent, config_data)


class FlightPlanEditor(tk.Toplevel):
    def __init__(self, parent, config_data):
        super().__init__(parent)
        self.config_data = config_data
        self.num_uavs = int(config_data.get('Number of UAVs', 0))
        self.working_uav_data = copy.deepcopy(config_data.get('uav_data', {}))
        self.selected_uav = 0
        self._selected_row_index = None
        self._pending_map_click_target = None
        self._scratch_path = None

        self.title("Flight Plan Editor")
        self.configure(bg=_BG)
        self.geometry("1050x650")

        if config_data.get('Remote Server', False):
            messagebox.showinfo(
                "Flight Plan Editor",
                "Flight Plan editing only applies when 'Remote Server' is "
                "off - in Remote Server mode, waypoints are supplied "
                "dynamically by the remote client, not a static schedule.",
                parent=self,
            )
            self.destroy()
            return

        if self.num_uavs <= 0:
            messagebox.showinfo(
                "Flight Plan Editor", "Number of UAVs is 0 - nothing to plan.",
                parent=self,
            )
            self.destroy()
            return

        for uav_id in range(self.num_uavs):
            key = str(uav_id)
            if not self.working_uav_data.get(key):
                self.working_uav_data[key] = [[0.0, 0.0, 0.0, 0.0, 0.0]]

        # DECISION plan-2026-10-21T101227-fd3e32c6/D-003: validate waypoint
        # shape up front and refuse to open, rather than let a malformed
        # hand-edited waypoint crash later inside unpacking/plotting code
        # with a raw traceback. See decisions.md D-003.
        malformed = find_malformed_waypoint(self.working_uav_data, self.num_uavs)
        if malformed is not None:
            bad_uav_id, bad_wp = malformed
            messagebox.showerror(
                "Flight Plan Editor",
                f"UAV {bad_uav_id} has a malformed waypoint ({bad_wp!r}) - "
                "expected exactly 5 numeric values (time, x, y, z, yaw). "
                "Fix it in config.json directly, then reopen this editor.",
                parent=self,
            )
            self.destroy()
            return

        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_table()
        self._redraw()

    # -- layout --------------------------------------------------------

    def _build_widgets(self):
        style = ttk.Style(self)
        style.theme_use('alt')
        style.configure('TButton', background=_BG, foreground=_FG, font=_FONT_BUTTON)
        style.configure('TLabel', background=_BG, foreground=_FG, font=_FONT)
        style.configure('TCombobox', fieldbackground=_FIELD_BG, foreground=_FG, font=_FONT)
        style.configure('Treeview', background=_FIELD_BG, fieldbackground=_FIELD_BG, foreground=_FG, font=_FONT_SMALL, rowheight=22)
        style.configure('Treeview.Heading', background=_BG, foreground=_FG, font=_FONT_BUTTON)

        main_frame = tk.Frame(self, bg=_BG)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        map_frame = tk.Frame(main_frame, bg=_BG)
        map_frame.pack(side='left', fill='both', expand=True)

        self.figure = Figure(figsize=(6, 6), facecolor=_BG)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=map_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.canvas.mpl_connect('button_press_event', self._on_map_click)

        side_frame = tk.Frame(main_frame, bg=_BG, width=380)
        side_frame.pack(side='right', fill='y', padx=(10, 0))

        selector_frame = tk.Frame(side_frame, bg=_BG)
        selector_frame.pack(fill='x', pady=(0, 5))
        tk.Label(selector_frame, text="UAV:", bg=_BG, fg=_FG, font=_FONT).pack(side='left')
        self.uav_selector = ttk.Combobox(
            selector_frame, state='readonly', font=_FONT,
            values=[str(i) for i in range(self.num_uavs)],
        )
        self.uav_selector.current(0)
        self.uav_selector.pack(side='left', padx=5)
        self.uav_selector.bind('<<ComboboxSelected>>', self._on_select_uav)

        columns = ('time', 'x', 'y', 'z', 'yaw')
        self.table = ttk.Treeview(side_frame, columns=columns, show='headings', height=8, selectmode='browse')
        for col, label in zip(columns, ('Time', 'X', 'Y', 'Z', 'Yaw')):
            self.table.heading(col, text=label)
            self.table.column(col, width=60, anchor='center')
        self.table.pack(fill='x', pady=(0, 10))
        self.table.bind('<<TreeviewSelect>>', self._on_select_row)

        row_buttons = tk.Frame(side_frame, bg=_BG)
        row_buttons.pack(fill='x', pady=(0, 10))
        tk.Button(row_buttons, text="New Row", command=self._clear_row_form, font=_FONT_BUTTON).pack(side='left', padx=2)
        tk.Button(row_buttons, text="Delete Selected", command=self._delete_row, font=_FONT_BUTTON).pack(side='left', padx=2)

        form_frame = tk.Frame(side_frame, bg=_BG)
        form_frame.pack(fill='x')

        def add_field(row, label_text):
            tk.Label(form_frame, text=label_text, bg=_BG, fg=_FG, font=_FONT).grid(
                row=row, column=0, sticky='w', padx=5, pady=3
            )
            entry = tk.Entry(form_frame, bg=_FIELD_BG, fg=_FG, insertbackground=_FG, font=_FONT, width=14)
            entry.grid(row=row, column=1, padx=5, pady=3)
            return entry

        self.time_entry = add_field(0, "Time (s):")
        self.x_entry = add_field(1, "X:")
        self.y_entry = add_field(2, "Y:")
        self.z_entry = add_field(3, "Z / altitude:")
        self.yaw_entry = add_field(4, "Yaw (deg):")

        self.error_label = tk.Label(
            side_frame, text="", bg=_BG, fg='#FF6B6B', font=_FONT_SMALL, wraplength=360, justify='left',
        )
        self.error_label.pack(fill='x', pady=(0, 5))

        coord_buttons = tk.Frame(side_frame, bg=_BG)
        coord_buttons.pack(fill='x', pady=(0, 5))
        tk.Button(coord_buttons, text="Paste X,Y from clipboard", command=self._paste_position, font=_FONT_BUTTON).pack(side='left', padx=2)
        tk.Button(coord_buttons, text="Set X,Y from map click", command=self._arm_map_click, font=_FONT_BUTTON).pack(side='left', padx=2)

        tk.Button(side_frame, text="Save Row", command=self._save_row, bg='#4CAF50', fg=_FG, font=_FONT).pack(fill='x', pady=(5, 10))

        bottom_buttons = tk.Frame(side_frame, bg=_BG)
        bottom_buttons.pack(fill='x', side='bottom', pady=10)
        tk.Button(bottom_buttons, text="Apply", command=self._apply, bg='#4CAF50', fg=_FG, font=_FONT).pack(side='left', padx=5)
        tk.Button(bottom_buttons, text="Cancel", command=self._on_close, bg='#F44336', fg=_FG, font=_FONT).pack(side='left', padx=5)

    # -- table / row editing --------------------------------------------

    def _current_waypoints(self):
        return self.working_uav_data[str(self.selected_uav)]

    def _refresh_table(self):
        self.table.delete(*self.table.get_children())
        for i, wp in enumerate(self._current_waypoints()):
            self.table.insert('', 'end', iid=str(i), values=[f"{v:.2f}" for v in wp])
        self._clear_row_form()

    def _on_select_uav(self, event=None):
        self.selected_uav = int(self.uav_selector.get())
        self._refresh_table()
        self._redraw()

    def _on_select_row(self, event=None):
        selection = self.table.selection()
        if not selection:
            return
        index = int(selection[0])
        self._selected_row_index = index
        self._disarm_map_click()
        self._fill_row_form(self._current_waypoints()[index])

    def _fill_row_form(self, wp):
        for entry, value in zip(
            (self.time_entry, self.x_entry, self.y_entry, self.z_entry, self.yaw_entry), wp
        ):
            entry.delete(0, tk.END)
            entry.insert(0, f"{value:.2f}")
        self.error_label.config(text="")

    def _clear_row_form(self):
        self._selected_row_index = None
        self._disarm_map_click()
        for entry in (self.time_entry, self.x_entry, self.y_entry, self.z_entry, self.yaw_entry):
            entry.delete(0, tk.END)
        self.error_label.config(text="")

    def _disarm_map_click(self):
        # Switching which row/UAV is being edited must cancel a pending
        # "set from map click" arm - otherwise a later click silently fills
        # coordinates for whatever is now selected, not what was armed.
        self._pending_map_click_target = None

    def _paste_position(self):
        try:
            clipboard_text = self.clipboard_get()
        except tk.TclError:
            self.error_label.config(text="Clipboard is empty or unavailable.")
            return
        numbers = _COORD_PATTERN.findall(clipboard_text)
        if len(numbers) < 2:
            self.error_label.config(
                text="Couldn't find an X,Y pair in the clipboard "
                     f"('{clipboard_text.strip()}'). In sumo-gui, right-click "
                     "the map and choose 'Copy cursor position' first."
            )
            return
        self.x_entry.delete(0, tk.END)
        self.x_entry.insert(0, numbers[0])
        self.y_entry.delete(0, tk.END)
        self.y_entry.insert(0, numbers[1])
        self.error_label.config(text="")

    def _arm_map_click(self):
        self._pending_map_click_target = (self.x_entry, self.y_entry)
        self.error_label.config(text="Click anywhere on the map to set X,Y...", fg='#FFD54F')

    def _on_map_click(self, event):
        if self._pending_map_click_target is None:
            return
        if event.xdata is None or event.ydata is None:
            return
        x_entry, y_entry = self._pending_map_click_target
        x_entry.delete(0, tk.END)
        x_entry.insert(0, f"{event.xdata:.2f}")
        y_entry.delete(0, tk.END)
        y_entry.insert(0, f"{event.ydata:.2f}")
        self._pending_map_click_target = None
        self.error_label.config(text="", fg='#FF6B6B')

    def _save_row(self):
        try:
            new_wp = parse_waypoint_fields(
                self.time_entry.get(), self.x_entry.get(), self.y_entry.get(),
                self.z_entry.get(), self.yaw_entry.get(),
            )
        except ValueError as e:
            self.error_label.config(text=str(e))
            return

        waypoints = self._current_waypoints()
        dup = find_duplicate_time(waypoints, new_wp[0], ignore_index=self._selected_row_index)
        if dup is not None:
            self.error_label.config(text=f"Another waypoint already has time={new_wp[0]:g}s.")
            return

        if self._selected_row_index is not None:
            waypoints[self._selected_row_index] = new_wp
        else:
            waypoints.append(new_wp)
        self.working_uav_data[str(self.selected_uav)] = sorted_by_time(waypoints)

        self._refresh_table()
        self._redraw()

    def _delete_row(self):
        selection = self.table.selection()
        if not selection:
            return
        waypoints = self._current_waypoints()
        if len(waypoints) <= 1:
            self.error_label.config(text="A UAV needs at least one waypoint - can't delete the last one.")
            return
        del waypoints[int(selection[0])]
        self._refresh_table()
        self._redraw()

    # -- preview recompute + redraw -------------------------------------

    # DECISION plan-2026-10-21T101227-fd3e32c6/D-001: recompute via a scratch
    # file + a fresh main.UAVSimulation construction, not a dict-accepting
    # constructor refactor and not a duplicate of uav_path_data()'s logic.
    # Rejected simpler-looking alternative: call main.UAVSimulation directly
    # against the REAL config.json path - rejected because it would require
    # writing in-progress, unapplied edits to the real file, violating "no
    # write until Apply". See decisions.md D-001 for the full comparison.
    def _recompute_paths(self):
        """Recompute every UAV's interpolated path via a scratch config file
        + a fresh main.UAVSimulation construction (decisions.md D-001) -
        reuses the exact, already-tested path-computation code instead of
        duplicating or re-deriving it. Returns None (and shows an error) if
        the current in-progress edits don't yet form a loadable config.
        """
        # DECISION plan-2026-10-21T101227-fd3e32c6/D-003: wrap the scratch
        # file creation/write in try/except too, not just the UAVSimulation
        # construction below - a disk-full/permissions error here must not
        # raise uncaught. See decisions.md D-003.
        try:
            if self._scratch_path is None:
                fd, self._scratch_path = tempfile.mkstemp(suffix='.json', prefix='flight_plan_preview_')
                os.close(fd)

            scratch_config = dict(self.config_data)
            scratch_config['uav_data'] = self.working_uav_data
            with open(self._scratch_path, 'w', encoding='utf-8') as f:
                json.dump(scratch_config, f)
        except OSError as e:
            self.error_label.config(text=f"Can't write preview scratch file: {e}")
            return None

        try:
            sim = main.UAVSimulation(self._scratch_path)
        except ConfigError as e:
            self.error_label.config(text=f"Can't preview: {e}")
            return None
        except Exception as e:
            # Defensive boundary: uav_path_data() isn't code this editor
            # modifies, so guard against any edge case it hits that this
            # editor's own validation (min 1 waypoint, no duplicate times,
            # sorted-by-time) doesn't already rule out.
            self.error_label.config(text=f"Can't preview: {e}")
            return None
        return sim.uav_positions_list

    def _redraw(self):
        self.axes.clear()
        # axes.clear() resets facecolor/spines/ticks to matplotlib defaults,
        # so the dark theme has to be re-applied every redraw, not just once
        # at construction time.
        self.axes.set_facecolor(_FIELD_BG)
        for spine in self.axes.spines.values():
            spine.set_color(_FG)
        self.axes.tick_params(colors=_FG, labelsize=9)
        self.axes.grid(True, color=_PLOT_GRID, linestyle='--', linewidth=0.5, alpha=0.6)

        try:
            geometry = parse_network_geometry(self.config_data.get('Network file', ''))
        except NetworkGeometryError:
            geometry = None

        if geometry is not None:
            for segment in geometry.segments:
                xs = [p[0] for p in segment]
                ys = [p[1] for p in segment]
                self.axes.plot(xs, ys, color=_PLOT_NETWORK, linewidth=0.6, zorder=1)
            self.axes.set_xlim(geometry.bounds[0], geometry.bounds[2])
            self.axes.set_ylim(geometry.bounds[1], geometry.bounds[3])

        positions_list = self._recompute_paths()
        if positions_list is not None:
            for uav_id in range(self.num_uavs):
                positions = positions_list[uav_id]
                xs = [p[0] for p in positions]
                ys = [p[1] for p in positions]
                color = _UAV_COLORS[uav_id % len(_UAV_COLORS)]
                is_selected = uav_id == self.selected_uav
                self.axes.plot(
                    xs, ys, color=color, linewidth=2.2 if is_selected else 0.9,
                    alpha=1.0 if is_selected else 0.45, zorder=2,
                )

        # Label only the selected UAV's own waypoints with their times, to
        # avoid an unreadable wall of overlapping labels with many UAVs.
        for t, x, y, z, yaw in self._current_waypoints():
            self.axes.plot(
                x, y, 'o', color=_PLOT_MARKER, markersize=7,
                markeredgecolor=_FIELD_BG, markeredgewidth=1.0, zorder=3,
            )
            self.axes.annotate(
                f"t={t:g}s", (x, y), textcoords='offset points', xytext=(6, 6),
                fontsize=8, color=_FG,
            )

        self.axes.set_title(
            f"UAV {self.selected_uav} flight plan", color=_FG, fontsize=12, fontweight='bold'
        )
        self.axes.set_xlabel("X (m)", color=_FG, fontsize=9)
        self.axes.set_ylabel("Y (m)", color=_FG, fontsize=9)
        self.axes.set_aspect('equal', adjustable='datalim')
        self.figure.tight_layout()
        self.canvas.draw_idle()

    # -- apply / cancel ---------------------------------------------------

    def _apply(self):
        self.config_data['uav_data'] = self.working_uav_data
        self._cleanup_scratch_file()
        self.destroy()

    def _on_close(self):
        self._cleanup_scratch_file()
        self.destroy()

    def _cleanup_scratch_file(self):
        if self._scratch_path is not None and os.path.exists(self._scratch_path):
            try:
                os.remove(self._scratch_path)
            except OSError:
                pass
            self._scratch_path = None
