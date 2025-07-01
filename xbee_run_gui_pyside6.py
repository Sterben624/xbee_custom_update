import sys
import json
import threading
import queue
import os
import time
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QObject
from xbee_for_import import Communicator
import winsound

class CommunicatorSignals(QObject):
    message_received = Signal(str)

class XBeeGUIPySide(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XBee Communicator")
        self.communicator = Communicator()
        timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        self.log_file_path = f"received_messages{timestamp}.txt"
        self.signals = CommunicatorSignals()
        self.signals.message_received.connect(self.handle_received_message)
        self.init_ui()
        if not os.path.exists(self.log_file_path):
            with open(self.log_file_path, "a") as log_file:
                log_file.write("\n\n---------Start logging---------\n")
        self.start_message_receiver()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        # Connection controls
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout()
        self.port_entry = QLineEdit()
        self.port_entry.setPlaceholderText("Enter port...")
        conn_layout.addWidget(self.port_entry)
        self.connect_btn = QPushButton("Connect to Device")
        self.connect_btn.clicked.connect(self.connect_device)
        conn_layout.addWidget(self.connect_btn)
        self.list_ports_btn = QPushButton("Ports")
        self.list_ports_btn.clicked.connect(self.list_serial_ports)
        conn_layout.addWidget(self.list_ports_btn)
        self.list_devices_btn = QPushButton("List")
        self.list_devices_btn.clicked.connect(self.list_devices)
        conn_layout.addWidget(self.list_devices_btn)
        conn_group.setLayout(conn_layout)
        left_layout.addWidget(conn_group)
        # Controls group
        controls_group = QGroupBox("Controls")
        controls_layout = QGridLayout()
        self.arm_btn = QPushButton("Arm")
        self.arm_btn.clicked.connect(lambda: self.send_arm_disarm(0))
        controls_layout.addWidget(self.arm_btn, 0, 0)
        self.disarm_btn = QPushButton("Disarm")
        self.disarm_btn.clicked.connect(lambda: self.send_arm_disarm(1))
        controls_layout.addWidget(self.disarm_btn, 0, 1)
        self.land_btn = QPushButton("Land")
        self.land_btn.clicked.connect(self.send_land)
        controls_layout.addWidget(self.land_btn, 0, 2)
        self.takeoff_btn = QPushButton("Takeoff")
        self.takeoff_btn.clicked.connect(self.send_takeoff)
        controls_layout.addWidget(self.takeoff_btn, 0, 3)
        self.takeoff_input = QLineEdit()
        self.takeoff_input.setPlaceholderText("Takeoff param")
        controls_layout.addWidget(self.takeoff_input, 0, 4)
        self.set_height_btn = QPushButton("Set Height")
        self.set_height_btn.clicked.connect(self.send_set_height)
        controls_layout.addWidget(self.set_height_btn, 1, 1)
        self.set_height_input = QLineEdit()
        self.set_height_input.setPlaceholderText("Set Height")
        controls_layout.addWidget(self.set_height_input, 1, 2)
        controls_group.setLayout(controls_layout)
        left_layout.addWidget(controls_group)
        # Modes group
        modes_group = QGroupBox("Modes")
        modes_layout = QHBoxLayout()
        for mode in ["ALT_HOLD", "STABILIZE", "LAND", "GUIDED", "POSHHOLD"]:
            btn = QPushButton(mode)
            btn.clicked.connect(lambda checked, m=mode: self.send_mode(m))
            modes_layout.addWidget(btn)
        modes_group.setLayout(modes_layout)
        left_layout.addWidget(modes_group)
        # Movement group
        move_group = QGroupBox("Movement")
        move_layout = QGridLayout()
        move_layout.addWidget(QLabel("Power"), 0, 0)
        move_layout.addWidget(QLabel("Pitch"), 0, 1)
        move_layout.addWidget(QLabel("Roll"), 0, 2)
        move_layout.addWidget(QLabel("Yaw"), 0, 3)
        self.power_input = QLineEdit("1500")
        self.pitch_input = QLineEdit("1500")
        self.roll_input = QLineEdit("1500")
        self.yaw_input = QLineEdit("1500")
        move_layout.addWidget(self.power_input, 1, 0)
        move_layout.addWidget(self.pitch_input, 1, 1)
        move_layout.addWidget(self.roll_input, 1, 2)
        move_layout.addWidget(self.yaw_input, 1, 3)
        # Add +/- buttons
        for idx, field in enumerate([self.power_input, self.pitch_input, self.roll_input, self.yaw_input]):
            minus_btn = QPushButton("-")
            plus_btn = QPushButton("+")
            minus_btn.clicked.connect(lambda checked, f=field: self.adjust_input(f, -25))
            plus_btn.clicked.connect(lambda checked, f=field: self.adjust_input(f, 25))
            move_layout.addWidget(minus_btn, 2, idx)
            move_layout.addWidget(plus_btn, 3, idx)
        self.move_btn = QPushButton("Move")
        self.move_btn.clicked.connect(self.send_move)
        move_layout.addWidget(self.move_btn, 4, 0, 1, 2)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_inputs)
        move_layout.addWidget(self.reset_btn, 4, 2, 1, 2)
        move_group.setLayout(move_layout)
        left_layout.addWidget(move_group)
        # Additional controls
        add_group = QGroupBox("Additional Controls")
        add_layout = QGridLayout()
        self.reboot_btn = QPushButton("Reboot")
        self.reboot_btn.setStyleSheet("background-color: #FF6347; color: white;")
        self.reboot_btn.clicked.connect(self.send_reboot)
        add_layout.addWidget(self.reboot_btn, 0, 0)
        self.square_btn = QPushButton("Square")
        self.square_btn.setStyleSheet("background-color: #0ff5f5; color: black;")
        self.square_btn.clicked.connect(self.send_square)
        add_layout.addWidget(self.square_btn, 0, 1)
        self.return_control_btn = QPushButton("Return Control")
        self.return_control_btn.setStyleSheet("background-color: #0ff5f5; color: black;")
        self.return_control_btn.clicked.connect(self.return_control)
        add_layout.addWidget(self.return_control_btn, 0, 2)
        self.battery_status_entry = QLineEdit()
        self.battery_status_entry.setReadOnly(True)
        add_layout.addWidget(QLabel("Battery:"), 1, 0)
        add_layout.addWidget(self.battery_status_entry, 1, 1)
        self.battery_status_btn = QPushButton("Battery Status")
        self.battery_status_btn.setStyleSheet("background-color: #0ff573; color: black;")
        self.battery_status_btn.clicked.connect(self.battery_status)
        add_layout.addWidget(self.battery_status_btn, 1, 2)
        add_group.setLayout(add_layout)
        left_layout.addWidget(add_group)
        # Add stretch
        left_layout.addStretch(1)
        # Output area
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        main_layout.addLayout(left_layout, 2)
        main_layout.addWidget(self.output_area, 3)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def connect_device(self):
        port = self.port_entry.text()
        try:
            if port:
                self.communicator.connect(port)
                self.append_output(f"Connected to device on port: {port}")
            else:
                self.append_output("No port entered.")
        except Exception as e:
            self.append_output(f"Error connecting to device: {str(e)}")

    def list_devices(self):
        devices = self.communicator.list_devices()
        device_list = "Devices found:\n" + "\n".join(devices)
        self.append_output(device_list)

    def adjust_input(self, input_field, delta):
        try:
            current_value = int(input_field.text()) if input_field.text() else 0
            new_value = max(0, current_value + delta)
            input_field.setText(str(new_value))
        except ValueError:
            input_field.setText("0")

    def reset_inputs(self):
        self.pitch_input.setText("1500")
        self.roll_input.setText("1500")
        self.yaw_input.setText("1500")

    def send_arm_disarm(self, state):
        if state == 0:
            self.communicator.send("arm,0")
            self.append_output("Sent command: arm,0")
        elif state == 1:
            self.communicator.send("arm,1")
            self.append_output("Sent command: arm,1")

    def send_land(self):
        self.communicator.send("land,1")
        self.append_output("Sent command: land,1")

    def send_takeoff(self):
        altitude = self.takeoff_input.text()
        if altitude.isdigit():
            self.communicator.send(f"takeoff,{altitude}")
            self.append_output(f"Sent command: takeoff,{altitude}")
        else:
            self.append_output("Enter a numeric value.")

    def send_set_height(self):
        height = self.set_height_input.text()
        if height:
            self.communicator.send(f"setHeight,{height}")
            self.append_output(f"Sent command: setHeight,{height}")
        else:
            self.append_output("Enter setHeight value!")

    def send_mode(self, mode):
        self.communicator.send(f"mode,{mode}")
        self.append_output(f"Sent command: mode,{mode}")

    def send_move(self):
        try:
            power = int(self.power_input.text()) if self.power_input.text().isdigit() else 0
            pitch = int(self.pitch_input.text()) if self.pitch_input.text().isdigit() else 0
            roll = int(self.roll_input.text()) if self.roll_input.text().isdigit() else 0
            yaw = int(self.yaw_input.text()) if self.yaw_input.text().isdigit() else 0
            command = f"move,{power},{pitch},{roll},{yaw}"
            self.communicator.send(command)
            self.append_output(f"Sent command: {command}")
        except ValueError:
            self.append_output("Error: Invalid input in move fields. Please enter valid integers.")

    def send_square(self):
        self.communicator.send("square,0")
        self.append_output("Sent command: square,0")

    def send_reboot(self):
        self.communicator.send("reboot,0")
        self.append_output("Sent command: reboot,0")

    def return_control(self):
        self.communicator.send("returnControl,0")
        self.append_output("Sent command: returnControl,0")

    def battery_status(self):
        self.communicator.send("takeoff,0")
        self.append_output("Sent command: takeoff,0")

    def append_output(self, message):
        self.output_area.append(message)
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
                self.signals.message_received.emit(text)
            except queue.Empty:
                continue

    def handle_received_message(self, text):
        self.append_output(f"Received message: {text}")
        # Check for battery voltage message
        if text.startswith("BATT "):
            parts = text.split()
            if len(parts) >= 2 and parts[1].endswith("V"):
                voltage = parts[1][:-1]  # Remove trailing 'V'
                self.battery_status_entry.setText(voltage)
        if text.strip() == "BATTERY_STATUS: Error":
            self.battery_status_entry.setText("ERROR")
        # Play beep if "I'm alive" message received
        if text.startswith("I'm alive"):
            try:
                winsound.Beep(1000, 100)
            except ImportError:
                pass

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
            self.append_output("Available serial ports:")
            for port in ports:
                self.append_output(f"- Port: {port.device}\n  Description: {port.description}")
        else:
            self.append_output("No serial ports available")

def main():
    app = QApplication(sys.argv)
    window = XBeeGUIPySide()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
