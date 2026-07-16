from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    serial_node = Node(
        package='linebot_ros',
        executable='serial_bridge',
        name='serial_bridge',
        parameters=[{'serial_port': '/dev/ttyACM0', 'baud_rate': 115200}],
    )

    manager_node = Node(
        package='linebot_ros',
        executable='manager',
        name='linebot_manager',
    )

    return LaunchDescription([serial_node, manager_node])
