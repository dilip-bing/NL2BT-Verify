"""
Shared configuration: allowed actions, map dimensions, loop limits, known locations.
Both the SMT verifier and the LLM prompt use these values to stay in sync.
"""
from __future__ import annotations

ALLOWED_ACTIONS = {
    "move_to",
    "pick_up",
    "place",
    "wait",
    "check_obstacle",
    "open_door",
    "close_door",
    "charge",
    "patrol",
    "deliver",
}

# Lab map dimensions in metres (real TurtleBot2 map)
MAP_WIDTH = 15
MAP_HEIGHT = 15

# Maximum loop iterations allowed
LOOP_THRESHOLD = 100

# Named locations and their (x, y) coordinates in the lab map frame (metres)
KNOWN_LOCATIONS = {
    "startingposition": (1.187, 0.125),
    "shelf1":           (1.187, 0.125),
    "shelf2":           (3.802, 2.424),
    "roomb":            (4.771, 5.09),
    "rooma":            (7.206, 3.328),
    "chargingdock":     (3.574, 0.143),
}

# Map connectivity graph (location → reachable locations)
# Simple fully-connected map for now; replace with actual Nav2 costmap query later
MAP_GRAPH: dict[str, list[str]] = {loc: list(KNOWN_LOCATIONS.keys()) for loc in KNOWN_LOCATIONS}
