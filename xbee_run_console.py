import time
import threading
from digi.xbee.devices import DigiMeshDevice, NetworkEventReason
from digi.xbee.models.status import NetworkDiscoveryStatus
import secrets
import string
import json
import serial
import queue
from datetime import datetime
import logging

SEPARATOR = "\x1F" 
logging.basicConfig(level=logging.DEBUG)

class Communicator:
    def __init__(self):
        self.device = None
        #self.xbee_network = None
        self.received_message_ids = set() # Список ідентифікаторів
        self.message_count = 0 # Поточна кількість
        self.clear_list_after = 5  # Гранична кількість для очистки
        self.current_discovered_devices = set()
        self.devices_to_send = {}
        self.timer_flag = False
        self.message_parts = {}
        self.message_queue = queue.Queue()

    # Генерація ідентифікатора
    def generate_message_id(self):
        #return uuid.uuid4().hex
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(5))
    
    def forward_message(self, full_message, source_device, base_message_id):
        # try:
        #     chunk_size = 10
        #     num_parts = (len(full_message) + chunk_size - 1) // chunk_size
            
        #     remote_devices = self.current_discovered_devices

        #     for i in range(num_parts):
        #         start_index = i * chunk_size
        #         end_index = min((i + 1) * chunk_size, len(full_message))
        #         message_part = full_message[start_index:end_index]

        #         message_id = f"{base_message_id}{i + 1}"

        #         data = {
        #             "id": message_id,
        #             "first": self.device.get_node_id(),
        #             "msg": message_part,
        #             "l": 1 if i + 1 == num_parts else 0
        #         }
        #         message_send = json.dumps(data)

        #         for remote_device in remote_devices:
        #             if remote_device.get_64bit_addr() != source_device.get_64bit_addr():
        #                 print(f"Forwarding part {i + 1}/{num_parts}: {message_send}")
        #                 self.device.send_data_async(remote_device, message_send)

        # except Exception as e:
        #     print("Forwarding error:", str(e))
        pass

    def message_callback(self, message):
        if message.remote_device is None:
            print("Received message without remote device information:", message.data.decode())
            return

        source_device = message.remote_device
        if not message.data:
            return

        # Декодируем данные из байтов
        message_data = message.data.decode()
        try:
            # Разбираем сообщение по разделителю
            parts = message_data.split(SEPARATOR)
            
            if len(parts) < 5:
                print("Invalid message format")
                return

            # Получаем части сообщения
            base_message_id = parts[0]  # ID сообщения (например, из base_message_id)
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

            # print(f"PARTS OF MSG: {self.message_parts}")

            # Проверяем, получены ли все части сообщения
            total_parts = self.message_parts[base_message_id]["total_parts"]
            if total_parts is not None and len(self.message_parts[base_message_id]["parts"]) == total_parts:
                # Собираем сообщение из всех частей
                full_message = ''.join(
                    self.message_parts[base_message_id]["parts"][i] for i in range(0, total_parts)
                )

                print(f"Full message: {full_message}")
                print(f"LEN MESSAGE: {len(full_message)} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{str(datetime.now().microsecond)[:3]}")
                print(f"Fisrt sender: {self.message_parts[base_message_id]["first_sender"]}")

                # Помещаем в очередь для дальнейшей обработки
                self.message_queue.put({
                    "first": self.message_parts[base_message_id]["first_sender"],
                    "from": source_device.get_node_id(),
                    "msg": full_message
                })

                # Теперь удаляем ID, так как сообщение собрано и обработано
                del self.message_parts[base_message_id]

                # Пробрасываем сообщение дальше
                self.forward_message(full_message, source_device, base_message_id)

        except Exception as e:
            print(f"Error processing message: {e}")

    #Створення колбеків для пошуку девайсів
    def callback_discover(self):
        xbee_network = self.device.get_network()
        xbee_network.set_discovery_timeout(10)  # Було 15, змінив на 3.2 (доступний мінімум)
        try:
            # Callback for discovered devices.
            def callback_device_discovered(remote):
                pass

            # Callback for discovery finished.
            def callback_discovery_finished(status):
                if status == NetworkDiscoveryStatus.SUCCESS:
                    self.current_discovered_devices = self.device.get_network().get_devices()
                    # Оновлення списку пристроїв для надсилання на основі поточного списку виявлених пристроїв
                    self.devices_to_send = {key: value for key, value in self.devices_to_send.items() if value["device"] in self.current_discovered_devices}
                    #print("Discovery process finished successfully.")
                    pass
                else:
                    print("There was an error discovering devices: %s" % status.description)

            xbee_network.add_device_discovered_callback(callback_device_discovered)
            xbee_network.add_discovery_process_finished_callback(callback_discovery_finished)
        except Exception as e:
                print("Connection error: %s" % str(e))

    #Ф-я потоку
    def run_device_discovery(self):
        while self.device and self.device.is_open():
            xbee_network = self.device.get_network()
            if self.timer_flag:
                xbee_network.clear()
                self.timer_flag = False
                #print("Очистили")
            xbee_network.start_discovery_process()

            while xbee_network.is_discovery_running():
                time.sleep(0.1)

    def run_timer(self):
        while self.device and self.device.is_open():
            time.sleep(32)  # Чекати 32 секунди
            self.timer_flag = True

    #Створення потоку пошуку
    def start_device_discovery(self):
        discovery_thread = threading.Thread(target=self.run_device_discovery)
        discovery_thread.daemon = True
        discovery_thread.start()

    #Створення потоку таймера для очищення
    def start_timer(self):
        timer_thread = threading.Thread(target=self.run_timer)
        timer_thread.daemon = True
        timer_thread.start()

    #Команда connect
    def handle_connect(self, params):
        if len(params) < 1:
            print("Error, no connect [device_port_name] provided")
            return

        device_name = str(params[0])

        if self.device is not None:
            print("Error, device already connected")
            return
        
        #port = "/dev/cu.usbserial-" + device_name
        port = "" + device_name
        print("Try connect to: %s" % port)
        self.device = DigiMeshDevice(port, 57600)

        try:
            self.device.open()
            self.device.add_data_received_callback(self.message_callback)

        except Exception as e:
                print("Connection error: %s" % str(e))

        self.callback_discover()
        self.start_device_discovery()
        self.start_timer()

    # Команда send
    def handle_send(self, params):
        if len(params) < 1:
            print("No send params [message] provided")
            return

        # Собираем сообщение из всех параметров
        message = ' '.join(params)

        if self.device is None:
            print("Error, no device connected")
            return

        # Очистка списка идентификаторов при необходимости
        self.message_count += 1
        if self.message_count >= self.clear_list_after:
            self.received_message_ids.clear()
            self.message_count = 0

        try:
            remote_devices = self.current_discovered_devices
            base_message_id = self.generate_message_id()  # Базовый ID сообщения
            self.received_message_ids.add(base_message_id)

            # Разделение сообщения на части по 10 символа
            message_parts = [message[i:i+10] for i in range(0, len(message), 10)]
            total_parts = len(message_parts)

            # Отправка каждой части сообщения
            for part_num, message_part in enumerate(message_parts, start=1):
                # Формируем уникальный ID для каждой части сообщения
                message_id = f"{base_message_id}{part_num}"

                # Подготовка данных для отправки
                data = {
                    "id": message_id,  # Уникальный ID для каждой части
                    "first": self.device.get_node_id(),
                    "msg": message_part,
                    "l": 1 if part_num == total_parts else 0  # Метка последней части
                }

                message_send = json.dumps(data)
                print(message_send)

                # Отправляем сообщение на все удаленные устройства
                for i, remote_device in enumerate(remote_devices):
                    self.device.send_data_async(remote_device, message_send)
                    print(f"Part {part_num} sent to:", remote_device.get_node_id())

        except Exception as e:
            print(f"Send error: {str(e)}")


    # Команда send_single
    def handle_send_single(self, params):
        if len(params) < 2:
            print("No send param [remote_device] or/and [message]")
            return

        remote_address = str(params[0])
        message = ' '.join(params[1:])  # Собираем сообщение из всех оставшихся параметров

        if self.device is None:
            print("Error, no device connected")
            return

        # Очистка списка идентификаторов при необходимости
        self.message_count += 1
        if self.message_count >= self.clear_list_after:
            self.received_message_ids.clear()
            self.message_count = 0

        try:
            remote_devices = self.current_discovered_devices
            message_id = self.generate_message_id()  # Генерируем ID для сообщения
            self.received_message_ids.add(message_id)
            
            # Разделение сообщения на части по 10 символов
            message_parts = [message[i:i+10] for i in range(0, len(message), 10)]
            total_parts = len(message_parts)

            # Поиск целевого устройства
            remote_device = None
            for dev in remote_devices:
                if dev.get_node_id() == remote_address:
                    remote_device = dev
                    break

            if remote_device is None:
                print("Device not found with address: %s" % remote_address)
                return

            # Отправка каждой части сообщения
            for part_num, message_part in enumerate(message_parts, start=1):
                # Формируем уникальный ID для каждой части сообщения
                part_id = f"{message_id}{part_num}"

                # Подготовка данных для отправки
                data = {
                    "id": part_id,  # Уникальный ID для каждой части
                    "first": self.device.get_node_id(),
                    "msg": message_part,
                    "l": 1 if part_num == total_parts else 0  # Метка последней части
                }

                message_send = json.dumps(data)
                print(message_send)

                # Отправляем сообщение на целевое устройство
                self.device.send_data_async(remote_device, message_send)
                print(f"Part {part_num} sent to:", remote_device.get_node_id())

        except Exception as e:
            print(f"Send error: {str(e)}")


    #Команда list
    def handle_list(self, params):
        print("Devices found:")
        remote_devices = self.current_discovered_devices
        for remote_device in remote_devices:
            print(remote_device.get_node_id())

    #Примусове встановлення прапорця оновлення списка
    def handle_refresh(self, params):
        self.timer_flag = True

class CommunicatorCommandProcessor:
    def __init__(self):
        self.commands = {}
        self.communicator = Communicator()
        self.commands["connect"] = self.communicator.handle_connect
        self.commands["send"] = self.communicator.handle_send
        self.commands["send_single"] = self.communicator.handle_send_single
        self.commands["list"] = self.communicator.handle_list
        self.commands["refresh"] = self.communicator.handle_refresh

    def process_command(self, input_text):
        parts = input_text.split()
        if not parts:
            return

        command = parts[0]
        params = parts[1:]

        if command in self.commands:
            self.commands[command](params)
        else:
            print(f"Unknown command: {command}")

if __name__ == "__main__":
    processor = CommunicatorCommandProcessor()

    while True:
        user_input = input("Input command: ")
        processor.process_command(user_input)