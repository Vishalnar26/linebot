#!/usr/bin/env python3
"""
linebot_manager_node — ROS2 manager
Provides simple high-level control: START, STOP, set SPEED via `/linebot_manager/cmd` (std_msgs/String).
Uses `/cmd_vel` to control motors and `/line_error` to monitor behavior. It can set controller parameters via ROS param CLI (documented) but does not call ros2param directly.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Int32MultiArray
from geometry_msgs.msg import Twist


class LinebotManager(Node):
    def __init__(self) -> None:
        super().__init__('linebot_manager')

        # Parameters
        self.declare_parameter('safe_base_speed', 0.05)
        self._safe_base_speed = self.get_parameter('safe_base_speed').get_parameter_value().double_value

        # Publishers/subscribers
        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._sensor_sub = self.create_subscription(Int32MultiArray, '/sensor_data', self._sensor_cb, 10)
        self._line_err_sub = self.create_subscription(Float32, '/line_error', self._line_err_cb, 10)
        self._cmd_sub = self.create_subscription(String, '/linebot_manager/cmd', self._cmd_cb, 10)

        self._last_sensor = None
        self._last_error = 0.0
        self._enabled = False

        self.get_logger().info('LinebotManager ready — publish String commands to /linebot_manager/cmd')

    def _sensor_cb(self, msg: Int32MultiArray) -> None:
        self._last_sensor = list(msg.data[:3]) if len(msg.data) >= 3 else None

    def _line_err_cb(self, msg: Float32) -> None:
        self._last_error = msg.data

    def _cmd_cb(self, msg: String) -> None:
        cmd = msg.data.strip()
        if not cmd:
            return
        cmd_up = cmd.upper()
        if cmd_up == 'START':
            self._enabled = True
            # recommend using `ros2 param set /line_follower_controller base_speed <val>` externally
            self.get_logger().info('START received — enabling controller (manager does not override controller loop)')
        elif cmd_up == 'STOP':
            self._enabled = False
            # publish immediate stop
            twist = Twist()
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            self._cmd_vel_pub.publish(twist)
            self.get_logger().info('STOP received — published zero /cmd_vel')
        elif cmd_up.startswith('SPEED:'):
            try:
                val = float(cmd.split(':', 1)[1])
                # Set controller base_speed via ros2 param externally; we just log suggestion
                self.get_logger().info(f'Request to set base_speed={val:.3f} received — run `ros2 param set /line_follower_controller base_speed {val}`')
            except Exception as exc:
                self.get_logger().error(f'Invalid SPEED value: {exc}')
        else:
            self.get_logger().warn(f'Unknown manager command: "{cmd}"')


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LinebotManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
