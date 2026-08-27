"""
Telemetry-only launch for onboard PID firmware.

Starts only the serial_bridge_node so ROS2 can receive sensor data,
line error, PID terms, and motor PWM values from the Arduino.

The Arduino is expected to run linebot_onboard.ino, which performs PID
control onboard and prints:
  A_Raw:L,C,R E:err P:p D:d PWM:left,right

Use this launch file instead of line_follower.launch.py when the robot
already handles line following on the Arduino and you only want telemetry.

Override the serial port at launch time if needed:
  ros2 launch line_follower telemetry_only.launch.py serial_port:=/dev/ttyACM0
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    # ── Launch argument: serial port ─────────────────────────────────────────
    serial_port_arg = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/ttyACM0',
        description=(
            'Serial port the Arduino Uno is connected to. '
            'Common values: /dev/ttyUSB0, /dev/ttyACM0'
        ),
    )

    # ── Node: serial bridge (telemetry only) ────────────────────────────────
    serial_bridge_node = Node(
        package='line_follower',
        executable='serial_bridge',
        name='serial_bridge_node',
        parameters=[
            {
                'serial_port': LaunchConfiguration('serial_port'),
                'baud_rate': 115200,
            }
        ],
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([
        serial_port_arg,
        serial_bridge_node,
    ])
