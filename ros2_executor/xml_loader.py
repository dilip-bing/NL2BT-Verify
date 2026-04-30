"""
Converts a verified XML Behavior Tree into a live py_trees tree.
"""
import xml.etree.ElementTree as ET
import py_trees
from ros2_executor.behaviors.move_to import MoveTo
from ros2_executor.behaviors.actions import (
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


def load_tree_from_xml(xml_string: str, navigator=None, box_pub=None) -> py_trees.behaviour.Behaviour:
    """Parse verified XML and return a py_trees Behaviour tree root."""
    root_elem = ET.fromstring(xml_string)

    # <BehaviorTree> wraps the actual root node
    if root_elem.tag == "BehaviorTree":
        children = list(root_elem)
        if not children:
            raise ValueError("BehaviorTree element has no children")
        root_elem = children[0]

    return _build_node(root_elem, navigator, box_pub)


def _build_node(elem: ET.Element, navigator, box_pub=None) -> py_trees.behaviour.Behaviour:
    tag = elem.tag
    name = elem.get("name", tag)

    if tag == "Sequence":
        node = py_trees.composites.Sequence(name=name, memory=True)
        for child in elem:
            node.add_child(_build_node(child, navigator, box_pub))
        return node

    elif tag == "Fallback":
        node = py_trees.composites.Selector(name=name, memory=False)
        for child in elem:
            node.add_child(_build_node(child, navigator, box_pub))
        return node

    elif tag == "Repeat":
        max_iter = int(elem.get("max_iterations", elem.get("num_cycles", 1)))
        children = list(elem)
        if not children:
            raise ValueError(f"Repeat node '{name}' has no child")
        child_node = _build_node(children[0], navigator, box_pub)
        # py_trees decorator for repeating
        node = py_trees.decorators.Repeat(
            child=child_node,
            name=name,
            num_success=max_iter,
        )
        return node

    elif tag == "Action":
        return _build_action(elem, navigator, box_pub)

    elif tag == "Condition":
        # Conditions treated as always-success stubs for now
        return py_trees.behaviours.Success(name=f"condition:{name}")

    else:
        raise ValueError(f"Unknown BT node type: {tag}")


def _build_action(elem: ET.Element, navigator, box_pub=None) -> py_trees.behaviour.Behaviour:
    action_name = elem.get("name", "")
    node_name = action_name

    if action_name == "move_to":
        location = elem.get("location", "start")
        if navigator is None:
            raise RuntimeError("Navigator required for move_to actions but not provided")
        return MoveTo(name=node_name, location=location, navigator=navigator)

    elif action_name in ACTION_MAP:
        cls = ACTION_MAP[action_name]
        item = elem.get("item", "object")
        duration = float(elem.get("duration", 2.0))

        if action_name in ("pick_up", "place", "deliver"):
            return cls(name=node_name, item=item, box_pub=box_pub)
        elif action_name == "wait":
            return cls(name=node_name, duration=duration)
        else:
            return cls(name=node_name)

    else:
        raise ValueError(f"Unknown action: {action_name}")
