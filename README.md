# LineBot ROS2 Telemetry

A line-following robot controlled by an Arduino Uno and observed through ROS2 Jazzy running inside WSL2 on a Windows laptop.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Hardware Requirements](#hardware-requirements)
4. [Software Requirements](#software-requirements)
5. [Wiring / Assembly](#wiring--assembly)
6. [Windows Setup](#windows-setup)
7. [WSL2 Setup](#wsl2-setup)
8. [Clone the Repository](#clone-the-repository)
9. [Upload Arduino Firmware](#upload-arduino-firmware)
10. [Pass USB Through to WSL2](#pass-usb-through-to-wsl2)
11. [Build the ROS2 Workspace](#build-the-ros2-workspace)
12. [Step-by-Step Execution Process](#step-by-step-execution-process)
13. [Run the Robot](#run-the-robot)
14. [View Telemetry](#view-telemetry)
15. [Troubleshooting](#troubleshooting)

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

## Prerequisites

Before starting, make sure every component below is available and its dependencies are installed.

| Component | Purpose | Required dependencies |
|-----------|---------|----------------------|
| Robot electronics | Arduino Uno + L298N + 2 DC motors + 3 TCRT5000 sensors + battery | Correct wiring (see [Wiring / Assembly](#wiring--assembly)) |
| Windows laptop | Host OS for WSL2 and Arduino IDE | Windows 10/11, WSL2 enabled, Administrator access |
| Arduino IDE / CLI | Compile and upload firmware | Arduino IDE, USB cable, Arduino drivers |
| `usbipd-win` | Pass USB devices into WSL2 | Installed via `winget`, PowerShell as Administrator |
| WSL2 Ubuntu | Runtime environment for ROS2 | Ubuntu 22.04 or 24.04 distro |
| ROS2 Jazzy | Robotics middleware | Installed inside WSL2 per the official guide |
| `linebot_ws` | ROS2 workspace containing nodes and launch files | Git, `colcon`, `python3-serial` |
| Serial bridge node | Reads Arduino telemetry and publishes ROS2 topics | `pyserial`, readable `/dev/ttyACM*` port |

All dependency installations must be complete before you run the execution steps below.

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

## Step-by-Step Execution Process

Follow this exact order on a fresh system or after a full restart.

### 1. Prepare the hardware

- Wire the motors, L298N, sensors, and battery as described in [Wiring / Assembly](#wiring--assembly).
- Connect the Arduino Uno to the Windows laptop with a USB cable.

### 2. Prepare Windows

- Install the [Arduino IDE](https://www.arduino.cc/en/software).
- Install `usbipd-win`:
  ```powershell
  winget install usbipd
  ```
- Reboot if prompted.
- Verify WSL2 is installed:
  ```powershell
  wsl --version
  ```

### 3. Prepare WSL2

- Install ROS2 Jazzy inside WSL2.
- Install required packages:
  ```bash
  sudo apt update
  sudo apt install -y python3-pip python3-serial git
  ```
- Add yourself to the `dialout` group:
  ```bash
  sudo usermod -a -G dialout $USER
  ```
  Then restart WSL or log out and back in.

### 4. Clone the repository

- Windows editing copy:
  ```powershell
  cd C:\
  git clone https://github.com/Vishalnar26/linebot.git
  ```
- WSL runtime copy:
  ```bash
  cd ~
  git clone https://github.com/Vishalnar26/linebot.git
  ```

### 5. Upload the Arduino firmware

- Open Arduino IDE on Windows.
- Select the correct COM port.
- Open `arduino/linebot/linebot_onboard.ino` (telemetry only) or `arduino/linebot/linebot.ino` (host PID).
- Click **Upload**.
- Open the Serial Monitor at `115200` baud and confirm telemetry lines appear.

### 6. Pass the Arduino USB device into WSL2

- PowerShell as Administrator:
  ```powershell
  usbipd list
  usbipd bind --busid 2-3
  usbipd attach --wsl --busid 2-3 --auto-attach
  ```
- In WSL:
  ```bash
  ls /dev/ttyACM* /dev/ttyUSB*
  sudo chmod 666 /dev/ttyACM0
  stty -F /dev/ttyACM0 -hupcl
  cat /dev/ttyACM0
  ```
  Press `Ctrl+C` after confirming telemetry output.

### 7. Build the ROS2 workspace

```bash
cd ~/linebot/linebot_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### 8. Launch the robot

- Onboard PID / telemetry only:
  ```bash
  ros2 launch line_follower telemetry_only.launch.py serial_port:=/dev/ttyACM0
  ```
- Host PID / ROS2-controlled:
  ```bash
  ros2 launch line_follower line_follower.launch.py serial_port:=/dev/ttyACM0
  ```

### 9. View telemetry

- In a second WSL terminal:
  ```bash
  source /opt/ros/jazzy/setup.bash
  source ~/linebot/linebot_ws/install/setup.bash
  ros2 topic echo /sensor_data
  ```
- Repeat for `/line_error`, `/pid_terms`, `/motor_pwm` as needed.

If any step fails, see [Troubleshooting](#troubleshooting) before continuing.

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