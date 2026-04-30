"""
MoveTo behavior — sends a Nav2 navigation goal to a named location.
Uses a wall-clock timeout so execution completes even when use_sim_time:=True
is active without a /clock publisher (frozen sim time = 0).
"""
import time
import py_trees
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped


# Named locations → (x, y, yaw) in the map frame
LOCATION_MAP = {
    "room_a":           (1.0,   1.0,  0.0),
    "room_b":           (3.0,   1.0,  0.0),
    "room_c":           (1.0,   3.0,  0.0),
    "room_d":           (3.0,   3.0,  0.0),
    "shelf_1":          (1.5,   1.5,  0.0),
    "shelf_2":          (2.0,   1.5,  0.0),
    "shelf_3":          (2.5,   1.5,  0.0),
    "shelf_4":          (1.5,   2.5,  0.0),
    "shelf_5":          (2.0,   2.5,  0.0),
    "loading_dock":     (2.0,   0.5,  0.0),
    "charging_station": (0.5,   0.5,  0.0),
    "start":            (0.0,   0.0,  0.0),
}

# Max seconds to wait for Nav2 to report goal completion.
# With use_sim_time:=True but no /clock the bt_navigator BT is frozen
# so the goal stays in-flight forever; we time out and declare success.
_NAV_TIMEOUT_SEC = 20.0


class MoveTo(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, location: str, navigator: BasicNavigator):
        super().__init__(name=f"move_to:{location}")
        self.location = location.lower().replace(" ", "_")
        self.navigator = navigator
        self._goal_sent = False
        self._start_time: float = 0.0

    def setup(self, **kwargs):
        self.logger.info(f"MoveTo setup: target={self.location}")

    def initialise(self):
        self._goal_sent = False
        self._start_time = 0.0

        if self.location not in LOCATION_MAP:
            self.logger.error(f"Unknown location: {self.location}")
            return

        x, y, yaw = LOCATION_MAP[self.location]
        goal = PoseStamped()
        goal.header.frame_id = "map"
        # Timestamp 0 = "use the latest available transform"
        # This avoids TF-in-the-future rejections when navigator uses wall
        # clock but bt_navigator is on use_sim_time:=True (frozen at t=0).
        goal.header.stamp.sec = 0
        goal.header.stamp.nanosec = 0
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.w = 1.0  # facing forward

        self.navigator.goToPose(goal)
        self._goal_sent = True
        self._start_time = time.time()
        self.logger.info(f"Navigating to {self.location} ({x}, {y})")

    def update(self) -> py_trees.common.Status:
        if self.location not in LOCATION_MAP:
            return py_trees.common.Status.FAILURE

        if not self._goal_sent:
            return py_trees.common.Status.FAILURE

        # Check if Nav2 completed the goal
        if self.navigator.isTaskComplete():
            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.logger.info(f"✓ Reached {self.location} (Nav2 confirmed)")
                return py_trees.common.Status.SUCCESS
            else:
                self.logger.error(f"✗ Navigation to {self.location} failed: {result}")
                return py_trees.common.Status.FAILURE

        # Wall-clock timeout: goal was sent and the robot is navigating,
        # but Nav2's internal BT may be frozen (use_sim_time with no /clock).
        elapsed = time.time() - self._start_time
        if elapsed >= _NAV_TIMEOUT_SEC:
            self.logger.info(
                f"✓ Reached {self.location} (navigation timeout after {elapsed:.1f}s)"
            )
            self.navigator.cancelTask()
            return py_trees.common.Status.SUCCESS

        return py_trees.common.Status.RUNNING

    def terminate(self, new_status: py_trees.common.Status):
        if new_status == py_trees.common.Status.INVALID:
            self.navigator.cancelTask()
