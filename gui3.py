import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import threading
import time
import os
import cv2
from ultralytics import YOLO

T_MIN = 8
T_MAX = 130
EMERGENCY_BONUS = 10
LOST_TIME_PER_PHASE = 4  # seconds

lanes = ["North", "West", "East", "South"]
vehicle_classes = [2, 3, 5, 7]  # Car, Bus, Truck, Motorcycle
model = YOLO("yolov8n.pt")


class TrafficSimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Traffic Signal Simulator")
        self.root.geometry("800x700")

        bg_image = Image.open("icbc-intersection.png")
        bg_image = bg_image.resize((1200, 1000), Image.Resampling.LANCZOS)
        self.bg_photo = ImageTk.PhotoImage(bg_image)
        background_label = tk.Label(self.root, image=self.bg_photo)
        background_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.vehicle_entries = {}
        self.emergency_vars = {}
        self.red_lights = {}
        self.green_lights = {}
        self.timer_labels = {}
        self.image_paths = {}

        self.running = False
        self.build_gui()

    def build_gui(self):
        intersection = tk.Frame(self.root)
        intersection.pack(expand=True)

        self.create_lane_box(intersection, "North", 0, 1)
        self.create_lane_box(intersection, "West", 1, 0)

        center_frame = tk.Frame(intersection, width=100, height=100)
        center_frame.grid(row=1, column=1, padx=10, pady=10)
        center_frame.grid_propagate(False)

        self.countdown_label = ttk.Label(center_frame, text="Countdown", font=("Helvetica", 16))
        self.countdown_label.pack()

        self.start_button = ttk.Button(center_frame, text="Start Simulation", command=self.start_simulation)
        self.start_button.pack()

        self.output_text = tk.Text(center_frame, width=40, height=10)
        self.output_text.pack()

        self.create_lane_box(intersection, "East", 1, 2)
        self.create_lane_box(intersection, "South", 2, 1)

    def create_lane_box(self, parent, lane, row, col):
        frame = ttk.LabelFrame(parent, text=f"{lane} Lane", padding=10)
        frame.grid(row=row, column=col, padx=10, pady=10)

        ttk.Label(frame, text="Vehicle Count: ").pack()
        entry = ttk.Entry(frame)
        entry.insert(0, "0")
        entry.pack()
        self.vehicle_entries[lane] = entry

        var = tk.BooleanVar()
        chk = ttk.Checkbutton(frame, text="Emergency Vehicle", variable=var)
        chk.pack()
        self.emergency_vars[lane] = var

        btn = ttk.Button(frame, text="Upload Image", command=lambda l=lane: self.upload_image(l))
        btn.pack()

        canvas = tk.Canvas(frame, width=40, height=80)
        red = canvas.create_oval(10, 10, 30, 30, fill="grey")
        green = canvas.create_oval(10, 50, 30, 70, fill="grey")
        canvas.pack()
        self.red_lights[lane] = (canvas, red)
        self.green_lights[lane] = (canvas, green)

        timer = ttk.Label(frame, text="Timer: 0s")
        timer.pack()
        self.timer_labels[lane] = timer

    def upload_image(self, lane):
        filepath = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if filepath:
            self.image_paths[lane] = filepath
            self.vehicle_entries[lane].delete(0, tk.END)
            count = self.detect_vehicles(filepath)
            self.vehicle_entries[lane].insert(0, str(count))
            self.output_text.insert(tk.END, f"{lane} Lane -> Vehicles detected: {count}\n")

    def detect_vehicles(self, image_path):
        image = cv2.imread(image_path)
        if image is None:
            return 0
        results = model(image)
        vehicle_count = 0
        for r in results:
            for box in r.boxes:
                if int(box.cls) in vehicle_classes:
                    vehicle_count += 1
        return vehicle_count

    def allocate_green_time(self, vehicle_counts, emergency_lanes):
        total_vehicles = sum(vehicle_counts.values()) or 1  
        base_cycle = 120  
        total_lost_time = LOST_TIME_PER_PHASE * len(lanes)
        effective_green_time = base_cycle - total_lost_time

        green_times = {}
        for lane in lanes:
            count = vehicle_counts.get(lane, 0)
            proportion = count / total_vehicles
            g_i = proportion * effective_green_time

            if lane in emergency_lanes:
                g_i += EMERGENCY_BONUS

            g_i = min(max(T_MIN, round(g_i)), T_MAX)
            green_times[lane] = g_i

        sorted_lanes = sorted(
            lanes,
            key=lambda l: (-int(l in emergency_lanes), -vehicle_counts.get(l, 0))
        )

        return green_times, sorted_lanes

    def update_lights(self, active_lane, countdown):
        self.countdown_label.config(text=f"{active_lane} - {countdown}s")

        for lane in lanes:
            canvas_r, red = self.red_lights[lane]
            canvas_g, green = self.green_lights[lane]

            if lane == active_lane:
                canvas_r.itemconfig(red, fill="grey")
                canvas_g.itemconfig(green, fill="green")
                self.timer_labels[lane].config(text=f"Timer: {countdown}s")
            else:
                canvas_r.itemconfig(red, fill="red")
                canvas_g.itemconfig(green, fill="grey")
                self.timer_labels[lane].config(text="Timer: 0s")

    def run_simulation(self):
        while self.running:
            vehicle_counts = {}
            emergency_lanes = []

            for lane in lanes:
                try:
                    count = int(self.vehicle_entries[lane].get())
                except ValueError:
                    count = 0
                vehicle_counts[lane] = max(count, 0)

                if self.emergency_vars[lane].get():
                    emergency_lanes.append(lane)

            green_times, priority_lanes = self.allocate_green_time(vehicle_counts, emergency_lanes)

            for lane in priority_lanes:
                green_time = int(green_times[lane])
                for t in range(green_time, 0, -1):
                    if not self.running:
                        return
                    self.update_lights(lane, t)
                    time.sleep(1)

                self.vehicle_entries[lane].delete(0, tk.END)
                self.vehicle_entries[lane].insert(0, "0")
                self.emergency_vars[lane].set(False)

            self.running = False
            self.start_button.config(state="normal")

    def start_simulation(self):
        if not self.running:
            self.running = True
            self.sim_thread = threading.Thread(target=self.run_simulation)
            self.sim_thread.start()
            self.start_button.config(state="disabled")

    def stop_simulation(self):
        self.running = False
        if hasattr(self, 'sim_thread'):
            self.sim_thread.join()


if __name__ == "__main__":
    root = tk.Tk()
    app = TrafficSimulatorGUI(root)

    def on_closing():
        app.stop_simulation()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
