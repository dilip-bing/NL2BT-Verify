"""
Stage 3 entry point — called from pipeline.py.

Auto-detects which ROS version is available:
  • ROS 2 (rclpy present)  → uses ros2_executor.bt_executor_node  (Nav2 / TurtleBot3)
  • ROS 1 (rospy present)  → uses ros1_executor.bt_executor_node   (move_base / TurtleBot2/Kobuki)
  • Neither                → prints the verified XML (dry-run / CI mode)
"""


def execute_behavior_tree(xml_string: str):
    # ── Try ROS 2 first ────────────────────────────────────────────────────────
    try:
        import rclpy  # noqa: F401
        from ros2_executor.bt_executor_node import execute_behavior_tree as _exec_ros2
        print("[Executor] ROS 2 detected → using Nav2 executor")
        _exec_ros2(xml_string)
        return
    except ImportError:
        pass

    # ── Fall back to ROS 1 ─────────────────────────────────────────────────────
    try:
        import rospy  # noqa: F401
        from ros1_executor.bt_executor_node import execute_behavior_tree as _exec_ros1
        print("[Executor] ROS 1 detected → using move_base executor")
        _exec_ros1(xml_string)
        return
    except ImportError:
        pass

    # ── No ROS — dry-run mode ──────────────────────────────────────────────────
    print("[Executor] No ROS installation found — running in dry-run mode.")
    print("[Executor] Verified XML that would be executed on hardware:")
    print(xml_string)
