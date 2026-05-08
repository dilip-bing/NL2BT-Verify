"""
MoveTo behavior — ROS 1 / Noetic version.

Uses actionlib.SimpleActionClient with move_base_msgs/MoveBaseAction.
This is the correct interface for TurtleBot2 (Kobuki) with ROS 1 Noetic.

LOCATION_MAP: Replace placeholder (x, y, yaw_degrees) values with
coordinates measured from your saved map.

How to measure coordinates:
  1. roslaunch turtlebot_navigation amcl_demo.launch map_file:=<your_map.yaml>
  2. Open RViz → Add a "2D Nav Goal" marker
  3. Click on the map where you want the location
  4. Read the (x, y) values printed in the terminal
  5. Update LOCATION_MAP below
"""
import math
import time
import rospy
import actionlib
import py_trees
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Quaternion

# Human-readable actionlib goal state names
_GOAL_STATE_NAMES = {
    0: "PENDING",
    1: "ACTIVE",
    2: "PREEMPTED",
    3: "SUCCEEDED",
    4: "ABORTED",
    5: "REJECTED",
    6: "PREEMPTING",
    7: "RECALLING",
    8: "RECALLED",
    9: "LOST",
}

# How often (seconds) to log "still navigating…" while RUNNING
_PROGRESS_LOG_INTERVAL = 10.0


# ── Named locations → (x, y, yaw_degrees) in the map frame ──────────────────
# IMPORTANT: replace placeholder values with coordinates from YOUR lab map.
# Run: roslaunch turtlebot_navigation amcl_demo.launch map_file:=<map.yaml>
# Then use RViz 2D Nav Goal clicks to find real coordinates.
LOCATION_MAP = {
    "start":            (1.187,  0.125,   1.0),
    "shelf_1":          (1.187,  0.125,   1.0),
    "shelf_2":          (3.750,  2.400,  74.1),
    "room_b":           (4.771,  5.090,  70.0),
    "room_a":           (7.206,  3.328, -53.9),
    "charging_station": (3.574,  0.143, -166.5),
}

# move_base action server name (standard for TurtleBot2)
MOVE_BASE_SERVER = "move_base"

# Timeout waiting for action server to come up (seconds)
SERVER_TIMEOUT = 10.0


def _yaw_to_quaternion(yaw_deg: float) -> Quaternion:
    """Convert yaw angle (degrees) to a ROS Quaternion (rotation around Z)."""
    yaw = math.radians(yaw_deg)
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q


class MoveTo(py_trees.behaviour.Behaviour):
    """
    Navigate the TurtleBot2 to a named location using move_base (ROS 1).

    State machine:
      RUNNING  — goal sent, waiting for move_base to finish
      SUCCESS  — move_base reported SUCCEEDED
      FAILURE  — unknown location, move_base failed/aborted, or server unavailable
    """

    def __init__(self, name: str, location: str):
        """
        Args:
            name:     py_trees node name (arbitrary string)
            location: key from LOCATION_MAP (case-insensitive, spaces → _)
        """
        super().__init__(name=f"move_to:{location}")
        self.location = location.lower().replace(" ", "_")
        self._client = None
        self._goal_sent = False
        self._goal_start_time = None
        self._last_log_time = None

    def setup(self, **kwargs):
        """Called once before the tree starts ticking.  Creates the action client."""
        self._client = actionlib.SimpleActionClient(MOVE_BASE_SERVER, MoveBaseAction)
        rospy.loginfo(f"[MoveTo] Waiting for move_base action server …")
        available = self._client.wait_for_server(rospy.Duration(SERVER_TIMEOUT))
        if available:
            rospy.loginfo("[MoveTo] move_base server found ✓")
        else:
            rospy.logerr(
                f"[MoveTo] move_base server NOT available after {SERVER_TIMEOUT}s. "
                "Is turtlebot_navigation running?"
            )

    def initialise(self):
        """Called every time the node transitions from INVALID → RUNNING."""
        self._goal_sent = False
        self._goal_start_time = None
        self._last_log_time = None

        if self.location not in LOCATION_MAP:
            rospy.logerr(
                f"[MoveTo] Unknown location '{self.location}'. "
                f"Add it to LOCATION_MAP in move_to.py. "
                f"Known: {list(LOCATION_MAP.keys())}"
            )
            return

        if self._client is None:
            rospy.logerr("[MoveTo] Action client not initialised (setup() not called?)")
            return

        x, y, yaw_deg = LOCATION_MAP[self.location]
        q = _yaw_to_quaternion(yaw_deg)

        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp    = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.position.z = 0.0
        goal.target_pose.pose.orientation = q

        self._client.send_goal(goal)
        self._goal_sent = True
        self._goal_start_time = time.time()
        self._last_log_time = self._goal_start_time
        rospy.loginfo(
            f"[MoveTo] Goal sent → '{self.location}'  "
            f"(x={x:.2f}, y={y:.2f}, yaw={yaw_deg:.0f}°)"
        )

    def update(self) -> py_trees.common.Status:
        """Ticked every BT cycle. Returns RUNNING until move_base finishes."""
        if self.location not in LOCATION_MAP:
            return py_trees.common.Status.FAILURE

        if not self._goal_sent:
            return py_trees.common.Status.FAILURE

        state = self._client.get_state()
        state_name = _GOAL_STATE_NAMES.get(state, f"UNKNOWN({state})")

        # Log progress every N seconds while still navigating
        if state in (actionlib.GoalStatus.PENDING, actionlib.GoalStatus.ACTIVE):
            now = time.time()
            elapsed = now - self._goal_start_time
            if now - self._last_log_time >= _PROGRESS_LOG_INTERVAL:
                x, y, _ = LOCATION_MAP[self.location]
                rospy.loginfo(
                    f"[MoveTo] Still navigating to '{self.location}' "
                    f"(x={x:.2f}, y={y:.2f}) — {elapsed:.0f}s elapsed, "
                    f"state={state_name}"
                )
                self._last_log_time = now
            return py_trees.common.Status.RUNNING

        elapsed = time.time() - self._goal_start_time

        if state == actionlib.GoalStatus.SUCCEEDED:
            rospy.loginfo(
                f"[MoveTo] ✓ Reached '{self.location}' in {elapsed:.1f}s"
            )
            return py_trees.common.Status.SUCCESS

        # ── FAILED — log state name + likely cause to help diagnose ──────────
        x, y, _ = LOCATION_MAP[self.location]
        inflation = "unknown"
        try:
            inflation = rospy.get_param(
                "/move_base/global_costmap/inflation_layer/inflation_radius"
            )
        except KeyError:
            pass

        hint = ""
        if state == actionlib.GoalStatus.ABORTED:
            hint = (
                "  Common causes of ABORTED:\n"
                f"    1. inflation_radius={inflation} — if > 0.1, path is blocked.\n"
                "       Fix: rosparam set /move_base/global_costmap/inflation_layer/inflation_radius 0.05\n"
                "            rosparam set /move_base/local_costmap/inflation_layer/inflation_radius 0.05\n"
                "            rosservice call /move_base/clear_costmaps '{}'\n"
                "    2. AMCL not localised — robot thinks it is in a wall.\n"
                "       Fix: RViz → '2D Pose Estimate' → click robot's real position\n"
                "    3. Goal coordinates are inside an obstacle in the map.\n"
                f"       Goal was: x={x:.3f}, y={y:.3f} — verify in RViz"
            )
        elif state == actionlib.GoalStatus.REJECTED:
            hint = (
                f"  Goal REJECTED by move_base — x={x:.3f}, y={y:.3f} may be\n"
                "  outside the map boundaries or in a lethal obstacle cell."
            )

        rospy.logerr(
            f"[MoveTo] ✗ Failed to reach '{self.location}' after {elapsed:.1f}s\n"
            f"  move_base state: {state} ({state_name})\n"
            f"{hint}"
        )
        return py_trees.common.Status.FAILURE

    def terminate(self, new_status: py_trees.common.Status):
        """Called when the node is interrupted (e.g. tree preempted)."""
        if new_status == py_trees.common.Status.INVALID and self._goal_sent:
            rospy.loginfo(f"[MoveTo] Cancelling navigation to '{self.location}'")
            self._client.cancel_goal()
            self._goal_sent = False
