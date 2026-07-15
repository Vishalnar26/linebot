#!/usr/bin/env python3
"""
Interactive script to generate an instruction file for a
Line Following Robot using ROS2 and Arduino Uno.
"""

import os
import json
from datetime import datetime

# ── Question definitions ────────────────────────────────────────────────────
QUESTIONS = [
    # 1. Project basics
    {
        "section": "Project Overview",
        "key": "project_name",
        "question": "1. What is the name of your project?",
        "hint": "e.g. LineBot, FollowMe, RoboTrack",
    },
    {
        "section": "Project Overview",
        "key": "author",
        "question": "2. Who is the author / team name?",
        "hint": "e.g. Vishal Narayanan",
    },
    {
        "section": "Project Overview",
        "key": "description",
        "question": "3. Briefly describe the robot's purpose.",
        "hint": "e.g. A differential-drive robot that follows a black line on a white surface.",
    },

    # 2. Hardware
    {
        "section": "Hardware",
        "key": "sensor_type",
        "question": "4. What type of line sensor(s) are you using?",
        "hint": "e.g. IR reflectance sensor array (QTR-8A), single TCRT5000, camera",
    },
    {
        "section": "Hardware",
        "key": "sensor_count",
        "question": "5. How many sensors / sensor channels?",
        "hint": "e.g. 5, 8",
    },
    {
        "section": "Hardware",
        "key": "motor_driver",
        "question": "6. Which motor driver are you using?",
        "hint": "e.g. L298N, L293D, TB6612FNG",
    },
    {
        "section": "Hardware",
        "key": "motor_type",
        "question": "7. What type of motors are on the robot?",
        "hint": "e.g. DC gear motors 200 RPM, stepper motors",
    },
    {
        "section": "Hardware",
        "key": "power_supply",
        "question": "8. What is the power supply for the robot?",
        "hint": "e.g. 7.4V 2S LiPo, 4×AA batteries",
    },
    {
        "section": "Hardware",
        "key": "communication",
        "question": "9. How does the Arduino communicate with the ROS2 host?",
        "hint": "e.g. USB Serial (rosserial / micro-ROS), Bluetooth HC-05, Wi-Fi ESP8266",
    },

    # 3. ROS2 Setup
    {
        "section": "ROS2 Setup",
        "key": "ros2_distro",
        "question": "10. Which ROS2 distribution are you using?",
        "hint": "e.g. Humble, Iron, Jazzy",
    },
    {
        "section": "ROS2 Setup",
        "key": "host_os",
        "question": "11. What OS is running on the ROS2 host machine?",
        "hint": "e.g. Ubuntu 22.04, Raspberry Pi OS (64-bit)",
    },
    {
        "section": "ROS2 Setup",
        "key": "workspace_name",
        "question": "12. What is the name of your ROS2 workspace?",
        "hint": "e.g. robot_ws, linebot_ws",
    },
    {
        "section": "ROS2 Setup",
        "key": "package_name",
        "question": "13. What is the main ROS2 package name?",
        "hint": "e.g. line_follower, linebot_controller",
    },
    {
        "section": "ROS2 Setup",
        "key": "topics",
        "question": "14. List the key ROS2 topics you plan to use (comma-separated).",
        "hint": "e.g. /sensor_data, /cmd_vel, /line_error, /odom",
    },

    # 4. Arduino Firmware
    {
        "section": "Arduino Firmware",
        "key": "arduino_library",
        "question": "15. Which Arduino/micro-ROS library are you using for ROS2 communication?",
        "hint": "e.g. micro_ros_arduino, rosserial_arduino",
    },
    {
        "section": "Arduino Firmware",
        "key": "control_algorithm",
        "question": "16. What control algorithm will the Arduino implement?",
        "hint": "e.g. PID, bang-bang, weighted average",
    },
    {
        "section": "Arduino Firmware",
        "key": "pid_params",
        "question": "17. Do you have initial PID tuning values? (Kp, Ki, Kd)",
        "hint": "e.g. Kp=1.2, Ki=0.0, Kd=0.8  — or 'TBD' if not yet tuned",
    },

    # 5. Software behaviour
    {
        "section": "Behaviour & Features",
        "key": "line_color",
        "question": "18. What color is the line on what background?",
        "hint": "e.g. Black line on white surface, white line on black surface",
    },
    {
        "section": "Behaviour & Features",
        "key": "speed",
        "question": "19. What is the target robot speed?",
        "hint": "e.g. 0.2 m/s, 150 PWM units",
    },
    {
        "section": "Behaviour & Features",
        "key": "extra_features",
        "question": "20. Any extra features or behaviours to include?",
        "hint": "e.g. intersection detection, obstacle avoidance, ROS2 dashboard, logging",
    },
]

# ── Helpers ─────────────────────────────────────────────────────────────────

def ask(q: dict) -> str:
    print(f"\n{'─'*60}")
    print(f"  Section : {q['section']}")
    print(f"  {q['question']}")
    print(f"  Hint    : {q['hint']}")
    while True:
        answer = input("  Your answer: ").strip()
        if answer:
            return answer
        print("  ⚠️  Answer cannot be empty. Please try again.")


def build_markdown(responses: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {responses.get('project_name', 'Line Following Robot')} — Instruction File",
        f"",
        f"> **Author:** {responses.get('author', 'N/A')}  ",
        f"> **Generated:** {now}  ",
        f"> **Platform:** ROS2 {responses.get('ros2_distro', '')} + Arduino Uno  ",
        f"",
        f"---",
        f"",
        f"## 1. Project Overview",
        f"",
        f"**Description:** {responses.get('description', '')}",
        f"",
        f"---",
        f"",
        f"## 2. Hardware Configuration",
        f"",
        f"| Component        | Details |",
        f"|------------------|---------|",
        f"| Line Sensor Type | {responses.get('sensor_type', '')} |",
        f"| Sensor Channels  | {responses.get('sensor_count', '')} |",
        f"| Motor Driver     | {responses.get('motor_driver', '')} |",
        f"| Motors           | {responses.get('motor_type', '')} |",
        f"| Power Supply     | {responses.get('power_supply', '')} |",
        f"| Arduino ↔ ROS2   | {responses.get('communication', '')} |",
        f"",
        f"---",
        f"",
        f"## 3. ROS2 Setup",
        f"",
        f"| Setting          | Value |",
        f"|------------------|-------|",
        f"| Distribution     | {responses.get('ros2_distro', '')} |",
        f"| Host OS          | {responses.get('host_os', '')} |",
        f"| Workspace        | `{responses.get('workspace_name', '')}` |",
        f"| Package Name     | `{responses.get('package_name', '')}` |",
        f"",
        f"### Key Topics",
        f"",
    ]
    topics = [t.strip() for t in responses.get("topics", "").split(",")]
    for t in topics:
        lines.append(f"- `{t}`")

    lines += [
        f"",
        f"---",
        f"",
        f"## 4. Arduino Firmware",
        f"",
        f"| Setting            | Value |",
        f"|--------------------|-------|",
        f"| ROS2 Library       | {responses.get('arduino_library', '')} |",
        f"| Control Algorithm  | {responses.get('control_algorithm', '')} |",
        f"| PID Parameters     | {responses.get('pid_params', '')} |",
        f"",
        f"---",
        f"",
        f"## 5. Behaviour & Features",
        f"",
        f"| Setting        | Value |",
        f"|----------------|-------|",
        f"| Line / Surface | {responses.get('line_color', '')} |",
        f"| Target Speed   | {responses.get('speed', '')} |",
        f"",
        f"**Extra Features:**",
        f"",
        f"{responses.get('extra_features', 'None')}",
        f"",
        f"---",
        f"",
        f"## 6. Quick-Start Steps",
        f"",
        f"```bash",
        f"# 1. Flash Arduino firmware",
        f"#    Open the .ino sketch in Arduino IDE and upload to the Uno.",
        f"",
        f"# 2. Source ROS2",
        f"source /opt/ros/{responses.get('ros2_distro', '<distro>').lower()}/setup.bash",
        f"",
        f"# 3. Build the workspace",
        f"cd ~/{responses.get('workspace_name', 'robot_ws')}",
        f"colcon build --symlink-install",
        f"source install/setup.bash",
        f"",
        f"# 4. Launch the line follower",
        f"ros2 launch {responses.get('package_name', 'line_follower')} line_follower.launch.py",
        f"```",
        f"",
        f"---",
        f"",
        f"*This file was auto-generated by `generate_instructions.py`.*",
    ]
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Line Following Robot — Instruction File Generator")
    print("  (ROS2 + Arduino Uno)")
    print("=" * 60)
    print("\nAnswer each question to build your custom instruction file.")
    print("Press Ctrl+C at any time to abort.\n")

    responses = {}
    try:
        for q in QUESTIONS:
            responses[q["key"]] = ask(q)
    except KeyboardInterrupt:
        print("\n\n⚠️  Aborted. No files were written.")
        return

    # ── Write outputs ──────────────────────────────────────────────────────
    out_dir = os.path.dirname(os.path.abspath(__file__))
    project_slug = responses.get("project_name", "linebot").replace(" ", "_").lower()

    md_path   = os.path.join(out_dir, f"{project_slug}_instructions.md")
    json_path = os.path.join(out_dir, f"{project_slug}_responses.json")

    with open(md_path, "w") as f:
        f.write(build_markdown(responses))

    with open(json_path, "w") as f:
        json.dump(responses, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  ✅  Instruction file : {md_path}")
    print(f"  ✅  Raw responses    : {json_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
