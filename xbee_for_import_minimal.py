import logging
from digi.xbee.devices import DigiMeshDevice, NetworkEventReason
from digi.xbee.models.status import NetworkDiscoveryStatus
from serial.serialutil import SerialException
from digi.xbee.models.options import TransmitOptions
import secrets
import string
import json
import queue

SEPARATOR = "\x1F" 
MAX_MESSAGE_LENGTH = 400
MAX_PART_LENGTH = 50

# logging.basicConfig(level=logging.DEBUG)

class Communicator:
    def __init__(self):
        self.device = None
        self.received_message_ids = set()
        self.message_count = 0
        self.clear_list_after = 15
        self.current_discovered_devices = set()
        self.devices_to_send = {}
        self.timer_flag = False
        self.message_queue = queue.Queue()
        self.status_discovery = 0
        self.message_parts = {}
    
    def generate_message_id(self):
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(3))

    def message_callback(self, message):
        if message.remote_device is None:
            print("Received message without remote device information:", message.data.decode())
            return

        source_device = message.remote_device
        if not message.data:
            return

        message_data = message.data.decode()
        try:
            parts = message_data.split(SEPARATOR)
            
            if len(parts) < 5:
                print("Invalid message format")
                return

            # Получаем части сообщения
            base_message_id = parts[0]  # ID сообщения
            part_number = int(parts[1])  # Номер части
            received_message_part = parts[2]  # Текущая часть сообщения
            first_sender = parts[3]  # Отправитель
            is_last_part = int(parts[4])  # Флаг последней части

            # Если это новое сообщение, создаем запись
            if base_message_id not in self.message_parts:
                self.message_parts[base_message_id] = {
                    "parts": {}, 
                    "total_parts": None,  # Изначально total_parts нет
                    "first_sender": first_sender
                }

            # Сохраняем текущую часть сообщения
            self.message_parts[base_message_id]["parts"][part_number] = received_message_part

            # Если это последняя часть, обновляем total_parts
            if is_last_part:
                total_parts = part_number + 1  # Количество частей = последний номер части + 1
                self.message_parts[base_message_id]["total_parts"] = total_parts


            # Проверяем, получены ли все части сообщения
            total_parts = self.message_parts[base_message_id]["total_parts"]
            if total_parts is not None and len(self.message_parts[base_message_id]["parts"]) == total_parts:
                # Собираем сообщение из всех частей
                full_message = ''.join(
                    self.message_parts[base_message_id]["parts"][i] for i in range(0, total_parts)
                )

                # print(f"Full message: {full_message}")
                # print(f"LEN MESSAGE: {len(full_message)}")

                # Помещаем в очередь для дальнейшей обработки
                self.message_queue.put({
                    "first": self.message_parts[base_message_id]["first_sender"],
                    "from": source_device.get_node_id(),
                    "msg": full_message
                })

                # Удаляем ID, так как сообщение собрано и обработано
                del self.message_parts[base_message_id]

        except Exception as e:
            print(f"Error processing message: {e}")

    def callback_discover(self):
        xbee_network = self.device.get_network()
        xbee_network.set_discovery_timeout(10)  # было 3.2

        def callback_device_discovered(remote):
            # if not hasattr(callback_device_discovered, "i"):
            #     callback_device_discovered.i = 0
            # callback_device_discovered.i += 1
            # print(f"START DISCOVERING {callback_device_discovered.i}")
            pass

        def callback_discovery_finished(status):
            if status == NetworkDiscoveryStatus.SUCCESS:
                self.current_discovered_devices = xbee_network.get_devices()
                self.devices_to_send = {key: value for key, value in self.devices_to_send.items() if value["device"] in self.current_discovered_devices}
                # print(f"New list devices: {self.current_discovered_devices}")
                self.status_discovery = 1
            else:
                # print(f"Discovery error: {status.description}")
                pass
            xbee_network.clear()
            xbee_network.start_discovery_process()

        if self.status_discovery:
            xbee_network.set_discovery_timeout(5)

        # Добавляем колбеки
        xbee_network.add_device_discovered_callback(callback_device_discovered)
        xbee_network.add_discovery_process_finished_callback(callback_discovery_finished)  

    def connect(self, device_name):
        if self.device is not None:
            print("Device already connected")
            return
        
        port = device_name
        self.device = DigiMeshDevice(port, 57600)

        try:
            self.device.open()
            self.device.add_data_received_callback(self.message_callback)
        except Exception as e:
            print("Connection error:", str(e))

        self.callback_discover()
        xbee_network = self.device.get_network()
        xbee_network.start_discovery_process()

    def send(self, message):
        if self.device is None:
            print("No device connected")
            return
        
        if len(message) > MAX_MESSAGE_LENGTH:
            print("Error: Message length exceeds the maximum allowed (400 characters).")
            return

        self.message_count += 1
        if self.message_count >= self.clear_list_after:
            self.received_message_ids.clear()
            self.message_count = 0

        base_message_id = str(self.generate_message_id())  
        self.received_message_ids.add(base_message_id)

        first_sender = self.device.get_node_id()

        try:
            max_part_length = MAX_PART_LENGTH
            message_parts = [message[i:i + max_part_length] for i in range(0, len(message), max_part_length)]
            total_parts = len(message_parts)

            for part_index, part in enumerate(message_parts):
                is_last = "1" if part_index == total_parts - 1 else "0"
                
                # Замінюємо роздільник у повідомленні (якщо раптом він є)
                safe_part = part.replace(SEPARATOR, "\\" + SEPARATOR)
                formatted_message = f"{base_message_id}{SEPARATOR}{part_index}{SEPARATOR}{safe_part}{SEPARATOR}{first_sender}{SEPARATOR}{is_last}"

                self.device.send_data_broadcast(formatted_message, transmit_options=TransmitOptions.REPEATER_MODE.value)
        except Exception as e:
            print("Send error:", str(e))

    def send_single(self, remote_address, message):
        if self.device is None:
            print("No device connected")
            return

        self.message_count += 1
        if self.message_count >= self.clear_list_after:
            self.received_message_ids.clear()
            self.message_count = 0

        base_message_id = str(self.generate_message_id())  
        self.received_message_ids.add(base_message_id)

        first_sender = self.device.get_node_id()

        try:
            remote_devices = self.current_discovered_devices

            remote_device = None
            for dev in remote_devices:
                if dev.get_node_id() == remote_address:
                    remote_device = dev
                    break

            if remote_device is None:
                print("Device not found with address: %s" % remote_address)
                return

            max_part_length = MAX_PART_LENGTH
            message_parts = [message[i:i + max_part_length] for i in range(0, len(message), max_part_length)]
            total_parts = len(message_parts)

            for part_index, part in enumerate(message_parts):
                is_last = "1" if part_index == total_parts - 1 else "0"

                safe_part = part.replace(SEPARATOR, "\\" + SEPARATOR)

                formatted_message = f"{base_message_id}{SEPARATOR}{part_index}{SEPARATOR}{safe_part}{SEPARATOR}{first_sender}{SEPARATOR}{is_last}"

                self.device.send_data(remote_device, formatted_message, transmit_options=TransmitOptions.REPEATER_MODE.value)

        except Exception as e:
            print("Send error:", str(e))

    def list_devices(self):
        return [dev.get_node_id() for dev in self.current_discovered_devices]

    def refresh(self):
        self.timer_flag = True