"""XBee communication module for mesh network messaging."""

import json
import logging
import queue
import secrets
import string
from typing import Set, Dict, Any, Optional

from digi.xbee.devices import DigiMeshDevice, NetworkEventReason
from digi.xbee.models.options import TransmitOptions
from digi.xbee.models.status import NetworkDiscoveryStatus
from serial.serialutil import SerialException

SEPARATOR = "\x1F"
MAX_MESSAGE_LENGTH = 400
MAX_PART_LENGTH = 50


class Communicator:
    """Handles XBee device communication and message management."""
    
    def __init__(self) -> None:
        self.device: Optional[DigiMeshDevice] = None
        self.received_message_ids: Set[str] = set()
        self.message_count: int = 0
        self.clear_list_after: int = 15
        self.current_discovered_devices: Set[Any] = set()
        self.devices_to_send: Dict[str, Any] = {}
        self.timer_flag: bool = False
        self.message_queue: queue.Queue = queue.Queue()
        self.status_discovery: int = 0
        self.message_parts: Dict[str, Dict] = {}

    def generate_message_id(self) -> str:
        """Generate a unique 3-character message ID."""
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(3))

    def message_callback(self, message) -> None:
        """Process received messages and handle message reassembly."""
        if message.remote_device is None:
            print("Received message without remote device information:", 
                  message.data.decode())
            return

        source_device = message.remote_device
        if not message.data:
            return

        try:
            message_data = message.data.decode()
            parts = message_data.split(SEPARATOR)
            
            if len(parts) < 5:
                print("Invalid message format")
                return

            base_message_id, part_number, received_message_part, first_sender, is_last_part = parts
            part_number = int(part_number)
            is_last_part = int(is_last_part)

            if base_message_id not in self.message_parts:
                self.message_parts[base_message_id] = {
                    "parts": {},
                    "total_parts": None,
                    "first_sender": first_sender
                }

            self.message_parts[base_message_id]["parts"][part_number] = received_message_part

            if is_last_part:
                total_parts = part_number + 1
                self.message_parts[base_message_id]["total_parts"] = total_parts

            message_info = self.message_parts[base_message_id]
            total_parts = message_info["total_parts"]
            
            if (total_parts is not None and 
                len(message_info["parts"]) == total_parts):
                full_message = ''.join(
                    message_info["parts"][i] for i in range(total_parts)
                )

                self.message_queue.put({
                    "first": message_info["first_sender"],
                    "from": source_device.get_node_id(),
                    "msg": full_message
                })

                del self.message_parts[base_message_id]

        except Exception as error:
            print(f"Error processing message: {error}")

    def callback_discover(self) -> None:
        """Initialize and manage network discovery process."""
        xbee_network = self.device.get_network()
        discovery_timeout = 5 if self.status_discovery else 10
        xbee_network.set_discovery_timeout(discovery_timeout)

        def callback_device_discovered(remote):
            pass

        def callback_discovery_finished(status):
            if status == NetworkDiscoveryStatus.SUCCESS:
                self.current_discovered_devices = xbee_network.get_devices()
                self.devices_to_send = {
                    key: value for key, value in self.devices_to_send.items() 
                    if value["device"] in self.current_discovered_devices
                }
                self.status_discovery = 1
            
            xbee_network.clear()
            xbee_network.start_discovery_process()

        xbee_network.add_device_discovered_callback(callback_device_discovered)
        xbee_network.add_discovery_process_finished_callback(
            callback_discovery_finished
        )

    def connect(self, device_name: str) -> None:
        """Connect to XBee device and initialize discovery."""
        if self.device is not None:
            print("Device already connected")
            return
        
        try:
            self.device = DigiMeshDevice(device_name, 57600)
            self.device.open()
            self.device.add_data_received_callback(self.message_callback)
        except Exception as error:
            print("Connection error:", str(error))
            return

        self.callback_discover()
        xbee_network = self.device.get_network()
        xbee_network.start_discovery_process()

    def send(self, message: str) -> None:
        """Broadcast message to all devices in the network."""
        if not self._validate_send_conditions(message):
            return

        base_message_id = self._prepare_message_id()
        first_sender = self.device.get_node_id()

        try:
            self._send_message_parts(message, base_message_id, first_sender)
        except Exception as error:
            print("Send error:", str(error))

    def send_single(self, remote_address: str, message: str) -> None:
        """Send message to a specific device."""
        if not self._validate_send_conditions(message):
            return

        base_message_id = self._prepare_message_id()
        first_sender = self.device.get_node_id()

        try:
            remote_device = self._find_remote_device(remote_address)
            if not remote_device:
                return

            self._send_message_parts(
                message, 
                base_message_id, 
                first_sender, 
                remote_device
            )
        except Exception as error:
            print("Send error:", str(error))

    def _validate_send_conditions(self, message: str) -> bool:
        """Validate conditions before sending message."""
        if self.device is None:
            print("No device connected")
            return False
        
        if len(message) > MAX_MESSAGE_LENGTH:
            print("Error: Message length exceeds the maximum allowed "
                  f"({MAX_MESSAGE_LENGTH} characters).")
            return False
        
        return True

    def _prepare_message_id(self) -> str:
        """Prepare and manage message IDs."""
        self.message_count += 1
        if self.message_count >= self.clear_list_after:
            self.received_message_ids.clear()
            self.message_count = 0

        message_id = self.generate_message_id()
        self.received_message_ids.add(message_id)
        return message_id

    def _find_remote_device(self, remote_address: str):
        """Find remote device by address."""
        for dev in self.current_discovered_devices:
            if dev.get_node_id() == remote_address:
                return dev
        print(f"Device not found with address: {remote_address}")
        return None

    def _send_message_parts(self, message: str, base_message_id: str, 
                          first_sender: str, remote_device=None) -> None:
        """Split and send message parts."""
        message_parts = [
            message[i:i + MAX_PART_LENGTH] 
            for i in range(0, len(message), MAX_PART_LENGTH)
        ]
        total_parts = len(message_parts)

        for part_index, part in enumerate(message_parts):
            is_last = "1" if part_index == total_parts - 1 else "0"
            safe_part = part.replace(SEPARATOR, "\\" + SEPARATOR)
            formatted_message = (f"{base_message_id}{SEPARATOR}{part_index}"
                               f"{SEPARATOR}{safe_part}{SEPARATOR}"
                               f"{first_sender}{SEPARATOR}{is_last}")

            if remote_device:
                self.device.send_data(
                    remote_device, 
                    formatted_message,
                    transmit_options=TransmitOptions.REPEATER_MODE.value
                )
            else:
                self.device.send_data_broadcast(
                    formatted_message,
                    transmit_options=TransmitOptions.REPEATER_MODE.value
                )

    def list_devices(self) -> list:
        """Return list of discovered device IDs."""
        return [dev.get_node_id() for dev in self.current_discovered_devices]

    def refresh(self) -> None:
        """Refresh device status."""
        self.timer_flag = True