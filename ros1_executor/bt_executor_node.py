"""
ROS 1 / Noetic BT Executor Node — TurtleBot2 (Kobuki).

Loads a verified XML Behavior Tree and ticks it at 10 Hz using rospy.
Connects to move_base via actionlib for navigation goals.

Usage:
    # Make sure ROS + turtlebot_navigation are running first, then:
    cd ~/NL2BT-Verify
    python3 -m ros1_executor.bt_executor_node <path_to_bt.xml>

    # Or pass XML string directly from pipeline.py via execute_behavior_tree()
"""
import sys
import time
import rospy
import py_trees
from std_msgs.msg import String

from ros1_executor.xml_loader import load_tree_from_xml

# Tick rate in Hz
TICK_HZ = 10


def execute_behavior_tree(xml_string: str):
    """
    Entry point called from pipeline.py (Stage 3).

    Initialises rospy, builds the BT, ticks it until SUCCESS or FAILURE,
    then shuts down cleanly.
    """
    rospy.init_node("nl2bt_executor", anonymous=False)
    rospy.loginfo("=== NL2BT-Verify ROS 1 Executor starting ===")

    # Publisher for box state (visualisation / debugging)
    box_pub = rospy.Publisher("/box_state", String, queue_size=10)
    rospy.sleep(0.5)  # give publisher time to register

    # Announce initial box state
    msg = String()
    msg.data = "on_shelf"
    box_pub.publish(msg)

    # Build the py_trees tree from verified XML
    rospy.loginfo("[Executor] Building behavior tree from XML …")
    try:
        root = load_tree_from_xml(xml_string, box_pub=box_pub)
    except Exception as e:
        rospy.logerr(f"[Executor] Failed to build tree: {e}")
        return

    # Call setup() on ALL nodes recursively (creates actionlib clients, etc.)
    # Note: root.setup() only runs on the root node itself — must iterate children.
    rospy.loginfo("[Executor] Setting up behavior tree …")
    for node in root.iterate():
        node.setup()

    # Print tree structure
    rospy.loginfo("\n" + py_trees.display.ascii_tree(root))

    # ── Tick loop ──────────────────────────────────────────────────────────────
    rate = rospy.Rate(TICK_HZ)
    rospy.loginfo("[Executor] Starting BT tick loop …")

    while not rospy.is_shutdown():
        root.tick_once()
        status = root.status

        if status == py_trees.common.Status.SUCCESS:
            rospy.loginfo("[Executor] ✓  Task COMPLETED successfully")
            break
        elif status == py_trees.common.Status.FAILURE:
            rospy.logerr("[Executor] ✗  Task FAILED")
            break

        rate.sleep()

    rospy.loginfo("[Executor] Shutting down.")


# ── CLI entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m ros1_executor.bt_executor_node <bt_xml_file>")
        sys.exit(1)

    xml_file = sys.argv[1]
    try:
        with open(xml_file) as f:
            xml_str = f.read()
    except FileNotFoundError:
        print(f"[ERROR] File not found: {xml_file}")
        sys.exit(1)

    execute_behavior_tree(xml_str)
