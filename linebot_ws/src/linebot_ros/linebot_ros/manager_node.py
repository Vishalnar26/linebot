#!/usr/bin/env python3
"""Manager node: provides services to start/stop, monitor telemetry, and set parameters."""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray
from geometry_msgs.msg import Twist
from std_srvs.srv import SetBool


class ManagerNode(Node):
    def __init__(self):
        super().__init__('linebot_manager')
        # runtime state
        self.latest_sensors = None
        self.running = False

        self.create_subscription(Int32MultiArray, '/sensor_data', self._sensor_cb, 10)
        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # services: start/stop (SetBool) where data=true -> start
        self.create_service(SetBool, 'start_stop', self._start_stop_cb)

        # timer for publishing keepalive commands while running (prevents Arduino timeout)
        self.create_timer(0.1, self._keepalive)

    def _sensor_cb(self, msg: Int32MultiArray):
        self.latest_sensors = msg.data

    def _start_stop_cb(self, request, response):
        self.running = bool(request.data)
        response.success = True
        response.message = 'running' if self.running else 'stopped'
        return response

    def _keepalive(self):
        # publish small command if running to prevent Arduino safety stop
        if self.running:
            t = Twist()
            t.linear.x = 0.05
            t.angular.z = 0.0
            self._cmd_pub.publish(t)


def main(args=None):
    rclpy.init(args=args)
    node = ManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
