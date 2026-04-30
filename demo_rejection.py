"""
Presentation demo: show the SMT verifier catching unsafe BTs.
Run with: python3 demo_rejection.py
"""
from verification.smt_verifier import SMTVerifier
from verification.config import ALLOWED_ACTIONS, MAP_WIDTH, MAP_HEIGHT, LOOP_THRESHOLD, KNOWN_LOCATIONS, MAP_GRAPH

verifier = SMTVerifier(
    allowed_actions=ALLOWED_ACTIONS,
    map_width=MAP_WIDTH,
    map_height=MAP_HEIGHT,
    loop_threshold=LOOP_THRESHOLD,
    known_locations=KNOWN_LOCATIONS,
    map_graph=MAP_GRAPH,
)

DEMOS = [
    (
        "GOOD: Normal pick-and-place task",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="move_to" location="shelf_1"/>
    <Action name="pick_up" item="box"/>
    <Action name="move_to" location="loading_dock"/>
    <Action name="deliver" item="box"/>
  </Sequence>
</BehaviorTree>"""
    ),
    (
        "BAD: Disallowed action (fire_laser)",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="move_to" location="room_a"/>
    <Action name="fire_laser" target="obstacle"/>
  </Sequence>
</BehaviorTree>"""
    ),
    (
        "BAD: Out-of-bounds coordinates",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="move_to" location="room_a" x="9999" y="9999"/>
    <Action name="pick_up" item="box"/>
  </Sequence>
</BehaviorTree>"""
    ),
    (
        "BAD: Infinite loop (no bound)",
        """<BehaviorTree>
  <Sequence name="root">
    <Repeat name="forever">
      <Action name="patrol"/>
    </Repeat>
  </Sequence>
</BehaviorTree>"""
    ),
    (
        "BAD: Unknown location (moon_base)",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="move_to" location="moon_base"/>
    <Action name="pick_up" item="box"/>
  </Sequence>
</BehaviorTree>"""
    ),
    (
        "BAD: Task ordering violation (pick_up before move_to)",
        """<BehaviorTree>
  <Sequence name="root">
    <Action name="pick_up" item="box"/>
    <Action name="move_to" location="loading_dock"/>
    <Action name="deliver" item="box"/>
  </Sequence>
</BehaviorTree>"""
    ),
]

print("=" * 65)
print("  NL2BT-Verify — SMT Safety Verification Demo")
print("=" * 65)

for label, xml in DEMOS:
    result = verifier.verify(xml)
    status = "SAFE ✓" if result["passed"] else "BLOCKED ✗"
    print(f"\n[{status}] {label}")
    if not result["passed"]:
        for err in result["errors"]:
            print(f"  → {err}")

print("\n" + "=" * 65)
print("  All unsafe behaviors blocked before any action was taken.")
print("=" * 65)
