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
from geometry_msgs.msg import PoseWithCovarianceStamped

from ros1_executor.xml_loader import load_tree_from_xml

# Tick rate in Hz
TICK_HZ = 10


def _set_initial_pose():
    """
    Publish the robot's starting position to /initialpose so AMCL
    localises immediately without needing RViz 2D Pose Estimate.
    Uses the 'startingposition' coordinates from LOCATION_MAP.
    """
    from ros1_executor.behaviors.move_to import LOCATION_MAP

    if "start" not in LOCATION_MAP:
        rospy.logwarn("[InitPose] 'start' not in LOCATION_MAP — skipping auto-pose")
        return

    x, y, _ = LOCATION_MAP["start"]

    pub = rospy.Publisher("/initialpose", PoseWithCovarianceStamped, queue_size=1, latch=True)
    rospy.sleep(0.5)   # give publisher time to connect

    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = "map"
    msg.header.stamp    = rospy.Time.now()
    msg.pose.pose.position.x    = x
    msg.pose.pose.position.y    = y
    msg.pose.pose.position.z    = 0.0
    msg.pose.pose.orientation.x = 0.0
    msg.pose.pose.orientation.y = 0.0
    msg.pose.pose.orientation.z = 0.0
    msg.pose.pose.orientation.w = 1.0
    # Covariance: moderate uncertainty so AMCL can still refine with laser
    msg.pose.covariance = [
        0.25, 0, 0, 0, 0, 0,
        0, 0.25, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0.07,
    ]
    pub.publish(msg)
    rospy.loginfo(f"[InitPose] Initial pose set → x={x}, y={y} (AMCL localising…)")
    rospy.sleep(2.0)   # give AMCL time to process and spread particles


def _check_inflation_radius():
    """Log inflation radius and warn loudly if it is still at the default 0.5."""
    for ns in ("global_costmap", "local_costmap"):
        param = f"/move_base/{ns}/inflation_layer/inflation_radius"
        try:
            val = rospy.get_param(param)
            if val > 0.1:
                rospy.logerr(
                    f"[StartupCheck] {param} = {val}  ← TOO LARGE, paths will be blocked!\n"
                    "  Fix now:\n"
                    f"    rosparam set {param} 0.05\n"
                    "    rosservice call /move_base/clear_costmaps '{}'"
                )
            else:
                rospy.loginfo(f"[StartupCheck] {param} = {val}  ✓")
        except KeyError:
            rospy.logwarn(f"[StartupCheck] {param} not found — move_base may not be running yet")


def _check_amcl_pose():
    """
    Wait up to 3 s for one /amcl_pose message and log the robot's estimated
    position.  A near-zero pose (0,0) or a position far outside the map usually
    means AMCL has not been given an initial pose yet.
    """
    from geometry_msgs.msg import PoseWithCovarianceStamped
    received = []

    def _cb(msg):
        received.append(msg)

    sub = rospy.Subscriber("/amcl_pose", PoseWithCovarianceStamped, _cb)
    deadline = rospy.Time.now() + rospy.Duration(3.0)
    while not received and rospy.Time.now() < deadline:
        rospy.sleep(0.1)
    sub.unregister()

    if not received:
        rospy.logwarn(
            "[StartupCheck] /amcl_pose — no message received in 3 s.\n"
            "  AMCL may not be running or the robot has not been localised yet.\n"
            "  In RViz: click '2D Pose Estimate' and mark where the robot IS on the map."
        )
        return

    p = received[0].pose.pose.position
    rospy.loginfo(
        f"[StartupCheck] AMCL pose → x={p.x:.3f}  y={p.y:.3f}  z={p.z:.3f}"
    )
    if abs(p.x) < 0.01 and abs(p.y) < 0.01:
        rospy.logwarn(
            "[StartupCheck] AMCL pose is at (0, 0) — robot is probably NOT localised.\n"
            "  In RViz: click '2D Pose Estimate' and click the robot's real position on the map."
        )


def execute_behavior_tree(xml_string: str):
    """
    Entry point called from pipeline.py (Stage 3).

    Initialises rospy, builds the BT, ticks it until SUCCESS or FAILURE,
    then shuts down cleanly.
    """
    rospy.init_node("nl2bt_executor", anonymous=False)
    rospy.loginfo("=== NL2BT-Verify ROS 1 Executor starting ===")

    # ── Startup diagnostics — print everything needed to catch common failures ─
    rospy.loginfo("[StartupCheck] ── Checking costmap inflation radius ──")
    _check_inflation_radius()
    rospy.loginfo("[StartupCheck] ── Checking AMCL localisation ──")
    _check_amcl_pose()
    rospy.loginfo("[StartupCheck] ── Done ──")

    # ── Auto-set initial pose (only if robot is at start position) ───────────
    # Disabled: robot may not always be at 'start' when executor launches.
    # Run this manually if needed:
    #   rostopic pub -1 /initialpose geometry_msgs/PoseWithCovarianceStamped ...
    # _set_initial_pose()

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
