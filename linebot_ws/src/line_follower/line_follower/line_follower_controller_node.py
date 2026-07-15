#!/usr/bin/env python3
"""
line_follower_controller_node — ROS2 Jazzy
Host-side PID controller for the LineBot line-follower robot.

Subscribed :  /sensor_data  (std_msgs/Int32MultiArray)
              [left_dig, center_dig, right_dig, left_ana, center_ana, right_ana]
              digital values: 1 = black (on line),  0 = white (off line)

Published  :  /cmd_vel      (geometry_msgs/Twist)   — motor velocity command
              /line_error   (std_msgs/Float32)       — weighted position error
              /intersection (std_msgs/Bool)          — True when all 3 sensors = 1

Error convention
----------------
  error < 0  →  line is to the LEFT   →  steer left  (angular.z becomes positive)
  error = 0  →  line is centred       →  drive straight
  error > 0  →  line is to the RIGHT  →  steer right (angular.z becomes negative)

Recovery behaviour
------------------
  If all sensors read 0 (robot is fully off the line), the controller preserves
  the sign of the last known error and uses maximum correction magnitude (±1.0)
  so the robot spins back toward the line.

Parameters (set via config/pid_params.yaml)
-------------------------------------------
  kp                float   Proportional gain        default: 1.0
  ki                float   Integral gain            default: 0.0
  kd                float   Derivative gain          default: 0.5
  base_speed        float   Forward speed (m/s)      default: 0.1
  max_angular_speed float   Max angular vel (rad/s)  default: 2.0
"""

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Bool, Int32MultiArray
from geometry_msgs.msg import Twist


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ─── PID Controller ───────────────────────────────────────────────────────────

class PIDController:
    """
    Discrete-time PID with:
      - Anti-windup via integral clamping
      - Derivative on error (standard form)
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        integral_limit: float = 1.0,
    ) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral_limit = integral_limit

        self._integral   = 0.0
        self._prev_error = 0.0
        self._last_time: float | None = None

    def reset(self) -> None:
        self._integral   = 0.0
        self._prev_error = 0.0
        self._last_time  = None

    def update(self, error: float) -> float:
        now = time.monotonic()

        if self._last_time is None:
            # First call — no derivative yet
            self._last_time  = now
            self._prev_error = error
            return self.kp * error

        dt = now - self._last_time
        if dt <= 0.0:
            return self.kp * error

        # Proportional term
        p_term = self.kp * error

        # Integral term with anti-windup
        self._integral = _clamp(
            self._integral + error * dt,
            -self._integral_limit,
            self._integral_limit,
        )
        i_term = self.ki * self._integral

        # Derivative term
        d_term = self.kd * (error - self._prev_error) / dt

        self._prev_error = error
        self._last_time  = now

        return p_term + i_term + d_term


# ─── Controller Node ──────────────────────────────────────────────────────────

class LineFollowerControllerNode(Node):

    def __init__(self) -> None:
        super().__init__('line_follower_controller')

        # ── Parameters ────────────────────────────────────────────────────────
        self.declare_parameter('kp',                1.0)
        self.declare_parameter('ki',                0.0)
        self.declare_parameter('kd',                0.5)
        self.declare_parameter('base_speed',        0.1)
        self.declare_parameter('max_angular_speed', 2.0)

        kp = self.get_parameter('kp').get_parameter_value().double_value
        ki = self.get_parameter('ki').get_parameter_value().double_value
        kd = self.get_parameter('kd').get_parameter_value().double_value
        self._base_speed  = self.get_parameter('base_speed').get_parameter_value().double_value
        self._max_angular = self.get_parameter('max_angular_speed').get_parameter_value().double_value

        # ── PID controller ────────────────────────────────────────────────────
        self._pid = PIDController(kp, ki, kd)
        self._last_error = 0.0   # used for lost-line recovery direction

        # ── Publishers ────────────────────────────────────────────────────────
        self._cmd_vel_pub      = self.create_publisher(Twist,   '/cmd_vel',      10)
        self._line_error_pub   = self.create_publisher(Float32, '/line_error',   10)
        self._intersection_pub = self.create_publisher(Bool,    '/intersection', 10)

        # ── Subscriber ────────────────────────────────────────────────────────
        self._sensor_sub = self.create_subscription(
            Int32MultiArray, '/sensor_data', self._sensor_callback, 10
        )

        self.get_logger().info(
            f'LineFollowerControllerNode started — '
            f'Kp={kp:.2f}  Ki={ki:.2f}  Kd={kd:.2f}  '
            f'base_speed={self._base_speed:.2f} m/s  '
            f'max_angular={self._max_angular:.2f} rad/s'
        )

    # ── /sensor_data callback ─────────────────────────────────────────────────
    def _sensor_callback(self, msg: Int32MultiArray) -> None:
        if len(msg.data) < 3:
            self.get_logger().warn(
                f'Expected at least 3 values in /sensor_data, got {len(msg.data)}'
            )
            return

        left   = int(msg.data[0])   # 1 = black / on-line
        center = int(msg.data[1])
        right  = int(msg.data[2])

        # ── Intersection detection ────────────────────────────────────────────
        # All three sensors on black → intersection (T-junction or crossing)
        at_intersection = (left == 1 and center == 1 and right == 1)
        int_msg = Bool()
        int_msg.data = at_intersection
        self._intersection_pub.publish(int_msg)

        # ── Weighted error ────────────────────────────────────────────────────
        # Sensor positions: LEFT = −1,  CENTER = 0,  RIGHT = +1
        # error < 0 → line is to the left  → need to steer left
        # error > 0 → line is to the right → need to steer right
        total = left + center + right

        if total == 0:
            # Robot is fully off the line — use last known direction at max magnitude
            error = 1.0 if self._last_error >= 0.0 else -1.0
        else:
            error = (-1.0 * left + 0.0 * center + 1.0 * right) / float(total)

        self._last_error = error

        # ── PID computation ───────────────────────────────────────────────────
        pid_output = _clamp(self._pid.update(error), -1.0, 1.0)

        # ── Publish /line_error ───────────────────────────────────────────────
        err_msg = Float32()
        err_msg.data = float(error)
        self._line_error_pub.publish(err_msg)

        # ── Publish /cmd_vel ──────────────────────────────────────────────────
        # angular.z sign convention:
        #   positive → turn left   (counter-clockwise)
        #   negative → turn right  (clockwise)
        #
        # error > 0 means line is to the right → we need angular.z < 0
        # Therefore:  angular.z = -pid_output * max_angular
        twist = Twist()

        if at_intersection:
            # Slow down at intersections; future higher-level logic can handle routing
            twist.linear.x  = self._base_speed * 0.5
            twist.angular.z = 0.0
        else:
            twist.linear.x  = self._base_speed
            twist.angular.z = -pid_output * self._max_angular

        self._cmd_vel_pub.publish(twist)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main(args=None) -> None:
    rclpy.init(args=args)
    node = LineFollowerControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
