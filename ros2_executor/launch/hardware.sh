#!/usr/bin/env bash
# =============================================================================
# NL2BT-Verify — Hardware Launch Script
# Run this on your LAPTOP (not the TurtleBot).
# The TurtleBot must already be running turtlebot3_bringup (see README).
#
# Usage:
#   chmod +x hardware.sh
#   ./hardware.sh
# =============================================================================

set -e

# ── Configuration — edit these ────────────────────────────────────────────────
TURTLEBOT_MODEL="${TURTLEBOT3_MODEL:-burger}"
DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
MAP_FILE="$(dirname "$0")/../lab_map.yaml"   # path to your saved map
ROS_SETUP="/opt/ros/humble/setup.bash"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Sanity checks ─────────────────────────────────────────────────────────────
info "Checking prerequisites..."

[[ -f "$ROS_SETUP" ]] || error "ROS 2 Humble not found at $ROS_SETUP"
source "$ROS_SETUP"

[[ -f "$MAP_FILE" ]] || error "Map file not found: $MAP_FILE
  Run SLAM first (see Phase 4 in the hardware guide) then:
  ros2 run nav2_map_server map_saver_cli -f ros2_executor/lab_map"

export TURTLEBOT3_MODEL="$TURTLEBOT_MODEL"
export ROS_DOMAIN_ID="$DOMAIN_ID"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

info "TurtleBot model : $TURTLEBOT_MODEL"
info "ROS_DOMAIN_ID   : $DOMAIN_ID"
info "Map file        : $MAP_FILE"

# ── Check robot is reachable ──────────────────────────────────────────────────
info "Checking if /scan topic is available (robot must be on and bringup running)..."
SCAN_CHECK=$(timeout 5 ros2 topic echo /scan --once 2>/dev/null | head -1 || true)
if [[ -z "$SCAN_CHECK" ]]; then
    warn "/scan not detected. Make sure the TurtleBot is on and bringup is running:"
    warn "  SSH into TurtleBot → ros2 launch turtlebot3_bringup robot.launch.py"
    warn "Continuing anyway — Nav2 will wait for sensor data."
else
    info "/scan detected ✓"
fi

# ── Launch Nav2 ───────────────────────────────────────────────────────────────
info "Launching Nav2 with map: $MAP_FILE"
info "In RViz2: click '2D Pose Estimate' and click where the robot IS on the map"
info "Press Ctrl+C to stop."
echo ""

ros2 launch nav2_bringup bringup_launch.py \
    map:="$MAP_FILE"          \
    use_sim_time:=false        \
    params_file:="$(dirname "$0")/../nav2_params.yaml"
