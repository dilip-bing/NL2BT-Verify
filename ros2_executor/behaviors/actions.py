"""
Simple action behaviors: pick_up, place, wait, check_obstacle, open_door, etc.
These are stubs that log and succeed — replace with real hardware calls later.
"""
import time
import py_trees
from std_msgs.msg import String


def _publish_box(box_pub, state: str):
    if box_pub is not None:
        msg = String()
        msg.data = state
        box_pub.publish(msg)


class PickUp(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(name=f"pick_up:{item}")
        self.item = item
        self.box_pub = box_pub
        self._start_time = None

    def initialise(self):
        self._start_time = time.time()
        self.logger.info(f"Reached item — picking up: {self.item}...")
        _publish_box(self.box_pub, "picking_up")

    def update(self) -> py_trees.common.Status:
        elapsed = time.time() - self._start_time
        if elapsed < 5.0:
            if elapsed > 1.0:
                _publish_box(self.box_pub, "carried")
            return py_trees.common.Status.RUNNING
        self.logger.info(f"Picked up: {self.item}")
        _publish_box(self.box_pub, "carried")
        return py_trees.common.Status.SUCCESS


class Place(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(name=f"place:{item}")
        self.item = item
        self.box_pub = box_pub

    def update(self) -> py_trees.common.Status:
        self.logger.info(f"Placing: {self.item}")
        _publish_box(self.box_pub, "placed")
        return py_trees.common.Status.SUCCESS


class Wait(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, duration: float = 2.0):
        super().__init__(name=f"wait:{duration}s")
        self.duration = duration
        self._start_time = None

    def initialise(self):
        self._start_time = time.time()

    def update(self) -> py_trees.common.Status:
        elapsed = time.time() - self._start_time
        if elapsed >= self.duration:
            self.logger.info(f"Wait complete ({self.duration}s)")
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING


class CheckObstacle(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="check_obstacle")

    def update(self) -> py_trees.common.Status:
        self.logger.info("Checking for obstacles...")
        return py_trees.common.Status.SUCCESS


class OpenDoor(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="open_door")

    def update(self) -> py_trees.common.Status:
        self.logger.info("Opening door...")
        return py_trees.common.Status.SUCCESS


class CloseDoor(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="close_door")

    def update(self) -> py_trees.common.Status:
        self.logger.info("Closing door...")
        return py_trees.common.Status.SUCCESS


class Charge(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="charge")

    def update(self) -> py_trees.common.Status:
        self.logger.info("Charging robot...")
        return py_trees.common.Status.SUCCESS


class Deliver(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(name=f"deliver:{item}")
        self.item = item
        self.box_pub = box_pub

    def update(self) -> py_trees.common.Status:
        self.logger.info(f"Delivering: {self.item}")
        _publish_box(self.box_pub, "delivered")
        return py_trees.common.Status.SUCCESS


class Patrol(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="patrol")

    def update(self) -> py_trees.common.Status:
        self.logger.info("Patrolling...")
        return py_trees.common.Status.SUCCESS
