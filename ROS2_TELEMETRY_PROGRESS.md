# LineBot ROS2 Telemetry Progress Log

> **Date:** 2026-08-27  
> **Goal:** Connect an Arduino Uno running line-follower firmware to a ROS2 Jazzy workspace inside WSL2, and receive telemetry topics.

---

## What has been done

### 1. Workspace setup

- Git cloned the repository into WSL at `~/linebot`:

  ```bash
  cd ~
  git clone https://github.com/Vishalnar26/linebot.git linebot
  ```

- Built the ROS2 workspace inside WSL:

  ```bash
  cd ~/linebot/linebot_ws
  source /opt/ros/jazzy/setup.bash
  colcon build --symlink-install
  source install/setup.bash
  ```

### 2. USB passthrough from Windows to WSL2

- Installed `usbipd-win` on Windows.
- Identified the Arduino Uno as `BUSID 2-3` (VID:PID `2341:0069`).
- Shared and attached it to WSL:

  ```powershell
  # PowerShell as Administrator
  usbipd list
  usbipd bind --busid 2-3
  usbipd attach --wsl --busid 2-3 --auto-attach
  ```

- After attachment, the Arduino appears under `/dev/ttyACM0` or `/dev/ttyACM1` in WSL.
- Permission fixed each time with:

  ```bash
  sudo chmod 666 /dev/ttyACM0
  # or
  sudo chmod 666 /dev/ttyACM1
  ```

### 3. Firmware on Arduino

- Current firmware: `arduino/linebot/linebot_onboard.ino`
- It runs PID **on the Arduino** and prints telemetry lines:

  ```
  A_Raw:469,513,142 E:-0.291 P:-44 D:-6 PWM:50,150
  ```
- It ignores `P:left,right` commands because PID is handled onboard.

### 4. ROS2 serial bridge update

- Modified `linebot_ws/src/line_follower/line_follower/serial_bridge_node.py` to:
  - Auto-detect the onboard PID telemetry format (`A_Raw:...`).
  - Also still support the original host-PID format (`D:...|A:...`).
  - Publish `/sensor_data`, `/line_error`, `/pid_terms`, `/motor_pwm`.
  - Retry on transient serial errors instead of exiting.
- Added `telemetry_only.launch.py` for use when the Arduino handles PID onboard.

### 5. Launch command used

```bash
ros2 launch line_follower telemetry_only.launch.py serial_port:=/dev/ttyACM0
# or /dev/ttyACM1 if the port number changes after re-attachment
```

### 6. Verified topics

```bash
ros2 topic list
ros2 node list
```

- Nodes: `/serial_bridge_node`, `/line_follower_controller`
- Topics present: `/sensor_data`, `/line_error`, `/motor_pwm`, `/pid_terms`, `/cmd_vel`, etc.

---

## Current blocker

The serial connection through `usbipd` is **unstable**:

- `dmesg` repeatedly shows:

  ```
  vhci_hcd: unlink->seqnum ...
  vhci_hcd: urb->status -104
  ```

- The Arduino serial device sometimes disappears and reappears as `/dev/ttyACM1` instead of `/dev/ttyACM0`.
- `cat /dev/ttyACM0` sometimes prints telemetry, sometimes prints nothing, even though `usbipd list` shows the device as `Attached`.
- Launch can open the port but then hits `Serial read error: device reports readiness to read but returned no data`.

### Suspected causes

1. Arduino Uno resets when the serial port is opened (DTR reset). With USB/IP, this reset may destabilize the device and cause it to re-enumerate or enter bootloader/DFU mode (the device has appeared as `DFU-RT Port`).
2. The USB cable or port may be unreliable.
3. `usbipd-win` NAT networking mode may be dropping URBs.

---

## Next steps to try (in order)

### Step A: Disable DTR reset before reading

In WSL, run:

```bash
stty -F /dev/ttyACM0 -hupcl
# or
stty -F /dev/ttyACM1 -hupcl
cat /dev/ttyACM0
```

If telemetry appears, the DTR reset is the problem. Update the bridge node to open the serial port with `dsrdtr=False` and `rtscts=False` to prevent the reset.

### Step B: Re-upload firmware from Windows

If `cat /dev/ttyACM0` still prints nothing, the Arduino may be stuck in bootloader/DFU mode.

1. Detach from WSL:

   ```powershell
   usbipd detach --busid 2-3
   ```

2. Open Arduino IDE on Windows and select the correct COM port.
3. Upload `arduino/linebot/linebot_onboard.ino`.
4. Re-attach to WSL:

   ```powershell
   usbipd attach --wsl --busid 2-3 --auto-attach
   ```

5. Check `cat /dev/ttyACM0` again.

### Step C: Use a Windows-side serial-to-TCP bridge

If `usbipd` cannot pass the serial device reliably to WSL, keep the Arduino connected to Windows and stream its data over TCP into WSL:

1. Install Python `pyserial` on Windows:

   ```powershell
   pip install pyserial
   ```

2. Run a small TCP bridge script on Windows that reads COM3 and forwards it to WSL:

   ```python
   # serial_bridge_tcp.py (run on Windows)
   import serial, socket, time
   ser = serial.Serial('COM3', 115200, timeout=1)
   s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   s.bind(('0.0.0.0', 5000))
   s.listen(1)
   conn, addr = s.accept()
   while True:
       line = ser.readline()
       if line:
           conn.sendall(line)
   ```

3. In WSL, connect to the bridge using a virtual serial port or modify the ROS2 node to read from a TCP socket at the Windows host IP (`172.26.208.1` or similar).

### Step D: Switch firmware to the host-PID protocol

If you want ROS2 to control the motors instead of the onboard PID:

1. Upload `arduino/linebot/linebot.ino` (prints `D:0,1,0|A:320,850,290`).
2. Use the original launch file:

   ```bash
   ros2 launch line_follower line_follower.launch.py serial_port:=/dev/ttyACM0
   ```

This still depends on a stable USB passthrough, so solve the connection issue first.

---

## Commands reference

```bash
# Source ROS2 (do this in every new WSL terminal)
source /opt/ros/jazzy/setup.bash
source ~/linebot/linebot_ws/install/setup.bash

# Check serial device
ls /dev/ttyACM* /dev/ttyUSB*
sudo chmod 666 /dev/ttyACM0

# Raw serial test
cat /dev/ttyACM0

# Launch telemetry-only mode
ros2 launch line_follower telemetry_only.launch.py serial_port:=/dev/ttyACM0

# Inspect topics
ros2 topic list
ros2 node list
ros2 topic echo /sensor_data
ros2 topic echo /line_error
ros2 topic echo /pid_terms
ros2 topic echo /motor_pwm

# Check USB/IP status from Windows PowerShell (admin)
usbipd list
usbipd attach --wsl --busid 2-3 --auto-attach
```

---

## Important note about editing workflow

- The repository was originally cloned into `C:\linebot` on Windows for editing in VS Code.
- Changes must be committed and pushed from Windows before pulling into WSL:

  ```powershell
  cd C:\linebot
  git add .
  git commit -m "..."
  git push
  ```

- Then pull and rebuild in WSL:

  ```bash
  cd ~/linebot
  git pull
  cd linebot_ws
  source /opt/ros/jazzy/setup.bash
  colcon build --symlink-install
  source install/setup.bash
  ```

---

## Files modified

- `linebot_ws/src/line_follower/line_follower/serial_bridge_node.py` — onboard telemetry parsing, retry logic.
- `linebot_ws/src/line_follower/launch/telemetry_only.launch.py` — new launch file.
