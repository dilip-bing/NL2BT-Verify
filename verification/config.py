"""
Shared configuration: allowed actions, map dimensions, loop limits, known locations.
Both the SMT verifier and the LLM prompt use these values to stay in sync.
"""

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

# Gazebo world dimensions (grid units)
MAP_WIDTH = 200
MAP_HEIGHT = 200

# Maximum loop iterations allowed
LOOP_THRESHOLD = 100

# Named locations and their (x, y) coordinates in the Gazebo world
KNOWN_LOCATIONS = {
    "room_a":       (20,  20),
    "room_b":       (180, 20),
    "room_c":       (20,  180),
    "room_d":       (180, 180),
    "shelf_1":      (50,  50),
    "shelf_2":      (100, 50),
    "shelf_3":      (150, 50),
    "shelf_4":      (50,  150),
    "shelf_5":      (100, 150),
    "loading_dock": (100, 10),
    "charging_station": (10, 10),
    "start":        (100, 100),
}

# Map connectivity graph (location → reachable locations)
# Simple fully-connected map for now; replace with actual Nav2 costmap query later
MAP_GRAPH: dict[str, list[str]] = {loc: list(KNOWN_LOCATIONS.keys()) for loc in KNOWN_LOCATIONS}
