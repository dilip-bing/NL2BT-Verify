"""
Simple action behaviors for ROS 1 / Noetic — TurtleBot2 (Kobuki).

PickUp, Place, and Deliver perform a full 360° rotation in place on
/cmd_vel as a visual cue (robot has no physical manipulator).
"""
import math
import time
import rospy
import py_trees
from std_msgs.msg import String
from geometry_msgs.msg import Twist

# One full rotation parameters
SPIN_ANGULAR_VEL = 0.8          # rad/s
SPIN_DURATION    = (2 * math.pi) / SPIN_ANGULAR_VEL   # ≈ 7.85 s for one full rotation

# Shared /cmd_vel publisher (created once, reused by all spin behaviours)
_cmd_vel_pub = None

def _get_cmd_vel_pub():
    global _cmd_vel_pub
    if _cmd_vel_pub is None:
        _cmd_vel_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        rospy.sleep(0.3)  # let publisher register
    return _cmd_vel_pub

def _spin(angular_z: float):
    """Publish a single rotation command."""
    pub = _get_cmd_vel_pub()
    twist = Twist()
    twist.angular.z = angular_z
    pub.publish(twist)

def _stop():
    """Stop the robot."""
    pub = _get_cmd_vel_pub()
    pub.publish(Twist())   # all zeros = stop

def _publish_box(box_pub, state: str):
    if box_pub is not None:
        msg = String()
        msg.data = state
        box_pub.publish(msg)


class _SpinBehaviour(py_trees.behaviour.Behaviour):
    """Base class: spins one full 360° rotation then succeeds."""

    def __init__(self, name: str, box_pub=None, box_state_start="", box_state_end=""):
        super().__init__(name=name)
        self.box_pub         = box_pub
        self.box_state_start = box_state_start
        self.box_state_end   = box_state_end
        self._start_time     = None

    def initialise(self):
        self._start_time = time.time()
        _publish_box(self.box_pub, self.box_state_start)
        _spin(SPIN_ANGULAR_VEL)
        rospy.loginfo(f"[{self.name}] Spinning 360° …")

    def update(self) -> py_trees.common.Status:
        elapsed = time.time() - self._start_time
        if elapsed < SPIN_DURATION:
            _spin(SPIN_ANGULAR_VEL)   # keep spinning each tick
            return py_trees.common.Status.RUNNING
        _stop()
        _publish_box(self.box_pub, self.box_state_end)
        rospy.loginfo(f"[{self.name}] Done ✓")
        return py_trees.common.Status.SUCCESS

    def terminate(self, new_status):
        _stop()   # always stop motors on interruption


class PickUp(_SpinBehaviour):
    """Spins 360° to simulate picking up an item."""

    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(
            name=f"pick_up:{item}",
            box_pub=box_pub,
            box_state_start="picking_up",
            box_state_end="carried",
        )
        self.item = item

    def initialise(self):
        rospy.loginfo(f"[PickUp] Picking up '{self.item}' — spinning 360°")
        super().initialise()


class Place(_SpinBehaviour):
    """Spins 360° to simulate placing an item."""

    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(
            name=f"place:{item}",
            box_pub=box_pub,
            box_state_start="placing",
            box_state_end="placed",
        )
        self.item = item

    def initialise(self):
        rospy.loginfo(f"[Place] Placing '{self.item}' — spinning 360°")
        super().initialise()


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


class Deliver(_SpinBehaviour):
    """Spins 360° to simulate delivering an item."""

    def __init__(self, name: str, item: str = "object", box_pub=None):
        super().__init__(
            name=f"deliver:{item}",
            box_pub=box_pub,
            box_state_start="delivering",
            box_state_end="delivered",
        )
        self.item = item

    def initialise(self):
        rospy.loginfo(f"[Deliver] Delivering '{self.item}' — spinning 360°")
        super().initialise()


class Patrol(py_trees.behaviour.Behaviour):
    def __init__(self, name: str):
        super().__init__(name="patrol")

    def update(self) -> py_trees.common.Status:
        rospy.loginfo("[Patrol] Patrolling …")
        return py_trees.common.Status.SUCCESS
