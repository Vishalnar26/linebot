#!/usr/bin/env python3
"""Serial bridge node: opens serial to Arduino and publishes /sensor_data; subscribes /cmd_pwm to send raw P: commands

This node assumes the Arduino firmware sends lines like:
  D:L,C,R|A:L,C,R\n
and accepts commands of the form:
  P:left_pwm,right_pwm\n
"""
import threading
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray
from geometry_msgs.msg import Twist

try:
    import serial
except Exception:
    serial = None


class SerialBridgeNode(Node):
    def __init__(self):
        super().__init__('serial_bridge')
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baud_rate', 115200)

        port = self.get_parameter('serial_port').get_parameter_value().string_value
        baud = self.get_parameter('baud_rate').get_parameter_value().integer_value

        if serial is None:
            self.get_logger().fatal('pyserial not available; install python3-serial')
            raise RuntimeError('pyserial missing')

        try:
            self._ser = serial.Serial(port, baud, timeout=1.0)
            self.get_logger().info(f'Opened serial {port} @ {baud}')
        except serial.SerialException as exc:
            self.get_logger().fatal(f'Failed to open serial port: {exc}')
            raise

        self._pub = self.create_publisher(Int32MultiArray, '/sensor_data', 10)
        self._cmd_sub = self.create_subscription(Twist, '/cmd_vel', self._cmd_vel_cb, 10)

        self._read_thread = threading.Thread(target=self._reader, daemon=True)
        self._read_thread.start()

    def _reader(self):
        while rclpy.ok():
            try:
                raw = self._ser.readline()
                if not raw:
                    continue
                line = raw.decode('ascii', errors='ignore').strip()
                self._parse_line(line)
            except Exception as exc:
                self.get_logger().error(f'Serial read error: {exc}')
                break

    def _parse_line(self, line: str):
        # Expected: D:L,C,R|A:L,C,R
        if not line.startswith('D:') or '|' not in line:
            return
        try:
            d_part, a_part = line.split('|', 1)
            d_vals = [int(v) for v in d_part[2:].split(',')]
            a_vals = [int(v) for v in a_part[2:].split(',')]
            if len(d_vals) != 3 or len(a_vals) != 3:
                return
            msg = Int32MultiArray()
            msg.data = d_vals + a_vals
            self._pub.publish(msg)
        except Exception:
            return

    def _cmd_vel_cb(self, msg: Twist):
        # Map linear.x & angular.z to differential PWM and send P:left,right\n
        # User can publish directly to /cmd_vel. We'll map using fixed MAX_SPEED/MAX_ANG.
        MAX_SPEED = 0.2
        MAX_ANG = 2.0
        base_pwm = int(max(-1.0, min(1.0, msg.linear.x / MAX_SPEED)) * 255)
        corr = int(max(-1.0, min(1.0, msg.angular.z / MAX_ANG)) * 255)
        left = base_pwm + corr
        right = base_pwm - corr
        left = max(-255, min(255, left))
        right = max(-255, min(255, right))
        cmd = f'P:{left},{right}\n'
        try:
            self._ser.write(cmd.encode('ascii'))
        except Exception as exc:
            self.get_logger().error(f'Serial write error: {exc}')

    def destroy_node(self):
        try:
            if self._ser and self._ser.is_open:
                self._ser.write(b'P:0,0\n')
                self._ser.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
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
