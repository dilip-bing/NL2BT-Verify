"""
MoveTo behavior — sends a Nav2 NavigateToPose goal to a named location.

Hardware mode  : Nav2 fully controls navigation. isTaskComplete() returns
                 True only when the robot physically reaches the goal or
                 fails. No timeout hacks needed.

Simulation mode: pass use_sim_time=True to BasicNavigator if running with
                 the fake node.

Update LOCATION_MAP below with coordinates measured from your saved map
(use RViz2 → 2D Nav Goal, read x/y from the terminal output).
"""
import math
import py_trees
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped
from builtin_interfaces.msg import Time


# ── Named locations → (x, y, yaw_degrees) in the map frame ──────────────────
# IMPORTANT: replace these with coordinates measured from YOUR lab map.
# How to measure: launch Nav2 with your map, click "2D Nav Goal" in RViz2
# on each location, and read the (x, y) printed in the terminal.
LOCATION_MAP = {
    "room_a":           (1.0,  1.0,   0.0),   # ← replace with real values
    "room_b":           (3.0,  1.0,   0.0),
    "room_c":           (1.0,  3.0,   0.0),
    "room_d":           (3.0,  3.0,   0.0),
    "shelf_1":          (1.5,  1.5,   0.0),
    "shelf_2":          (2.0,  1.5,   0.0),
    "shelf_3":          (2.5,  1.5,   0.0),
    "shelf_4":          (1.5,  2.5,   0.0),
    "shelf_5":          (2.0,  2.5,   0.0),
    "loading_dock":     (2.0,  0.5,   0.0),
    "charging_station": (0.5,  0.5, 180.0),   # face the charger
    "start":            (0.0,  0.0,   0.0),
}


def _yaw_to_quaternion(yaw_deg: float):
    """Convert yaw angle (degrees) to a (qz, qw) quaternion pair."""
    yaw = math.radians(yaw_deg)
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)


class MoveTo(py_trees.behaviour.Behaviour):
    """
    Navigate the robot to a named location using Nav2.

    On hardware:  Nav2 reports SUCCEEDED / FAILED when the robot arrives
                  or gives up. No wall-clock timeout is used.
    On failure:   returns FAILURE so the behavior tree can handle it
                  (e.g. a Fallback node could retry or raise an alarm).
    """

    def __init__(self, name: str, location: str, navigator: BasicNavigator):
        super().__init__(name=f"move_to:{location}")
        self.location  = location.lower().replace(" ", "_")
        self.navigator = navigator
        self._goal_sent = False

    def setup(self, **kwargs):
        self.logger.info(f"[MoveTo] Ready — target location: {self.location}")

    def initialise(self):
        self._goal_sent = False

        if self.location not in LOCATION_MAP:
            self.logger.error(
                f"[MoveTo] Unknown location '{self.location}'. "
                f"Add it to LOCATION_MAP in move_to.py"
            )
            return

        x, y, yaw_deg = LOCATION_MAP[self.location]
        qz, qw        = _yaw_to_quaternion(yaw_deg)

        goal                       = PoseStamped()
        goal.header.frame_id       = "map"
        goal.header.stamp          = Time()   # stamp=0 → use latest TF
        goal.pose.position.x       = x
        goal.pose.position.y       = y
        goal.pose.position.z       = 0.0
        goal.pose.orientation.z    = qz
        goal.pose.orientation.w    = qw

        self.navigator.goToPose(goal)
        self._goal_sent = True
        self.logger.info(
            f"[MoveTo] Navigating to '{self.location}'  "
            f"(x={x:.2f}, y={y:.2f}, yaw={yaw_deg:.0f}°)"
        )

    def update(self) -> py_trees.common.Status:
        if self.location not in LOCATION_MAP:
            return py_trees.common.Status.FAILURE

        if not self._goal_sent:
            return py_trees.common.Status.FAILURE

        if not self.navigator.isTaskComplete():
            # Still navigating — show live feedback
            feedback = self.navigator.getFeedback()
            if feedback:
                dist = feedback.distance_remaining
                self.logger.debug(f"[MoveTo] {self.location} — {dist:.2f} m remaining")
            return py_trees.common.Status.RUNNING

        # Nav2 finished — check the result
        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            self.logger.info(f"[MoveTo] ✓ Reached '{self.location}'")
            return py_trees.common.Status.SUCCESS
        else:
            self.logger.error(
                f"[MoveTo] ✗ Failed to reach '{self.location}' — Nav2 result: {result}"
            )
            return py_trees.common.Status.FAILURE

    def terminate(self, new_status: py_trees.common.Status):
        if new_status == py_trees.common.Status.INVALID:
            self.logger.info(f"[MoveTo] Cancelled navigation to '{self.location}'")
            self.navigator.cancelTask()
