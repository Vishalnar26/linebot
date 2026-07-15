"""
Launch file for the LineBot line follower.

Starts two nodes:
  1. serial_bridge_node        — Arduino Uno ↔ ROS2 USB serial bridge
  2. line_follower_controller  — host-side PID controller

Override the serial port at launch time if needed:
  ros2 launch line_follower line_follower.launch.py serial_port:=/dev/ttyACM0
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg_share  = get_package_share_directory('line_follower')
    pid_config = os.path.join(pkg_share, 'config', 'pid_params.yaml')

    # ── Launch argument: serial port ─────────────────────────────────────────
    serial_port_arg = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/ttyUSB0',
        description=(
            'Serial port the Arduino Uno is connected to. '
            'Common values: /dev/ttyUSB0, /dev/ttyACM0'
        ),
    )

    # ── Node: serial bridge ───────────────────────────────────────────────────
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

    # ── Node: PID controller ──────────────────────────────────────────────────
    controller_node = Node(
        package='line_follower',
        executable='line_follower_controller',
        name='line_follower_controller',
        parameters=[pid_config],
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([
        serial_port_arg,
        serial_bridge_node,
        controller_node,
    ])
