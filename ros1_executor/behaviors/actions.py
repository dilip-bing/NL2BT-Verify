"""
Simple action behaviors for ROS 1 / Noetic — TurtleBot2 (Kobuki).

These publish to ROS topics and log via rospy instead of py_trees logger.
Stub behaviours succeed after a short delay; replace with real hardware
calls as needed (e.g. arm actuation, gripper, etc.).
"""
import time
import rospy
import py_trees
from std_msgs.msg import String


def _publish_box(box_pub, state: str):
    """Publish box state if a publisher was provided."""
    if box_pub is not None:
        msg = String()
        msg.data = state
        box_pub.publish(msg)


class PickUp(py_trees.behaviour.Behaviour):
    """Simulates picking up an item (5-second stub)."""

    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(name=f"pick_up:{item}")
        self.item = item
        self.box_pub = box_pub
        self._start_time = None

    def initialise(self):
        self._start_time = time.time()
        rospy.loginfo(f"[PickUp] Picking up: {self.item}")
        _publish_box(self.box_pub, "picking_up")

    def update(self) -> py_trees.common.Status:
        elapsed = time.time() - self._start_time
        if elapsed < 5.0:
            if elapsed > 1.0:
                _publish_box(self.box_pub, "carried")
            return py_trees.common.Status.RUNNING
        rospy.loginfo(f"[PickUp] Picked up: {self.item}")
        _publish_box(self.box_pub, "carried")
        return py_trees.common.Status.SUCCESS


class Place(py_trees.behaviour.Behaviour):
    """Places an item (instant stub)."""

    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(name=f"place:{item}")
        self.item = item
        self.box_pub = box_pub

    def update(self) -> py_trees.common.Status:
        rospy.loginfo(f"[Place] Placing: {self.item}")
        _publish_box(self.box_pub, "placed")
        return py_trees.common.Status.SUCCESS


class Wait(py_trees.behaviour.Behaviour):
    """Waits for a given duration (seconds)."""

    def __init__(self, name: str, duration: float = 2.0):
        super().__init__(name=f"wait:{duration}s")
        self.duration = duration
        self._start_time = None

    def initialise(self):
        self._start_time = time.time()

    def update(self) -> py_trees.common.Status:
        elapsed = time.time() - self._start_time
        if elapsed >= self.duration:
            rospy.loginfo(f"[Wait] Complete ({self.duration}s)")
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING


class CheckObstacle(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="check_obstacle")

    def update(self) -> py_trees.common.Status:
        rospy.loginfo("[CheckObstacle] Checking for obstacles …")
        return py_trees.common.Status.SUCCESS


class OpenDoor(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="open_door")

    def update(self) -> py_trees.common.Status:
        rospy.loginfo("[OpenDoor] Opening door …")
        return py_trees.common.Status.SUCCESS


class CloseDoor(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="close_door")

    def update(self) -> py_trees.common.Status:
        rospy.loginfo("[CloseDoor] Closing door …")
        return py_trees.common.Status.SUCCESS


class Charge(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="charge")

    def update(self) -> py_trees.common.Status:
        rospy.loginfo("[Charge] Docking to charge …")
        return py_trees.common.Status.SUCCESS


class Deliver(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(name=f"deliver:{item}")
        self.item = item
        self.box_pub = box_pub

    def update(self) -> py_trees.common.Status:
        rospy.loginfo(f"[Deliver] Delivering: {self.item}")
        _publish_box(self.box_pub, "delivered")
        return py_trees.common.Status.SUCCESS


class Patrol(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="patrol")

    def update(self) -> py_trees.common.Status:
        rospy.loginfo("[Patrol] Patrolling …")
        return py_trees.common.Status.SUCCESS
