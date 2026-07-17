from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'line_follower'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        # ament package index marker
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        # package.xml
        ('share/' + package_name, ['package.xml']),
        # launch files
        (
            os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py'),
        ),
        # config files
        (
            os.path.join('share', package_name, 'config'),
            glob('config/*.yaml'),
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Vishal Narayanan',
    maintainer_email='vishal@linebot.local',
    description=(
        'ROS2 Jazzy line follower — serial bridge + PID controller for LineBot.'
    ),
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'serial_bridge = line_follower.serial_bridge_node:main',
            'line_follower_controller = line_follower.line_follower_controller_node:main',
            'linebot_manager = line_follower.linebot_manager_node:main',
        ],
    },
)
