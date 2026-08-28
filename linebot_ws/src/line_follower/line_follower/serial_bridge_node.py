#!/usr/bin/env python3
"""
serial_bridge_node — ROS2 Jazzy
Bridges the Arduino Uno and ROS2 over USB serial.

Serial protocols (auto-detected)
--------------------------------
1. Host-side PID firmware [linebot.ino]:
   Arduino → PC  (every 50 ms):   D:L,C,R|A:L,C,R\\n
     L/C/R digital: 0 = white (LED on)  |  1 = black (LED off)
     L/C/R analog:  0–1023
     Order: Left, Center, Right

   PC → Arduino  (on /cmd_vel):   P:left_pwm,right_pwm\\n

2. Onboard PID firmware [linebot_onboard.ino]:
   Arduino → PC  (every ~150 ms):  A_Raw:L,C,R E:err P:p D:d PWM:left,right\\n
     L/C/R analog: 0–1023
     err: line error in [-1, +1]
     p/d: proportional/derivative PID contributions (PWM units)
     left/right: current motor PWM values

   In this mode the Arduino ignores P: commands (PID runs onboard).

ROS2 interfaces
---------------
  Published :  /sensor_data  (std_msgs/Int32MultiArray)
                 host PID mode: [left_dig, center_dig, right_dig,
                                 left_ana, center_ana, right_ana]
                 onboard mode:  [left_ana, center_ana, right_ana]
               /line_error   (std_msgs/Float32)      — line position error
               /pid_terms    (std_msgs/Float32MultiArray)
                 host PID mode: computed by controller node
                 onboard mode:  [p_term, 0.0, d_term] from telemetry
               /motor_pwm    (std_msgs/Int32MultiArray)
                 onboard mode only: [left_pwm, right_pwm]

  Subscribed:  /cmd_vel      (geometry_msgs/Twist)  — used only by host-PID mode
               linear.x  → base speed   (0 … MAX_SPEED m/s → 0 … 255 PWM)
               angular.z → differential (−MAX_ANGULAR … +MAX_ANGULAR rad/s)

Parameters
----------
  serial_port  (string)  default: /dev/ttyUSB0
  baud_rate    (int)     default: 115200
"""

import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray, Float32, Float32MultiArray
from geometry_msgs.msg import Twist

try:
    import serial
except ImportError as exc:
    raise SystemExit(
        "pyserial is not installed.  "
        "Run:  sudo apt install python3-serial"
    ) from exc

# Mapping limits: these match pid_params.yaml / controller defaults
MAX_SPEED   = 0.2   # m/s  → PWM 255
MAX_ANGULAR = 2.0   # rad/s → PWM 255


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class SerialBridgeNode(Node):

    def __init__(self) -> None:
        super().__init__('serial_bridge_node')

        # ── Parameters ────────────────────────────────────────────────────────
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)

        port      = self.get_parameter('serial_port').get_parameter_value().string_value
        baud_rate = self.get_parameter('baud_rate').get_parameter_value().integer_value

        # ── Serial connection ─────────────────────────────────────────────────
        # dsrdtr=False / rtscts=False keeps DTR/RTS de-asserted so the Arduino
        # does not reset when the port is opened.  This is critical when the
        # device is passed through usbipd-win, because the reset can cause the
        # virtual USB device to re-enumerate or drop off the bus.
        try:
            self._serial = serial.Serial(
                port, baud_rate, timeout=1.0,
                dsrdtr=False, rtscts=False
            )
            self.get_logger().info(
                f'Serial port opened: {port} @ {baud_rate} baud'
            )
        except serial.SerialException as exc:
            self.get_logger().fatal(f'Cannot open serial port "{port}": {exc}')
            raise

        # ── Publishers ────────────────────────────────────────────────────────
        self._sensor_pub = self.create_publisher(
            Int32MultiArray, '/sensor_data', 10
        )
        self._line_error_pub = self.create_publisher(
            Float32, '/line_error', 10
        )
        self._pid_terms_pub = self.create_publisher(
            Float32MultiArray, '/pid_terms', 10
        )
        self._motor_pwm_pub = self.create_publisher(
            Int32MultiArray, '/motor_pwm', 10
        )

        # ── Subscriber: velocity commands ─────────────────────────────────────
        self._cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self._cmd_vel_callback, 10
        )

        # Protocol auto-detection state
        self._protocol_onboard = None  # None = unknown, True = onboard PID mode

        # ── Background serial-reader thread ───────────────────────────────────
        self._read_thread = threading.Thread(
            target=self._serial_reader, daemon=True, name='serial_reader'
        )
        self._read_thread.start()

        self.get_logger().info('SerialBridgeNode ready.')

    # ── Background serial reader ──────────────────────────────────────────────
    def _serial_reader(self) -> None:
        """Read lines from the serial port and publish sensor data."""
        while rclpy.ok():
            try:
                raw = self._serial.readline()          # blocks up to timeout=1 s
                if not raw:
                    continue
                line = raw.decode('ascii', errors='ignore').strip()
                if line:
                    self._parse_and_publish(line)
            except serial.SerialException as exc:
                self.get_logger().error(f'Serial read error: {exc}')
                # Do not kill the node; wait and retry so transient USB
                # disconnects can recover without restarting the launch.
                import time
                time.sleep(0.5)
                continue

    # ── Sensor line parser ────────────────────────────────────────────────────
    def _parse_and_publish(self, line: str) -> None:
        """
        Auto-detect and parse either:
          D:L,C,R|A:L,C,R        (host-PID firmware)
          A_Raw:L,C,R E:err P:p D:d PWM:left,right  (onboard PID firmware)
        """
        try:
            if line.startswith('A_Raw:'):
                if self._protocol_onboard is not True:
                    self._protocol_onboard = True
                    self.get_logger().info('Detected onboard-PID telemetry protocol')
                self._parse_onboard(line)
            elif line.startswith('D:') and '|' in line:
                if self._protocol_onboard is not False:
                    self._protocol_onboard = False
                    self.get_logger().info('Detected host-PID telemetry protocol')
                self._parse_host_pid(line)
            else:
                self.get_logger().debug(f'Unrecognised line ignored: "{line}"')
        except (ValueError, IndexError, KeyError) as exc:
            self.get_logger().debug(
                f'Malformed sensor line ignored: "{line}" ({exc})'
            )

    def _parse_host_pid(self, line: str) -> None:
        """Parse D:L,C,R|A:L,C,R and publish /sensor_data."""
        d_part, a_part = line.split('|', 1)
        d_vals = [int(v) for v in d_part[2:].split(',')]   # skip "D:"
        a_vals = [int(v) for v in a_part[2:].split(',')]   # skip "A:"

        if len(d_vals) != 3 or len(a_vals) != 3:
            return

        msg = Int32MultiArray()
        # [left_dig, center_dig, right_dig, left_ana, center_ana, right_ana]
        msg.data = d_vals + a_vals
        self._sensor_pub.publish(msg)

    def _parse_onboard(self, line: str) -> None:
        """
        Parse A_Raw:L,C,R E:err P:p D:d PWM:left,right
        and publish sensor_data, line_error, pid_terms, motor_pwm.
        """
        # line example: A_Raw:469,513,142 E:-0.291 P:-44 D:-6 PWM:50,150
        parts = line.split()
        data = {}
        for part in parts:
            if ':' in part:
                key, value = part.split(':', 1)
                data[key] = value

        a_vals = [int(v) for v in data['A_Raw'].split(',')]
        error = float(data['E'])
        p_term = float(data['P'])
        d_term = float(data['D'])
        pwm_vals = [int(v) for v in data['PWM'].split(',')]

        if len(a_vals) != 3 or len(pwm_vals) != 2:
            return

        sensor_msg = Int32MultiArray()
        sensor_msg.data = a_vals
        self._sensor_pub.publish(sensor_msg)

        error_msg = Float32()
        error_msg.data = error
        self._line_error_pub.publish(error_msg)

        pid_msg = Float32MultiArray()
        pid_msg.data = [p_term, 0.0, d_term]
        self._pid_terms_pub.publish(pid_msg)

        pwm_msg = Int32MultiArray()
        pwm_msg.data = pwm_vals
        self._motor_pwm_pub.publish(pwm_msg)

    # ── /cmd_vel → serial PWM command ────────────────────────────────────────
    def _cmd_vel_callback(self, msg: Twist) -> None:
        """
        Convert Twist to signed PWM values and send to the Arduino.

        Differential drive:
          base_pwm   = linear.x  / MAX_SPEED   * 255
          correction = angular.z / MAX_ANGULAR * 255
          left_pwm   = base_pwm + correction
          right_pwm  = base_pwm − correction
        """
        base_pwm   = _clamp(msg.linear.x  / MAX_SPEED   * 255.0, -255.0, 255.0)
        correction = _clamp(msg.angular.z / MAX_ANGULAR * 255.0, -255.0, 255.0)

        left_pwm  = int(_clamp(base_pwm + correction, -255.0, 255.0))
        right_pwm = int(_clamp(base_pwm - correction, -255.0, 255.0))

        cmd = f'P:{left_pwm},{right_pwm}\n'
        try:
            self._serial.write(cmd.encode('ascii'))
        except serial.SerialException as exc:
            self.get_logger().error(f'Serial write error: {exc}')

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def destroy_node(self) -> None:
        if self._serial.is_open:
            # Send a stop command before closing
            try:
                self._serial.write(b'P:0,0\n')
            except serial.SerialException:
                pass
            self._serial.close()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SerialBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
