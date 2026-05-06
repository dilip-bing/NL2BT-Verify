"""
Converts a verified XML Behavior Tree into a live py_trees tree.
ROS 1 / Noetic version — uses ros1_executor behaviors.
"""
import xml.etree.ElementTree as ET
import py_trees
from ros1_executor.behaviors.move_to import MoveTo
from ros1_executor.behaviors.actions import (
    PickUp, Place, Wait, CheckObstacle,
    OpenDoor, CloseDoor, Charge, Deliver, Patrol,
)


ACTION_MAP = {
    "pick_up":        PickUp,
    "place":          Place,
    "wait":           Wait,
    "check_obstacle": CheckObstacle,
    "open_door":      OpenDoor,
    "close_door":     CloseDoor,
    "charge":         Charge,
    "deliver":        Deliver,
    "patrol":         Patrol,
}


def load_tree_from_xml(xml_string: str, box_pub=None) -> py_trees.behaviour.Behaviour:
    """Parse verified XML and return a py_trees Behaviour tree root.

    Note: no 'navigator' argument — ROS 1 MoveTo creates its own actionlib client.
    """
    root_elem = ET.fromstring(xml_string)

    # <BehaviorTree> wraps the actual root node
    if root_elem.tag == "BehaviorTree":
        children = list(root_elem)
        if not children:
            raise ValueError("BehaviorTree element has no children")
        root_elem = children[0]

    return _build_node(root_elem, box_pub)


def _build_node(elem: ET.Element, box_pub=None) -> py_trees.behaviour.Behaviour:
    tag  = elem.tag
    name = elem.get("name", tag)

    if tag == "Sequence":
        node = py_trees.composites.Sequence(name=name, memory=True)
        for child in elem:
            node.add_child(_build_node(child, box_pub))
        return node

    elif tag == "Fallback":
        node = py_trees.composites.Selector(name=name, memory=False)
        for child in elem:
            node.add_child(_build_node(child, box_pub))
        return node

    elif tag == "Repeat":
        max_iter  = int(elem.get("max_iterations", elem.get("num_cycles", 1)))
        children  = list(elem)
        if not children:
            raise ValueError(f"Repeat node '{name}' has no child")
        child_node = _build_node(children[0], box_pub)
        node = py_trees.decorators.Repeat(
            child=child_node,
            name=name,
            num_success=max_iter,
        )
        return node

    elif tag == "Action":
        return _build_action(elem, box_pub)

    elif tag == "Condition":
        return py_trees.behaviours.Success(name=f"condition:{name}")

    else:
        raise ValueError(f"Unknown BT node type: '{tag}'")


def _build_action(elem: ET.Element, box_pub=None) -> py_trees.behaviour.Behaviour:
    action_name = elem.get("name", "")

    if action_name == "move_to":
        location = elem.get("location", "start")
        return MoveTo(name=action_name, location=location)

    elif action_name in ACTION_MAP:
        cls      = ACTION_MAP[action_name]
        item     = elem.get("item", "object")
        duration = float(elem.get("duration", 2.0))

        if action_name in ("pick_up", "place", "deliver"):
            return cls(name=action_name, item=item, box_pub=box_pub)
        elif action_name == "wait":
            return cls(name=action_name, duration=duration)
        else:
            return cls(name=action_name)

    else:
        raise ValueError(f"Unknown action: '{action_name}'")
