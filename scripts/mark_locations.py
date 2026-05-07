#!/usr/bin/env python3
"""
mark_locations.py — Interactive location marker for NL2BT-Verify.

Run this while the robot is localised (AMCL running).
Drive the robot to each spot with teleop, then press Enter to save it.

Usage:
    python3 scripts/mark_locations.py

At the end it prints the complete LOCATION_MAP ready to paste into
ros1_executor/behaviors/move_to.py
"""
import sys
import math

try:
    import rospy
    from geometry_msgs.msg import PoseWithCovarianceStamped
except ImportError:
    print("[ERROR] rospy not found. Source ROS first:")
    print("  source /opt/ros/noetic/setup.bash")
    sys.exit(1)

current_pose = None

def pose_callback(msg):
    global current_pose
    p = msg.pose.pose.position
    o = msg.pose.pose.orientation
    # Convert quaternion to yaw
    yaw = math.degrees(math.atan2(
        2.0 * (o.w * o.z + o.x * o.y),
        1.0 - 2.0 * (o.y * o.y + o.z * o.z)
    ))
    current_pose = (round(p.x, 3), round(p.y, 3), round(yaw, 1))

def main():
    rospy.init_node("location_marker", anonymous=True)
    rospy.Subscriber("/amcl_pose", PoseWithCovarianceStamped, pose_callback)

    print("\n" + "="*55)
    print("  NL2BT-Verify — Location Marker")
    print("="*55)
    print("  Drive to each spot with teleop, then come back here.")
    print("  Press Enter to save current position.")
    print("  Type 'done' when finished.")
    print("="*55 + "\n")

    # Wait for first pose
    print("Waiting for /amcl_pose ... (make sure AMCL is running)")
    rate = rospy.Rate(2)
    while current_pose is None and not rospy.is_shutdown():
        rate.sleep()
    print(f"Connected! Current position: x={current_pose[0]}, y={current_pose[1]}\n")

    saved = {}

    while not rospy.is_shutdown():
        x, y, yaw = current_pose
        print(f"  Current position → x={x:7.3f}  y={y:7.3f}  yaw={yaw:6.1f}°")
        name = input("  Name this location (or 'done'): ").strip().lower().replace(" ", "_")

        if name == "done" or name == "":
            break

        saved[name] = (x, y, yaw)
        print(f"  ✓ Saved '{name}' → ({x}, {y}, {yaw}°)\n")

    if not saved:
        print("No locations saved.")
        return

    # ── Print ready-to-paste LOCATION_MAP ─────────────────────────────────────
    print("\n" + "="*55)
    print("  Copy this into ros1_executor/behaviors/move_to.py")
    print("="*55)
    print("\nLOCATION_MAP = {")
    for name, (x, y, yaw) in saved.items():
        print(f'    "{name}":{" " * max(1, 20 - len(name))}({x},  {y},  {yaw}),')
    print("}")

    # ── Also write directly to move_to.py ─────────────────────────────────────
    import os, re
    move_to_path = os.path.join(
        os.path.dirname(__file__), "..", "ros1_executor", "behaviors", "move_to.py"
    )
    move_to_path = os.path.abspath(move_to_path)

    save_choice = input("\nAuto-update move_to.py with these coordinates? [y/N]: ").strip().lower()
    if save_choice == "y":
        with open(move_to_path, "r") as f:
            content = f.read()

        # Build new LOCATION_MAP block
        lines = ["LOCATION_MAP = {\n"]
        for name, (x, y, yaw) in saved.items():
            lines.append(f'    "{name}":{" " * max(1, 20 - len(name))}({x},  {y},  {yaw}),\n')
        lines.append("}\n")
        new_block = "".join(lines)

        # Replace existing LOCATION_MAP block
        updated = re.sub(
            r"LOCATION_MAP\s*=\s*\{[^}]*\}",
            new_block.rstrip("\n"),
            content,
            flags=re.DOTALL,
        )

        with open(move_to_path, "w") as f:
            f.write(updated)

        print(f"  ✓ Updated: {move_to_path}")
        print("  Now commit and push, or just use locally on the robot.")
    else:
        print("  Paste the block above manually into move_to.py")

    print("\nDone!\n")

if __name__ == "__main__":
    main()
