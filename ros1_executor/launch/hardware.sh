#!/usr/bin/env bash
# =============================================================================
# NL2BT-Verify — ROS 1 / Noetic Hardware Launch Script
# Run this ON the TurtleBot2 (Kobuki) laptop.
#
# What this does (in order):
#   1. Sources ROS Noetic
#   2. Exports required environment variables (Kobuki + Astra)
#   3. Terminal 1 (background): roscore
#   4. Terminal 2 (background): turtlebot_bringup minimal.launch (Kobuki base)
#   5. Terminal 3 (background): astra.launch (Orbbec depth camera)
#   6. Terminal 4 (background): amcl_demo.launch with chosen map
#   7. Prints next steps for running the NL2BT pipeline
#
# Usage:
#   chmod +x hardware.sh
#   ./hardware.sh [path/to/map.yaml]
#
# If no map is given, it defaults to the most recent map in ~/maps/
# =============================================================================

set -e

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── ROS setup ─────────────────────────────────────────────────────────────────
ROS_SETUP="/opt/ros/noetic/setup.bash"
[[ -f "$ROS_SETUP" ]] || error "ROS Noetic not found at $ROS_SETUP"
source "$ROS_SETUP"

# Source catkin workspace if it exists
CATKIN_WS="$HOME/catkin_ws"
[[ -f "$CATKIN_WS/devel/setup.bash" ]] && source "$CATKIN_WS/devel/setup.bash"

# ── Robot environment variables ───────────────────────────────────────────────
export TURTLEBOT_BASE=kobuki
export TURTLEBOT_STACKS=hexagons
export TURTLEBOT_3D_SENSOR=astra
export TURTLEBOT_SERIAL_PORT=/dev/kobuki
export ROS_MASTER_URI=http://localhost:11311

info "Robot model  : TurtleBot2 (Kobuki)"
info "3D sensor    : Orbbec Astra"
info "Serial port  : $TURTLEBOT_SERIAL_PORT"

# ── Map file ──────────────────────────────────────────────────────────────────
if [[ -n "$1" ]]; then
    MAP_FILE="$1"
else
    # Auto-find the most recently modified map in ~/maps or catkin_ws
    MAP_FILE=$(find ~ -maxdepth 6 \( -name "*.yaml" \) 2>/dev/null \
        | grep -v "ros\|opt\|snap\|\.ros" \
        | xargs ls -t 2>/dev/null \
        | head -1)
fi

[[ -f "$MAP_FILE" ]] || error "Map file not found: $MAP_FILE
  Saved maps on this laptop:
$(find ~ -maxdepth 6 -name '*.yaml' 2>/dev/null | grep -v 'ros\|opt\|snap\|\.ros' | head -10)
  Run SLAM first (see README), or pass map path as argument:
    ./hardware.sh ~/maps/my_map.yaml"

info "Using map    : $MAP_FILE"

# ── Check Kobuki device ───────────────────────────────────────────────────────
if [[ ! -e /dev/kobuki ]]; then
    warn "/dev/kobuki not found. Checking /dev/ttyUSB0 …"
    if [[ -e /dev/ttyUSB0 ]]; then
        info "Found /dev/ttyUSB0 — creating /dev/kobuki symlink (needs sudo)"
        sudo ln -sf /dev/ttyUSB0 /dev/kobuki 2>/dev/null \
            || warn "Could not create symlink — run manually: sudo ln -sf /dev/ttyUSB0 /dev/kobuki"
    else
        warn "No Kobuki USB device detected — is the robot powered on and USB connected?"
    fi
fi

# ── Helper: launch in new gnome-terminal tab (falls back to xterm) ────────────
new_term() {
    local title="$1"
    local cmd="$2"
    if command -v gnome-terminal &>/dev/null; then
        gnome-terminal --tab --title="$title" -- bash -c "source $ROS_SETUP; $cmd; exec bash" &
    elif command -v xterm &>/dev/null; then
        xterm -T "$title" -e "bash -c 'source $ROS_SETUP; $cmd; exec bash'" &
    else
        # No GUI available (SSH session) — run in background with nohup
        warn "No terminal emulator found — launching $title in background"
        nohup bash -c "source $ROS_SETUP; $cmd" > /tmp/nl2bt_${title// /_}.log 2>&1 &
    fi
    sleep 2   # give each process time to start
}

# ── 1. roscore ─────────────────────────────────────────────────────────────────
info "Starting roscore …"
new_term "roscore" "roscore"

# ── 2. Kobuki bringup ─────────────────────────────────────────────────────────
info "Starting TurtleBot2 bringup …"
new_term "TurtleBot Bringup" \
    "TURTLEBOT_BASE=kobuki TURTLEBOT_3D_SENSOR=astra \
     roslaunch turtlebot_bringup minimal.launch"

# ── 3. Astra camera ───────────────────────────────────────────────────────────
info "Starting Orbbec Astra camera …"
new_term "Astra Camera" \
    "roslaunch astra_launch astra.launch"

# ── 4. Navigation (AMCL + move_base) ──────────────────────────────────────────
info "Starting navigation with map: $MAP_FILE"
info "  → After RViz opens: click '2D Pose Estimate' and click where the robot IS on the map"
new_term "Navigation (AMCL)" \
    "TURTLEBOT_BASE=kobuki TURTLEBOT_3D_SENSOR=astra \
     roslaunch turtlebot_navigation amcl_demo.launch map_file:=$MAP_FILE"

sleep 5   # wait for move_base to fully load before overriding params

# ── 5. Fix costmap inflation (default 0.5 is too large for small lab) ─────────
info "Reducing costmap inflation radius to 0.05 …"
rosparam set /move_base/global_costmap/inflation_layer/inflation_radius 0.05
rosparam set /move_base/local_costmap/inflation_layer/inflation_radius 0.05
rosservice call /move_base/clear_costmaps "{}" 2>/dev/null || true
info "Costmap inflation updated ✓"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}  All hardware nodes launched!${NC}"
echo ""
echo "  NEXT STEPS:"
echo "  1. In RViz, click '2D Pose Estimate' and mark where the robot IS"
echo "  2. Verify robot moves correctly with teleop:"
echo "       roslaunch turtlebot_teleop keyboard_teleop.launch"
echo "  3. Run the NL2BT pipeline:"
echo "       cd ~/NL2BT-Verify"
echo "       python3 -m pipeline"
echo "       # or start the web UI:"
echo "       streamlit run web_interface/app.py"
echo ""
echo "  Logs are in /tmp/nl2bt_*.log (if running over SSH)"
echo -e "${GREEN}================================================================${NC}"
