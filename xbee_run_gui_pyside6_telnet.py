import sys
import json
import threading
import queue
import time
import telnetlib
import logging
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QObject

class TelnetCommunicator:
    def __init__(self):
        self.tn = None
        self.message_queue = queue.Queue()
        self.host = "192.168.88.251"
        self.port = 2323

    def connect(self, host="192.168.88.251", port=2323):
        """Store connection parameters"""
        self.host = host
        self.port = port
        return True

    def _connect_and_send(self, command):
        """Temporary connection to send a command"""
        try:
            # Connect
            self.tn = telnetlib.Telnet(self.host, self.port, timeout=5)
            
            # Send command
            self.tn.write(f"{command}\r\n".encode('ascii'))
            
            # Wait and read response
            time.sleep(1)  # Wait 1 second
            try:
                response = self.tn.read_very_eager()
                if response:
                    decoded = response.decode('ascii', errors='ignore').strip()
                    message = json.dumps({"msg": decoded})
                    self.message_queue.put(message)
            except Exception as e:
                self.logger.error(f"Error reading response: {str(e)}")
            
            # Close connection
            self.tn.close()
            self.tn = None
            
        except Exception as e:
            if self.tn:
                self.tn.close()
                self.tn = None
            raise Exception(f"Command failed: {str(e)}")

    def send(self, command):
        """Send command with temporary connection"""
        try:
            self._connect_and_send(command)
        except Exception as e:
            raise Exception(f"Failed to send command: {str(e)}")

    def close(self):
        """Clean up if needed"""
        if self.tn:
            self.tn.close()
            self.tn = None

    def list_devices(self):
        return ["Telnet connection available at 192.168.88.251:2323"]
import os
import platform
try:
    import winsound
except ImportError:
    winsound = None

def cross_platform_beep(frequency=1000, duration=100):
    """Play a beep sound on Windows and Ubuntu"""
    try:
        if platform.system() == "Windows" and winsound:
            winsound.Beep(frequency, duration)
        elif platform.system() == "Linux":
            # Try multiple methods for Linux
            duration_sec = duration / 1000.0
            
            # Method 1: pactl (PulseAudio) - most reliable on modern Ubuntu
            if os.system("which pactl > /dev/null 2>&1") == 0:
                os.system(f"pactl upload-sample /usr/share/sounds/alsa/Front_Left.wav beep-sample > /dev/null 2>&1")
                os.system("pactl play-sample beep-sample > /dev/null 2>&1")
            # Method 2: speaker-test
            elif os.system("which speaker-test > /dev/null 2>&1") == 0:
                os.system(f"timeout {duration_sec}s speaker-test -t sine -f {frequency} > /dev/null 2>&1")
            # Method 3: ASCII bell (terminal bell)
            else:
                print('\a', end='', flush=True)
        else:
            # Fallback for other systems (macOS, etc.)
            print('\a', end='', flush=True)
    except Exception:
        # Final fallback - ASCII bell
        print('\a', end='', flush=True)

class CommunicatorSignals(QObject):
    message_received = Signal(str)

class XBeeGUIPySide(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telnet Drone Communicator")
        self.communicator = TelnetCommunicator()
        self.setup_logging()
        self.signals = CommunicatorSignals()
        self.signals.message_received.connect(self.handle_received_message)
        self.init_ui()
        self.logger.info("Telnet Drone Communicator started")
        # Start a timer to check for messages
        self.start_message_checker()

    def setup_logging(self):
        """Setup logging configuration to write to log directory."""
        os.makedirs("log", exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        log_filename = f"log/xbee_communicator_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('XBeeGUI')
        self.logger.info(f"Logging initialized - log file: {log_filename}")

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
        """Connect to the device using Telnet."""
        host = "192.168.88.251"
        try:
            self.logger.info(f"Attempting to connect to device at: {host}")
            self.communicator.connect(host)
            self.append_output(f"Connected to device at: {host}")
            self.logger.info(f"Successfully connected to device at: {host}")
            self.port_entry.setText(host)
        except Exception as e:
            self.append_output(f"Error connecting to device: {str(e)}")
            self.logger.error(f"Connection failed to {host}: {str(e)}")


    def list_devices(self):
        """List available devices."""
        devices = self.communicator.list_devices()
        device_list = "Devices found:\n" + "\n".join(devices)
        self.append_output(device_list)


    def adjust_input(self, input_field, delta):
        """Adjust the value in the input field by delta."""
        try:
            current_value = int(input_field.text()) if input_field.text() else 0
            new_value = max(0, current_value + delta)
            input_field.setText(str(new_value))
        except ValueError:
            input_field.setText("0")


    def reset_inputs(self):
        """Reset movement input fields to default values."""
        self.pitch_input.setText("1500")
        self.roll_input.setText("1500")
        self.yaw_input.setText("1500")


    def send_arm_disarm(self, state):
        """Send arm or disarm command."""
        if state == 0:
            self.communicator.send("arm,0")
            self.append_output("Sent command: arm,0")
        elif state == 1:
            self.communicator.send("arm,1")
            self.append_output("Sent command: arm,1")


    def send_land(self):
        """Send land command."""
        self.communicator.send("land,1")
        self.append_output("Sent command: land,1")


    def send_takeoff(self):
        """Send takeoff command with specified altitude."""
        altitude = self.takeoff_input.text()
        if altitude.isdigit():
            self.communicator.send(f"takeoff,{altitude}")
            self.append_output(f"Sent command: takeoff,{altitude}")
        else:
            self.append_output("Enter a numeric value.")


    def send_set_height(self):
        """Send set height command."""
        height = self.set_height_input.text()
        if height:
            self.communicator.send(f"setHeight,{height}")
            self.append_output(f"Sent command: setHeight,{height}")
        else:
            self.append_output("Enter setHeight value!")


    def send_mode(self, mode):
        """Send mode change command."""
        self.communicator.send(f"mode,{mode}")
        self.append_output(f"Sent command: mode,{mode}")


    def send_move(self):
        """Send move command with current input values."""
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
        """Send square command."""
        self.communicator.send("square,0")
        self.append_output("Sent command: square,0")


    def send_reboot(self):
        """Send reboot command."""
        self.communicator.send("reboot,0")
        self.append_output("Sent command: reboot,0")


    def return_control(self):
        """Send return control command."""
        self.communicator.send("returnControl,0")
        self.append_output("Sent command: returnControl,0")


    def battery_status(self):
        """Send battery status command."""
        self.communicator.send("takeoff,0")
        self.append_output("Sent command: takeoff,0")


    def append_output(self, message):
        """Append a message to the output area and log it."""
        self.output_area.append(message)
        self.log_message(message)


    def start_message_checker(self):
        """Start a timer to check for messages periodically."""
        from PySide6.QtCore import QTimer
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self.check_messages)
        self.message_timer.start(100)  # Check every 100ms

    def check_messages(self):
        """Check for new messages in the queue."""
        try:
            while not self.communicator.message_queue.empty():
                message = self.communicator.message_queue.get_nowait()
                data = json.loads(message)
                text = data["msg"]
                self.signals.message_received.emit(text)
        except queue.Empty:
            pass


    def handle_received_message(self, text):
        """Handle a message received from the communicator thread."""
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
            cross_platform_beep(1000, 100)

    def log_message(self, message):
        """Log a message using the configured logger."""
        try:
            self.logger.info(message)
        except Exception as e:
            print(f"Error writing to log file: {e}")


    def list_serial_ports(self):
        """List Telnet connection info."""
        self.append_output("Available Telnet connection:")
        self.append_output("- Host: 192.168.88.251")
        self.append_output("- Port: 2323")
        self.port_entry.setText("192.168.88.251")

def main():
    app = QApplication(sys.argv)
    window = XBeeGUIPySide()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
