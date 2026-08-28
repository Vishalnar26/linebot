# LineBot ROS2 Telemetry

A line-following robot controlled by an Arduino Uno and observed through ROS2 Jazzy running inside WSL2 on a Windows laptop.

## Table of Contents

1. [Overview](#overview)
2. [Hardware Requirements](#hardware-requirements)
3. [Software Requirements](#software-requirements)
4. [Wiring / Assembly](#wiring--assembly)
5. [Windows Setup](#windows-setup)
6. [WSL2 Setup](#wsl2-setup)
7. [Clone the Repository](#clone-the-repository)
8. [Upload Arduino Firmware](#upload-arduino-firmware)
9. [Pass USB Through to WSL2](#pass-usb-through-to-wsl2)
10. [Build the ROS2 Workspace](#build-the-ros2-workspace)
11. [Run the Robot](#run-the-robot)
12. [View Telemetry](#view-telemetry)
13. [Troubleshooting](#troubleshooting)

---

## Overview

This project connects an Arduino-based line-follower to ROS2 Jazzy inside WSL2. The Arduino can either run PID onboard (`linebot_onboard.ino`) or receive motor commands from ROS2 (`linebot.ino`). Telemetry is published on ROS2 topics:

- `/sensor_data` — raw sensor readings
- `/line_error` — computed line position error
- `/pid_terms` — PID terms
- `/motor_pwm` — motor PWM values

Two ROS2 launch modes are provided:

- `telemetry_only.launch.py` — Arduino runs PID onboard; ROS2 only listens.
- `line_follower.launch.py` — ROS2 runs PID and sends motor commands to Arduino.

## Hardware Requirements

| Component | Notes |
|-----------|-------|
| Arduino Uno | R3 or compatible, VID:PID `2341:0043` or `2341:0069` |
| L298N dual H-bridge motor driver | Drives two DC motors |
| 2× DC motors + robot chassis | Differential-drive chassis |
| 3× TCRT5000 analog line sensors | Left, Center, Right |
| Breadboard + jumper wires | For power/signal distribution |
| USB cable | Arduino ↔ laptop; keep it short and reliable |
| Lenovo Windows laptop (or equivalent) | Host for WSL2 + ROS2 |
| 7–12 V battery pack | Powers motors through the L298N |

## Software Requirements

### Windows (host)

- Windows 10 or Windows 11 with WSL2 enabled
- [Arduino IDE](https://www.arduino.cc/en/software) (or Arduino CLI)
- [usbipd-win](https://github.com/dorssel/usbipd-win) for USB passthrough to WSL
- Git for Windows (or Git inside WSL)

### WSL2 (Ubuntu)

- Ubuntu 22.04 or 24.04
- ROS2 Jazzy Jalisco ([official install guide](https://docs.ros.org/en/jazzy/Installation.html))
- Python packages: `pyserial`
  ```bash
  sudo apt install python3-serial
  ```

## Wiring / Assembly

### TCRT5000 sensors → Arduino

| Sensor | Arduino pin |
|--------|-------------|
| Left analog output | A0 |
| Center analog output | A1 |
| Right analog output | A2 |
| VCC | 5 V |
| GND | GND |

If your sensors have a digital output, ignore it for this firmware; only the analog outputs are used.

### L298N motor driver → Arduino

| L298N | Arduino pin |
|-------|-------------|
| ENA | D5 (PWM) |
| IN1 | D6 |
| IN2 | D7 |
| IN3 | D8 |
| IN4 | D9 |
| ENB | D10 (PWM) |
| +12 V | Battery positive |
| GND | Battery negative **and** Arduino GND |
| +5 V | Not used (unless powering logic) |

### Motors → L298N

| Motor | L298N output |
|-------|--------------|
| Left motor | OUT1 / OUT2 |
| Right motor | OUT3 / OUT4 |

> **Important:** The L298N GND pin must be connected to both the battery negative **and** the Arduino GND for a common reference.

## Windows Setup

1. **Install Arduino IDE**
   Download and install from <https://www.arduino.cc/en/software>.

2. **Install usbipd-win**
   In PowerShell **as Administrator**:
   ```powershell
   winget install usbipd
   ```
   Then reboot if prompted.

3. **Verify WSL2 is installed**
   ```powershell
   wsl --version
   ```
   If WSL2 is not installed, follow Microsoft's guide first.

## WSL2 Setup

1. **Install ROS2 Jazzy**
   Follow the official guide: <https://docs.ros.org/en/jazzy/Installation.html>

2. **Install required tools**
   ```bash
   sudo apt update
   sudo apt install -y python3-pip python3-serial git
   ```

3. **Add your user to the `dialout` group** (optional but recommended)
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Log out and back in for this to take effect.

## Clone the Repository

You will have two copies: one on Windows for editing, and one in WSL for running.

### Windows (editing copy)

```powershell
cd C:\
git clone https://github.com/Vishalnar26/linebot.git
```

### WSL (runtime copy)

```bash
cd ~
git clone https://github.com/Vishalnar26/linebot.git
```

## Upload Arduino Firmware

1. Open the Arduino IDE on Windows.
2. Connect the Arduino Uno via USB.
3. Select the correct COM port under **Tools → Port**.
4. Open the desired firmware:
   - For onboard PID (telemetry only): `arduino/linebot/linebot_onboard.ino`
   - For host PID (ROS2 controls motors): `arduino/linebot/linebot.ino`
5. Click **Upload**.
6. Open **Tools → Serial Monitor** at `115200` baud and confirm telemetry lines appear, e.g.:
   ```
   A_Raw:469,513,142 E:-0.291 P:-44 D:-6 PWM:50,150
   ```

## Pass USB Through to WSL2

1. In PowerShell **as Administrator**, list USB devices:
   ```powershell
   usbipd list
   ```
   Find the Arduino Uno bus ID (e.g. `2-3`).

2. Bind the device (one-time):
   ```powershell
   usbipd bind --busid 2-3
   ```

3. Attach to WSL:
   ```powershell
   usbipd attach --wsl --busid 2-3 --auto-attach
   ```

4. Inside WSL, verify the device appears:
   ```bash
   ls /dev/ttyACM* /dev/ttyUSB*
   ```
   Typical output: `/dev/ttyACM0`

5. Fix permissions:
   ```bash
   sudo chmod 666 /dev/ttyACM0
   ```

6. Test raw serial output:
   ```bash
   stty -F /dev/ttyACM0 -hupcl
   cat /dev/ttyACM0
   ```
   Press `Ctrl+C` to stop. You should see telemetry lines.

> **Why `-hupcl`?** This disables DTR reset on port open, which can destabilize the Arduino over USB/IP. The ROS2 bridge already opens the port with equivalent flags.

## Build the ROS2 Workspace

Run inside WSL:

```bash
cd ~/linebot/linebot_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

After every `git pull`, rebuild:

```bash
cd ~/linebot/linebot_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## Run the Robot

### Option 1 — Onboard PID (telemetry only)

Use this when the Arduino handles line following itself and you only want to observe telemetry.

```bash
source /opt/ros/jazzy/setup.bash
source ~/linebot/linebot_ws/install/setup.bash
ros2 launch line_follower telemetry_only.launch.py serial_port:=/dev/ttyACM0
```

If the device appears as `/dev/ttyACM1`, use that instead:

```bash
ros2 launch line_follower telemetry_only.launch.py serial_port:=/dev/ttyACM1
```

### Option 2 — Host PID (ROS2 controls motors)

Upload `arduino/linebot/linebot.ino` first, then run:

```bash
source /opt/ros/jazzy/setup.bash
source ~/linebot/linebot_ws/install/setup.bash
ros2 launch line_follower line_follower.launch.py serial_port:=/dev/ttyACM0
```

## View Telemetry

In a new WSL terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/linebot/linebot_ws/install/setup.bash
```

Then echo any topic:

```bash
ros2 topic echo /sensor_data
ros2 topic echo /line_error
ros2 topic echo /pid_terms
ros2 topic echo /motor_pwm
```

To list active topics and nodes:

```bash
ros2 topic list
ros2 node list
```

## Troubleshooting

### `Serial read error: device reports readiness to read but returned no data`

- The port opened successfully but the USB/IP link dropped one URB.
- The bridge node retries automatically; if it recovers and detects telemetry, the error is harmless.
- If it repeats continuously, proceed to the next steps.

### Arduino keeps re-enumerating as `/dev/ttyACM1`

- Use that port name in the launch command.
- Check the USB cable and port; try a different cable or a powered USB hub.

### `cat /dev/ttyACM0` shows nothing

1. Detach the device in PowerShell:
   ```powershell
   usbipd detach --busid 2-3
   ```
2. Re-upload the firmware from the Arduino IDE on Windows.
3. Re-attach:
   ```powershell
   usbipd attach --wsl --busid 2-3 --auto-attach
   ```
4. Test `cat /dev/ttyACM0` again.

### `usbipd list` shows `DFU-RT Port`

The Arduino entered bootloader/DFU mode. Detach it, re-upload the firmware from Windows, and re-attach.

### Permission denied on `/dev/ttyACM0`

Run:

```bash
sudo chmod 666 /dev/ttyACM0
```

Or add your user to the `dialout` group and restart WSL:

```bash
sudo usermod -a -G dialout $USER
wsl --shutdown
```

### Windows-side TCP bridge fallback

If `usbipd` cannot be made stable, keep the Arduino on Windows and stream serial data over TCP into WSL. A helper script can be added on request.

### Workflow reminder

- Edit files in `C:\linebot` on Windows.
- Commit and push from Windows:
  ```powershell
  cd C:\linebot
  git add .
  git commit -m "..."
  git push
  ```
- Pull and rebuild in WSL:
  ```bash
  cd ~/linebot
  git pull
  cd linebot_ws
  source /opt/ros/jazzy/setup.bash
  colcon build --symlink-install
  source install/setup.bash
  ```

---

For USB/IP details, see [Microsoft's WSL USB documentation](https://learn.microsoft.com/windows/wsl/connect-usb).