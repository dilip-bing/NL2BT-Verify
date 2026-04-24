"""Unit tests for the SMT verification engine."""
import pytest
from verification.smt_verifier import SMTVerifier
from verification.config import ALLOWED_ACTIONS, MAP_WIDTH, MAP_HEIGHT, LOOP_THRESHOLD, KNOWN_LOCATIONS, MAP_GRAPH

VERIFIER = SMTVerifier(
    allowed_actions=ALLOWED_ACTIONS,
    map_width=MAP_WIDTH,
    map_height=MAP_HEIGHT,
    loop_threshold=LOOP_THRESHOLD,
    known_locations=KNOWN_LOCATIONS,
    map_graph=MAP_GRAPH,
)

VALID_BT = """
<BehaviorTree>
  <Sequence name="root">
    <Action name="move_to" location="room_a"/>
    <Action name="pick_up" item="box"/>
    <Action name="move_to" location="loading_dock"/>
    <Action name="place" item="box"/>
  </Sequence>
</BehaviorTree>
"""

# --- Property 1: Structural Validity ---

def test_valid_bt_passes():
    result = VERIFIER.verify(VALID_BT)
    assert result["passed"], result["errors"]

def test_malformed_xml_fails():
    result = VERIFIER.verify("<BehaviorTree><Sequence>")
    assert not result["passed"]

def test_unknown_node_type_fails():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <FlyAction name="fly_to" location="room_a"/>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    assert not result["passed"]
    assert any("structural" in e for e in result["errors"])

# --- Property 2: Action Whitelist ---

def test_disallowed_action_fails():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="fire_laser" location="room_a"/>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    assert not result["passed"]
    assert any("whitelist" in e for e in result["errors"])

def test_all_allowed_actions_pass():
    for action in ALLOWED_ACTIONS:
        xml = f'<BehaviorTree><Sequence name="root"><Action name="{action}"/></Sequence></BehaviorTree>'
        result = VERIFIER.verify(xml)
        whitelist_check = next(c for c in result["checks"] if c["name"] == "action_whitelist")
        assert whitelist_check["passed"], f"Action '{action}' should be allowed"

# --- Property 3: Spatial Bounds ---

def test_out_of_bounds_coordinates_fail():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="move_to" location="out_of_bounds" x="500" y="500"/>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    assert not result["passed"]
    assert any("spatial" in e for e in result["errors"])

def test_in_bounds_coordinates_pass():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="move_to" location="room_a" x="20" y="20"/>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    spatial_check = next(c for c in result["checks"] if c["name"] == "spatial_bounds")
    assert spatial_check["passed"]

# --- Property 4: Loop Termination ---

def test_loop_with_bound_passes():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Repeat name="patrol" max_iterations="5">
          <Action name="move_to" location="room_a"/>
        </Repeat>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    loop_check = next(c for c in result["checks"] if c["name"] == "loop_termination")
    assert loop_check["passed"]

def test_loop_without_bound_fails():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Repeat name="infinite_loop">
          <Action name="move_to" location="room_a"/>
        </Repeat>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    assert not result["passed"]
    assert any("loop" in e for e in result["errors"])

def test_loop_exceeding_threshold_fails():
    xml = f"""
    <BehaviorTree>
      <Sequence name="root">
        <Repeat name="too_long" max_iterations="{LOOP_THRESHOLD + 1}">
          <Action name="move_to" location="room_a"/>
        </Repeat>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    assert not result["passed"]

# --- Property 5: Reachability ---

def test_unknown_location_fails():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="move_to" location="moon_base"/>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    assert not result["passed"]
    assert any("reachability" in e for e in result["errors"])

def test_known_location_passes():
    xml = """
    <BehaviorTree>
      <Sequence name="root">
        <Action name="move_to" location="room_b"/>
      </Sequence>
    </BehaviorTree>
    """
    result = VERIFIER.verify(xml)
    reach_check = next(c for c in result["checks"] if c["name"] == "reachability")
    assert reach_check["passed"]
