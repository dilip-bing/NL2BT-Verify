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


# ── Named locations → (x, y, yaw_degrees) in the map frame ──────────────────
# IMPORTANT: replace placeholder values with coordinates from YOUR lab map.
# Run: roslaunch turtlebot_navigation amcl_demo.launch map_file:=<map.yaml>
# Then use RViz 2D Nav Goal clicks to find real coordinates.
LOCATION_MAP = {
    "start":            (1.187,  0.125,   1.0),
    "shelf_1":          (1.187,  0.125,   1.0),
    "shelf_2":          (3.802,  2.424,  74.1),
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

        # actionlib states: PENDING=0, ACTIVE=1, SUCCEEDED=3, ABORTED=4, etc.
        if state in (actionlib.GoalStatus.PENDING, actionlib.GoalStatus.ACTIVE):
            return py_trees.common.Status.RUNNING

        if state == actionlib.GoalStatus.SUCCEEDED:
            rospy.loginfo(f"[MoveTo] ✓ Reached '{self.location}'")
            return py_trees.common.Status.SUCCESS

        rospy.logerr(
            f"[MoveTo] ✗ Failed to reach '{self.location}' "
            f"— move_base state: {state}"
        )
        return py_trees.common.Status.FAILURE

    def terminate(self, new_status: py_trees.common.Status):
        """Called when the node is interrupted (e.g. tree preempted)."""
        if new_status == py_trees.common.Status.INVALID and self._goal_sent:
            rospy.loginfo(f"[MoveTo] Cancelling navigation to '{self.location}'")
            self._client.cancel_goal()
            self._goal_sent = False
