# XBee Communication System

## Overview
This project is a small extension of the original library, designed to facilitate real-time wireless control using XBee modules within a reliable mesh network. The primary enhancement enables easier transmission of messages longer than the hardware platform's per-conditional time limit. An intuitive GUI is included for streamlined device management and control operations.

## Project Structure
```
xbee/
├── list_ports.py                  # Serial 
├── xbee_for_import_minimal.py     # Core XBee  
└── xbee_run_gui_updated.py        # GUI 
```

## Dependencies
- Python 3.7+
- digi-xbee >= 1.4.0
- pyserial >= 3.5
- tkinter (included with Python)

## Quick Start
1. **Install Dependencies**
   ```powershell
   pip install digi-xbee pyserial
   ```

2. **List Available Ports**
   ```powershell
   python list_ports.py
   ```

3. **Launch Control Interface**
   ```powershell
   python xbee_run_gui_updated.py
   ```

## Connection Guide
1. Start the GUI application
2. Click "Ports" to view available connections
3. Enter the port name (e.g., COM3)
4. Click "Connect to Device"
5. Wait for device discovery
6. Use control interface

## Technical Details

### Protocol Specifications
- **Message Format**: `message_id|part_number|message|sender|is_last`
- **Separator**: `0x1F` (Unit Separator)
- **Limits**:
  - Maximum message: 400 chars
  - Part size: 50 chars

### Core Features
#### Communication
- Mesh network topology
- Auto device discovery
- Message fragmentation
- Reliable transmission
- Broadcast support
- Point-to-point messaging

#### Interface
- Connection management
- Movement control
- Mode selection
- Height adjustment
- Emergency procedures
- Real-time logging

## Development Guide

### Adding Commands
```python
def send_custom_command(self):
    command = {
        "type": "custom",
        "params": {
            "value": self.value_entry.get()
        }
    }
    self.communicator.send(json.dumps(command))
```

### Port Detection Example
```python
import serial.tools.list_ports

ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"Port: {port.device}")
    print(f"Description: {port.description}\n")
```

## Troubleshooting
1. **No Ports Found**
   - Check USB connections
   - Verify device manager
   - Install FTDI drivers

2. **Connection Failed**
   - Confirm baud rate (57600)
   - Check port permissions
   - Verify XBee configuration

3. **Message Errors**
   - Check network visibility
   - Verify device addressing
   - Monitor signal strength

## Contributing
1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create pull request

## License
[Your License]

## Contact
[Your Contact Information]

---
*For detailed documentation, see the code comments and docstrings in each module.*