"""
test_locations.py — Verifies that location names are consistent across:
  1. ros1_executor/behaviors/move_to.py  (LOCATION_MAP)
  2. verification/config.py              (KNOWN_LOCATIONS)
  3. llm_module/prompts/system_prompt.txt (Known Locations line)

Run with:
    python3 -m pytest tests/test_locations.py -v
    # or without pytest:
    python3 tests/test_locations.py
"""
import sys
import os
import re
import ast

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_dict_keys_from_file(filepath: str, var_name: str) -> set:
    """Extract keys from a dict assignment in a Python file without importing it.
    Works even when the file has imports that aren't available (e.g. rospy)."""
    with open(filepath) as f:
        source = f.read()

    # Find the dict literal: VAR_NAME = { ... }
    pattern = rf"{var_name}\s*=\s*(\{{[^}}]*\}})"
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find '{var_name}' dict in {filepath}")

    dict_src = match.group(1)
    # ast.literal_eval only handles string keys + tuple values — perfect here
    parsed = ast.literal_eval(dict_src)
    return set(parsed.keys())


def _parse_prompt_locations(filepath: str) -> set:
    """Extract the comma-separated location names from the system prompt."""
    with open(filepath) as f:
        for line in f:
            if line.startswith("room_") or ("room_a" in line and "shelf_" in line):
                # This is the Known Locations line
                return {loc.strip() for loc in line.strip().split(",")}
            # Look for the line right after "## Known Locations"
    # Second pass: line after the header
    with open(filepath) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "## Known Locations" in line and i + 1 < len(lines):
            return {loc.strip() for loc in lines[i + 1].strip().split(",")}
    raise ValueError("Could not find Known Locations in system_prompt.txt")


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_location_names_in_sync():
    """LOCATION_MAP, KNOWN_LOCATIONS, and system_prompt must have identical keys."""
    move_to_keys = _parse_dict_keys_from_file(
        os.path.join(ROOT, "ros1_executor/behaviors/move_to.py"),
        "LOCATION_MAP",
    )
    config_keys = _parse_dict_keys_from_file(
        os.path.join(ROOT, "verification/config.py"),
        "KNOWN_LOCATIONS",
    )
    prompt_keys = _parse_prompt_locations(
        os.path.join(ROOT, "llm_module/prompts/system_prompt.txt"),
    )

    print("\n  LOCATION_MAP keys  :", sorted(move_to_keys))
    print("  KNOWN_LOCATIONS keys:", sorted(config_keys))
    print("  system_prompt keys  :", sorted(prompt_keys))

    only_in_move_to  = move_to_keys  - config_keys
    only_in_config   = config_keys   - move_to_keys
    only_in_prompt   = prompt_keys   - move_to_keys
    missing_in_prompt = move_to_keys - prompt_keys

    errors = []
    if only_in_move_to:
        errors.append(f"  ❌ In move_to.py but NOT config.py:      {only_in_move_to}")
    if only_in_config:
        errors.append(f"  ❌ In config.py but NOT move_to.py:      {only_in_config}")
    if only_in_prompt:
        errors.append(f"  ❌ In system_prompt but NOT move_to.py:  {only_in_prompt}")
    if missing_in_prompt:
        errors.append(f"  ❌ In move_to.py but NOT system_prompt:  {missing_in_prompt}")

    if errors:
        print("\nMISMATCHES FOUND:")
        for e in errors:
            print(e)
        assert False, "Location names are out of sync — see output above"
    else:
        print("\n  ✅ All location names are in sync across all three files.")


def test_coordinates_in_bounds():
    """All LOCATION_MAP coordinates must be within the MAP bounds."""
    from verification.config import MAP_WIDTH, MAP_HEIGHT

    move_to_path = os.path.join(ROOT, "ros1_executor/behaviors/move_to.py")
    with open(move_to_path) as f:
        source = f.read()

    pattern = r"LOCATION_MAP\s*=\s*(\{[^}]*\})"
    match = re.search(pattern, source, re.DOTALL)
    loc_map = ast.literal_eval(match.group(1))

    errors = []
    for name, coords in loc_map.items():
        x, y = coords[0], coords[1]
        if not (0 <= x <= MAP_WIDTH):
            errors.append(f"  ❌ {name}: x={x} out of bounds [0, {MAP_WIDTH}]")
        if not (0 <= y <= MAP_HEIGHT):
            errors.append(f"  ❌ {name}: y={y} out of bounds [0, {MAP_HEIGHT}]")

    if errors:
        print("\nOUT-OF-BOUNDS COORDINATES:")
        for e in errors:
            print(e)
        assert False, "Some coordinates are outside map bounds"
    else:
        print("\n  ✅ All coordinates are within map bounds.")


# ── Standalone runner ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    passed = 0
    failed = 0
    for name, fn in [("test_location_names_in_sync", test_location_names_in_sync),
                     ("test_coordinates_in_bounds",  test_coordinates_in_bounds)]:
        print(f"\n{'='*55}")
        print(f"  Running: {name}")
        print('='*55)
        try:
            fn()
            print(f"  PASSED ✅")
            passed += 1
        except AssertionError as e:
            print(f"  FAILED ❌  {e}")
            failed += 1

    print(f"\n{'='*55}")
    print(f"  Results: {passed} passed, {failed} failed")
    print('='*55)
    sys.exit(0 if failed == 0 else 1)
