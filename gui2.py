import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import threading
import time
import os
import cv2
from ultralytics import YOLO

class ModernTrafficGUI:
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("Traffic Signal Simulator")
            
            # Initialize essential variables first
            self.running = False
            self.sim_thread = None
            
            # Initialize screen dimensions and scaling
            self.screen_width = root.winfo_screenwidth()
            self.screen_height = root.winfo_screenheight()
            
            # Set minimum window size
            self.root.minsize(800, 600)
            
            # Better scaling factors
            self.width_scale = min(self.screen_width / 1280, 1.5)
            self.height_scale = min(self.screen_height / 800, 1.5)
            
            # Configure grid
            self.root.grid_rowconfigure(0, weight=1)
            self.root.grid_columnconfigure(0, weight=1)
            
            self.root.geometry(f"{self.screen_width}x{self.screen_height}")
            
            # Add protocol for window closing after variables are initialized
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Adjust scale factors for better proportions
            self.width_scale = self.screen_width / 1280
            self.height_scale = self.screen_height / 800
            
            # Initialize other variables
            self.lanes = ["North", "West", "East", "South"]
            self.lane_boxes = {}
            self.vehicle_counts = {}
            self.emergency_vars = {}
            self.image_paths = {}
            self.red_lights = {}
            self.green_lights = {}
            
            self.root.state('zoomed')
            self.root.configure(bg='#FFFFFF')
            
            # Initialize YOLO model
            self.model = YOLO("yolov8n.pt")
            self.vehicle_classes = [2, 3, 5, 7]
            
            self.build_gui()
            
        except Exception as e:
            print(f"Initialization error: {e}")
            self.root.destroy()

    def on_closing(self):
        """Clean up resources before closing"""
        try:
            if self.running:
                self.running = False
                if hasattr(self, 'sim_thread') and self.sim_thread.is_alive():
                    self.sim_thread.join(timeout=1.0)
            self.root.destroy()
        except Exception as e:
            print(f"Closing error: {e}")
            self.root.destroy()

    def build_gui(self):
        # Adjust lane box positions for better spacing
        self.create_lane_box("North", self.screen_width * 0.35, self.screen_height * 0.05)
        self.create_lane_box("South", self.screen_width * 0.35, self.screen_height * 0.55)
        self.create_lane_box("East", self.screen_width * 0.65, self.screen_height * 0.3)
        self.create_lane_box("West", self.screen_width * 0.05, self.screen_height * 0.3)
        
        self.create_central_controls()
        self.create_terminal()

    def create_lane_box(self, lane, x, y):
        # Adjust frame size ratios
        frame = tk.Frame(
            self.root, 
            bg='#D9D9D9', 
            width=int(350 * self.width_scale),
            height=int(250 * self.height_scale)
        )
        frame.place(x=int(x), y=int(y))
        frame.pack_propagate(False)
        
        # Adjust font sizes and padding
        font_size = max(int(14 * self.width_scale), 12)
        padding = int(10 * self.width_scale)
        
        select_btn = tk.Button(
            frame,
            text="Select Image",
            font=('Arial Hebrew', font_size),
            bg='#B1B1B1',
            command=lambda: self.upload_image(lane)
        )
        select_btn.place(relx=0.1, rely=0.1, relwidth=0.8, relheight=0.15)
        
        tk.Label(
            frame,
            text="Vehicle Count:",
            font=('Inter', font_size),
            bg='#D9D9D9'
        ).place(relx=0.1, rely=0.3, relwidth=0.5)
        
        count_entry = tk.Entry(
            frame,
            font=('Inter', font_size),
            width=5,
            bd=4
        )
        count_entry.place(relx=0.65, rely=0.3, relwidth=0.25)
        self.vehicle_counts[lane] = count_entry
        
        var = tk.BooleanVar()
        tk.Checkbutton(
            frame,
            text="Emergency Vehicle",
            font=('Inter', font_size),
            variable=var,
            bg='#D9D9D9'
        ).place(relx=0.1, rely=0.5, relwidth=0.8)
        self.emergency_vars[lane] = var
        
        self.create_traffic_light(frame, lane)

    def create_traffic_light(self, parent, lane):
        light_frame = tk.Frame(
            parent,
            bg='#B1B1B1',
            bd=3,
            relief='solid'
        )
        light_frame.place(relx=0.3, rely=0.6, relwidth=0.4, relheight=0.3)
        
        # Adjust light sizes
        light_size = int(40 * self.width_scale)
        padding = int(5 * self.width_scale)
        
        red_light = tk.Canvas(
            light_frame,
            bg='#B1B1B1',
            highlightthickness=0,
            width=light_size,
            height=light_size
        )
        red_light.place(relx=0.25, rely=0.1)
        red_light.create_oval(padding, padding, 
                            light_size-padding, light_size-padding, 
                            fill='#EB0000')
        
        green_light = tk.Canvas(
            light_frame,
            bg='#B1B1B1',
            highlightthickness=0,
            width=light_size,
            height=light_size
        )
        green_light.place(relx=0.25, rely=0.55)
        green_light.create_oval(padding, padding, 
                              light_size-padding, light_size-padding, 
                              fill='grey')
        
        self.red_lights[lane] = (red_light, red_light.find_all()[0])
        self.green_lights[lane] = (green_light, green_light.find_all()[0])

    def create_central_controls(self):
        # Center the timer and controls
        self.timer_frame = tk.Frame(
            self.root,
            bg='#D9D9D9',
            bd=4,
            relief='solid'
        )
        self.timer_frame.place(
            relx=0.45,
            rely=0.3,
            relwidth=0.1,
            relheight=0.15
        )
        
        self.timer_label = tk.Label(
            self.timer_frame,
            text="00:00",
            font=('Arial Hebrew', max(int(28 * self.width_scale), 20)),
            bg='#D9D9D9'
        )
        self.timer_label.pack(expand=True)
        
        # Improve start button appearance
        self.start_button = tk.Button(
            self.root,
            text="Start Simulation",
            font=('Arial Hebrew', max(int(18 * self.width_scale), 16)),
            bg='#2E7D32',  # Dark green
            fg='#FFFFFF',
            command=self.start_simulation,
            relief='raised',
            bd=3
        )
        self.start_button.place(
            relx=0.4,
            rely=0.45,
            relwidth=0.2,
            relheight=0.08
        )

    def create_terminal(self):
        terminal_frame = tk.Frame(
            self.root,
            bg='#000000',
            bd=2,
            relief='solid'
        )
        terminal_frame.place(
            relx=0.05,
            rely=0.75,
            relwidth=0.3,
            relheight=0.2
        )
        
        tk.Label(
            terminal_frame,
            text="Terminal",
            font=('Arial Hebrew', int(18 * self.width_scale)),
            bg='#000000',
            fg='#FFFFFF'
        ).place(relx=0.35, rely=0.05)
        
        self.terminal_text = tk.Text(
            terminal_frame,
            bg='#000000',
            fg='#FFFFFF',
            font=('Arial Hebrew', int(12 * self.width_scale))
        )
        self.terminal_text.place(
            relx=0.05,
            rely=0.2,
            relwidth=0.9,
            relheight=0.75
        )

    def upload_image(self, lane):
        try:
            filepath = filedialog.askopenfilename(
                filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")]
            )
            if filepath:
                self.image_paths[lane] = filepath
                count = self.detect_vehicles(filepath)
                self.vehicle_counts[lane].delete(0, tk.END)
                self.vehicle_counts[lane].insert(0, str(count))
                self.terminal_text.insert(
                    tk.END,
                    f"{lane} Lane -> Vehicles detected: {count}\n"
                )
                self.terminal_text.see(tk.END)
        except Exception as e:
            self.terminal_text.insert(tk.END, f"Error processing image: {e}\n")
            self.terminal_text.see(tk.END)

    def detect_vehicles(self, image_path):
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("Failed to load image")
            results = self.model(image)
            count = sum(1 for r in results for box in r.boxes 
                       if int(box.cls) in self.vehicle_classes)
            return count
        except Exception as e:
            self.terminal_text.insert(tk.END, f"Vehicle detection error: {e}\n")
            self.terminal_text.see(tk.END)
            return 0

    def start_simulation(self):
        try:
            if not self.running and len(self.image_paths) == 4:
                self.running = True
                self.sim_thread = threading.Thread(target=self.run_simulation)
                self.sim_thread.daemon = True  # Make thread daemon
                self.sim_thread.start()
        except Exception as e:
            self.terminal_text.insert(tk.END, f"Simulation error: {e}\n")
            self.terminal_text.see(tk.END)

    def run_simulation(self):
        # Simulation logic
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernTrafficGUI(root)
    root.mainloop()