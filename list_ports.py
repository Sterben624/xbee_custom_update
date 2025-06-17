import serial.tools.list_ports

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    if ports:
        print("Available serial ports:")
        for port in ports:
            print(f"- Port: {port.device}")
            print(f"  Description: {port.description}")
            print(f"  Manufacturer: {port.manufacturer}")
            print(f"  Product ID: {port.product}")
            print(f"  Serial Number: {port.serial_number}")
            print(f"  VID:PID: {port.vid}:{port.pid}")
            print()
    else:
        print("No serial ports available")

list_serial_ports()
