"""
Tests for the XML → py_trees loader (no ROS 2 needed, navigator=None for non-move_to trees).
"""
import pytest
import py_trees
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ros2_executor.xml_loader import load_tree_from_xml


def test_simple_sequence():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="pick_up" item="box"/>
        <Action name="place" item="box"/>
      </Sequence>
    </BehaviorTree>
    """
    tree = load_tree_from_xml(xml, navigator=None)
    assert tree.name == "root"
    assert isinstance(tree, py_trees.composites.Sequence)
    assert len(tree.children) == 2


def test_fallback_node():
    xml = """
    <BehaviorTree>
      <Fallback name="fb">
        <Action name="check_obstacle"/>
        <Action name="wait"/>
      </Fallback>
    </BehaviorTree>
    """
    tree = load_tree_from_xml(xml, navigator=None)
    assert isinstance(tree, py_trees.composites.Selector)


def test_repeat_node():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Repeat name="loop" max_iterations="3">
          <Action name="wait"/>
        </Repeat>
      </Sequence>
    </BehaviorTree>
    """
    tree = load_tree_from_xml(xml, navigator=None)
    assert tree.name == "root"


def test_nested_sequence():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="pick_up" item="box"/>
        <Sequence name="deliver_seq">
          <Action name="deliver" item="box"/>
          <Action name="wait"/>
        </Sequence>
      </Sequence>
    </BehaviorTree>
    """
    tree = load_tree_from_xml(xml, navigator=None)
    assert len(tree.children) == 2


def test_move_to_requires_navigator():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="move_to" location="room_a"/>
      </Sequence>
    </BehaviorTree>
    """
    with pytest.raises(RuntimeError, match="Navigator required"):
        load_tree_from_xml(xml, navigator=None)


def test_unknown_action_raises():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="fire_laser"/>
      </Sequence>
    </BehaviorTree>
    """
    with pytest.raises(ValueError, match="Unknown action"):
        load_tree_from_xml(xml, navigator=None)
