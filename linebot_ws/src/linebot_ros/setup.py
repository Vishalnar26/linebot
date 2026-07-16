from setuptools import setup

package_name = 'linebot_ros'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='You',
    maintainer_email='you@example.com',
    description='ROS2 nodes for LineBot',
    license='MIT',
    classifiers=['Programming Language :: Python :: 3'],
    entry_points={
        'console_scripts': [
            'serial_bridge = linebot_ros.serial_bridge_node:main',
            'manager = linebot_ros.manager_node:main',
        ],
    },
)
