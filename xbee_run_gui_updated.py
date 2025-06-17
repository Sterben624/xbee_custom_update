import tkinter as tk
from tkinter import scrolledtext
from xbee_for_import import Communicator
import json
import threading
import queue
from tkinter import ttk
import os
import time
import serial.tools.list_ports

class XBeeGUI:
    def __init__(self, root):
        self.root = root
        self.timeout_RC = tk.DoubleVar(value=1.0)
        self.timer = None
        self.root.title("XBee Communicator")
        self.communicator = Communicator()
        self.log_file_path = "received_messages.log"

        # Port Entry and Connect Button
        self.port_entry = tk.Entry(root, width=50)
        self.port_entry.grid(row=0, column=0, columnspan=2, pady=2)
        self.port_entry.insert(0, "")

        self.connect_button = tk.Button(root, text="Connect to Device", command=self.connect_device, height=2, width=20)
        self.connect_button.grid(row=1, column=0, pady=2)

        self.list_ports = tk.Button(root, text="Ports", command=self.list_serial_ports, height=2, width=20)
        self.list_ports.grid(row=1, column=1, pady=2)

        self.list_button = tk.Button(root, text="List", command=self.list_devices, height=2, width=20)
        self.list_button.grid(row=1, column=2, pady=2)

        # Frame for groups of buttons and input fields
        self.groups_frame = tk.Frame(root)
        self.groups_frame.grid(row=2, column=0, columnspan=2, pady=2, sticky="ew")

        # Mode Frame to hold mode buttons
        self.mode_frame = tk.Frame(root)
        self.mode_frame.grid(row=3, column=0, columnspan=2, pady=2, sticky="ew")

        # Move Frame to hold the Move button
        self.move_frame = tk.Frame(root)
        self.move_frame.grid(row=4, column=0, columnspan=2, pady=2, sticky="ew")

        self.create_buttons_and_fields()
        self.create_mode_button()
        self.create_move_button()

        # Output Area (for received messages)
        self.output_area = scrolledtext.ScrolledText(root, width=60, height=20, state='disabled')
        self.output_area.grid(row=2, column=2, rowspan=4, padx=10, pady=2, sticky="nsew")

        self.reboot_button = tk.Button(self.move_frame, text="Reboot", height=2, width=15, 
                                        command=self.send_reboot, bg="#FF6347")
        self.reboot_button.grid(row=5, column=0, columnspan=5, pady=2)

        # Ensure the grid configuration allows for resizing
        root.grid_columnconfigure(0, weight=1, uniform="equal")
        root.grid_columnconfigure(1, weight=1, uniform="equal")
        root.grid_columnconfigure(2, weight=2, uniform="equal")  # Wider column for output

        # if not os.path.exists(self.log_file_path):
        with open(self.log_file_path, "a") as log_file:
            log_file.write("\n\n---------Start logging---------\n")

        self.start_message_receiver()


    def create_buttons_and_fields(self):
        # First Row: Three Groups
        takeoff_label = tk.Label(self.groups_frame, text="Takeoff param", width=15)
        takeoff_label.grid(row=0, column=4, padx=5, pady=1)

        self.arm_button = tk.Button(self.groups_frame, text="Arm", height=2, width=15,
                               command=lambda: self.send_arm_disarm(0))
        self.arm_button.grid(row=1, column=0, padx=5, pady=2)

        self.disarm_button = tk.Button(self.groups_frame, text="Disarm", height=2, width=15,
                                  command=lambda: self.send_arm_disarm(1))
        self.disarm_button.grid(row=1, column=1, padx=5, pady=2)

        self.land_button = tk.Button(self.groups_frame, text="Land", height=2, width=15,
                                command=lambda: self.send_land())
        self.land_button.grid(row=1, column=2, padx=5, pady=2)

        self.takeoff_button = tk.Button(self.groups_frame, text="Takeoff", height=2, width=15,
                                        command=self.send_takeoff)
        self.takeoff_button.grid(row=1, column=3, padx=5, pady=2)

        self.takeoff_input = tk.Entry(self.groups_frame, width=10)
        self.takeoff_input.grid(row=1, column=4, padx=5, pady=2)

        self.set_height_button = tk.Button(self.groups_frame, text="Set Height", height=2, width=15,
                                        command=self.send_set_height)
        self.set_height_button.grid(row=2, column=1, padx=5, pady=2)

        self.set_height_input = tk.Entry(self.groups_frame, width=10)
        self.set_height_input.grid(row=2, column=2, padx=5, pady=2)

        # Add a horizontal line using a Canvas widget
        line = tk.Canvas(self.groups_frame, height=2, bd=0, highlightthickness=0)
        line.grid(row=3, column=0, columnspan=5, padx=5, pady=2)
        line.create_line(0, 1, 600, 1, fill="black")

    def create_mode_button(self):
        self.mode_label = tk.Label(self.mode_frame, text="MODES", width=15)
        self.mode_label.grid(row=0, column=3, padx=5, pady=1)

        # ALT_HOLD button
        self.alt_hold_mode_button = tk.Button(
            self.mode_frame, text="ALT_HOLD", height=2, width=15,
            command=lambda: self.send_mode("ALT_HOLD")
        )
        self.alt_hold_mode_button.grid(row=1, column=1, padx=5, pady=2)

        # STABILIZE button
        self.stabilaze_mode_button = tk.Button(
            self.mode_frame, text="STABILIZE", height=2, width=15,
            command=lambda: self.send_mode("STABILIZE")
        )
        self.stabilaze_mode_button.grid(row=1, column=2, padx=5, pady=2)

        # LAND button
        self.land_mode_button = tk.Button(
            self.mode_frame, text="LAND", height=2, width=15,
            command=lambda: self.send_mode("LAND")
        )
        self.land_mode_button.grid(row=1, column=3, padx=5, pady=2)

        # GUIDED button
        self.guided_hold_button = tk.Button(
            self.mode_frame, text="GUIDED", height=2, width=15,
            command=lambda: self.send_mode("GUIDED")
        )
        self.guided_hold_button.grid(row=1, column=4, padx=5, pady=2)

        # POSHHOLD button
        self.poshhold_hold_button = tk.Button(
            self.mode_frame, text="POSHHOLD", height=2, width=15,
            command=lambda: self.send_mode("POSHHOLD")
        )
        self.poshhold_hold_button.grid(row=1, column=5, padx=5, pady=2)

        line = tk.Canvas(self.mode_frame, height=2, bd=0, highlightthickness=0)
        line.grid(row=2, column=0, columnspan=5, padx=5, pady=2)
        line.create_line(0, 1, 600, 1, fill="black")

    def create_move_button(self):
        # Move Button
        self.move_button = tk.Button(self.move_frame, text="Move", height=2, width=15, command=self.send_move)
        self.move_button.grid(row=0, column=0, columnspan=3, pady=2)

        self.reset_button = tk.Button(self.move_frame, text="Reset", height=2, width=15, command=self.reset_inputs)
        self.reset_button.grid(row=0, column=1, columnspan=3, pady=2)

        # Labels for input fields
        self.power_label = tk.Label(self.move_frame, text="Power")
        self.power_label.grid(row=1, column=0, padx=5, pady=2)

        self.pitch_label = tk.Label(self.move_frame, text="Pitch")
        self.pitch_label.grid(row=1, column=1, padx=5, pady=2)

        self.roll_label = tk.Label(self.move_frame, text="Roll")
        self.roll_label.grid(row=1, column=2, padx=5, pady=2)

        self.yaw_label = tk.Label(self.move_frame, text="Yaw")
        self.yaw_label.grid(row=1, column=3, padx=5, pady=2)

        # Input fields
        self.power_input = tk.Entry(self.move_frame, width=10)
        self.power_input.grid(row=2, column=0, padx=5, pady=2)
        self.power_input.insert(0, "1500")

        self.pitch_input = tk.Entry(self.move_frame, width=10)
        self.pitch_input.grid(row=2, column=1, padx=5, pady=2)
        self.pitch_input.insert(0, "1500")

        self.roll_input = tk.Entry(self.move_frame, width=10)
        self.roll_input.grid(row=2, column=2, padx=5, pady=2)
        self.roll_input.insert(0, "1500")

        self.yaw_input = tk.Entry(self.move_frame, width=10)
        self.yaw_input.grid(row=2, column=3, padx=5, pady=2)
        self.yaw_input.insert(0, "1500")

        self.create_adjust_buttons(self.move_frame, self.power_input, 2, 0)
        self.create_adjust_buttons(self.move_frame, self.pitch_input, 2, 1)
        self.create_adjust_buttons(self.move_frame, self.roll_input, 2, 2)
        self.create_adjust_buttons(self.move_frame, self.yaw_input, 2, 3)

        for i in range(4):
            self.move_frame.grid_columnconfigure(i, weight=1, uniform="equal")

    def create_adjust_buttons(self, parent, input_field, row, column):
        """Create "-" and "+" buttons under a specific input field."""
        minus_button = tk.Button(parent, text="-", width=4, command=lambda: self.adjust_input(input_field, -50))
        minus_button.grid(row=row, column=column, sticky="w", padx=(5, 0), pady=2)

        plus_button = tk.Button(parent, text="+", width=4, command=lambda: self.adjust_input(input_field, 50))
        plus_button.grid(row=row, column=column, sticky="e", padx=(0, 5), pady=2)

    def connect_device(self):
        port = self.port_entry.get()
        try:
            if port:
                self.communicator.connect(port)
                self.append_output(f"Connected to device on port: {port}")
            else:
                self.append_output("No port entered.")
        except Exception as e:
            # Выводим сообщение об ошибке
            self.append_output(f"Error connecting to device: {str(e)}")

    def list_devices(self):
        devices = self.communicator.list_devices()
        device_list = "Devices found:\n" + "\n".join(devices)
        self.append_output(device_list)

    def adjust_input(self, input_field, delta):
        try:
            current_value = int(input_field.get()) if input_field.get() else 0
            new_value = max(0, current_value + delta)
            input_field.delete(0, tk.END)
            input_field.insert(0, str(new_value))
        except ValueError:
            input_field.delete(0, tk.END)
            input_field.insert(0, "0")

    def reset_inputs(self):
        self.power_input.delete(0, tk.END)
        self.power_input.insert(0, "1500")

        self.pitch_input.delete(0, tk.END)
        self.pitch_input.insert(0, "1500")

        self.roll_input.delete(0, tk.END)
        self.roll_input.insert(0, "1500")

        self.yaw_input.delete(0, tk.END)
        self.yaw_input.insert(0, "1500")

    def send_arm_disarm(self, state):
        if state == 0:
            self.communicator.send("arm,0")
            self.append_output(f"Sent command: arm,0")
        elif state == 1:
            self.communicator.send("arm,1")
            self.append_output(f"Sent command: arm,1")

    def send_land(self):
        self.communicator.send("land,1")
        self.append_output(f"Sent command: land,1")

    def send_takeoff(self):
        altitude = self.takeoff_input.get()
        if altitude.isdigit():
            self.communicator.send(f"takeoff,{altitude}")
            self.append_output(f"Sent command: takeoff,{altitude}")
        else:
            self.append_output("Enter a numeric value.")

    def send_set_height(self):
        height = self.set_height_input.get()
        if(height):
            self.communicator.send(f"setHeight,{height}")
            self.append_output(f"Sent command: setHeight,{height}")
        else:
            self.append_output(f"Enter setHeight value!")

    def send_mode(self, mode):
        """Send mode change command."""
        self.communicator.send(f"mode,{mode}")
        self.append_output(f"Sent command: mode,{mode}")

    def send_move(self):
        """Send a move command with values from input fields."""
        try:
            power = int(self.power_input.get()) if self.power_input.get().isdigit() else 0
            pitch = int(self.pitch_input.get()) if self.pitch_input.get().isdigit() else 0
            roll = int(self.roll_input.get()) if self.roll_input.get().isdigit() else 0
            yaw = int(self.yaw_input.get()) if self.yaw_input.get().isdigit() else 0

            command = f"move,{power},{pitch},{roll},{yaw}"

            self.communicator.send(command)

            self.append_output(f"Sent command: {command}")
        except ValueError:
            self.append_output("Error: Invalid input in move fields. Please enter valid integers.")

    def send_reboot(self):
        self.communicator.send("reboot,0")
        self.append_output(f"Sent command: reboot,0")

    def append_output(self, message):
        self.output_area.config(state='normal')
        self.output_area.insert(tk.END, message + "\n")
        self.output_area.config(state='disabled')
        self.output_area.yview(tk.END)
        self.log_message(message)

    def start_message_receiver(self):
        self.message_receiver_thread = threading.Thread(target=self.update_received_messages, daemon=True)
        self.message_receiver_thread.start()

    def update_received_messages(self):
        while True:
            try:
                message = self.communicator.message_queue.get(timeout=1)
                data = json.loads(message)
                text = data["msg"]
                self.append_output(f"Received message: {text}")
                # self.log_message(text)
            except queue.Empty:
                continue

    def log_message(self, message):
        try:                    
            with open(self.log_file_path, "a") as log_file:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                log_file.write(f"{timestamp}-> {message}\n")
        except Exception as e:
            print(f"Error writing to log file: {e}")

    def list_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        if ports:
            print("Available serial ports:")
            self.append_output("Available serial ports:")
            for port in ports:
                self.append_output(f"- Port: {port.device}\n  Description: {port.description}")
        else:
            self.append_output("No serial ports available")

if __name__ == "__main__":
    root = tk.Tk()
    app = XBeeGUI(root)
    root.mainloop()
