"""
Stage 3: ROS 2 Executor — loads a verified XML BT and runs it via py_trees_ros.
This module is only imported when ROS 2 Humble is available.
"""
import xml.etree.ElementTree as ET


def execute_behavior_tree(xml_string: str):
    """Load a verified XML BT and execute via py_trees_ros."""
    try:
        import rclpy
        import py_trees_ros
    except ImportError:
        print("[Executor] ROS 2 / py_trees_ros not available. Skipping execution.")
        print("[Executor] XML BT that would have been executed:")
        print(xml_string)
        return

    rclpy.init()

    # Write XML to a temp file — py_trees_ros loads from file path
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml_string)
        tmp_path = f.name

    try:
        # TODO: Replace with actual py_trees_ros XML tree loader once
        # ROS 2 package structure is set up (see ros2_executor/bt_ros2_pkg/)
        print(f"[Executor] Would load BT from: {tmp_path}")
        print("[Executor] py_trees_ros execution stub — implement BT node wiring here")
    finally:
        os.unlink(tmp_path)
        rclpy.shutdown()
