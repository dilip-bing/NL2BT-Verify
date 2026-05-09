#!/usr/bin/env bash
# =============================================================================
# Permanently fix inflation_radius to 0.05 for TurtleBot2 navigation.
#
# Finds and patches EVERY YAML file under turtlebot_navigation and the
# catkin workspace that contains inflation_radius, then adds a roslaunch
# arg override as a final safety net so the value can never be overridden
# at launch time.
#
# Run ONCE on the TurtleBot2 robot laptop (requires sudo).
#
# Usage:
#   chmod +x scripts/fix_inflation_permanent.sh
#   ./scripts/fix_inflation_permanent.sh
# =============================================================================

set -e

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

TARGET="0.05"
PATTERN='s/inflation_radius: [0-9][0-9.]*/inflation_radius: '"$TARGET"'/g'

echo "============================================================"
echo "  NL2BT-Verify — Permanent inflation_radius fix"
echo "  Target value: $TARGET"
echo "============================================================"
echo ""

# ── 1. Find all YAML files with inflation_radius ───────────────────────────
info "Searching for all YAML files containing inflation_radius ..."
echo ""

SEARCH_DIRS=(
    "/opt/ros/noetic/share/turtlebot_navigation"
    "/opt/ros/noetic/share/turtlebot_bringup"
    "$HOME/catkin_ws"
    "$HOME/ros_ws"
)

FILES=()
for dir in "${SEARCH_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        while IFS= read -r f; do
            FILES+=("$f")
        done < <(grep -rl "inflation_radius" "$dir" 2>/dev/null || true)
    fi
done

if [[ ${#FILES[@]} -eq 0 ]]; then
    error "No files found with inflation_radius. Check your ROS installation."
    exit 1
fi

info "Found ${#FILES[@]} file(s):"
for f in "${FILES[@]}"; do
    echo "    $f"
    grep "inflation_radius" "$f" | sed 's/^/        before: /'
done
echo ""

# ── 2. Patch every file found ──────────────────────────────────────────────
info "Patching all files ..."
for f in "${FILES[@]}"; do
    # Backup (only once — don't overwrite an existing backup)
    BACKUP="${f}.bak"
    if [[ ! -f "$BACKUP" ]]; then
        sudo cp "$f" "$BACKUP"
        echo "    Backed up → $BACKUP"
    fi
    sudo sed -i "$PATTERN" "$f"
    echo "    Patched  → $f"
    grep "inflation_radius" "$f" | sed 's/^/        after:  /'
done
echo ""

# ── 3. Add a drop-in override file that amcl_demo.launch can't undo ───────
# Write a YAML override that hardware.sh loads AFTER amcl_demo.launch.
# This is the last line of defence if any launch file still overrides the value.
OVERRIDE="$HOME/NL2BT-Verify/ros1_executor/params/move_base_override.yaml"
if [[ -f "$OVERRIDE" ]]; then
    info "Override YAML already exists at $OVERRIDE — skipping"
else
    info "Writing override YAML to $OVERRIDE ..."
    cat > "$OVERRIDE" <<'YAML'
move_base:
  global_costmap:
    inflation_layer:
      inflation_radius: 0.05
  local_costmap:
    inflation_layer:
      inflation_radius: 0.05
  DWAPlannerROS:
    max_vel_x: 0.3
    min_vel_x: 0.0
    max_rot_vel: 1.0
    xy_goal_tolerance: 0.3
    yaw_goal_tolerance: 0.5
YAML
fi

# ── 4. Write a one-liner apply script to ~/apply_inflation_fix.sh ──────────
# So the user can run it quickly after every amcl_demo.launch as backup.
APPLY_SCRIPT="$HOME/apply_inflation_fix.sh"
cat > "$APPLY_SCRIPT" <<SCRIPT
#!/usr/bin/env bash
# Run this after amcl_demo.launch if inflation_radius ever resets.
rosparam load $HOME/NL2BT-Verify/ros1_executor/params/move_base_override.yaml
rosservice call /move_base/clear_costmaps "{}"
echo "inflation_radius: \$(rosparam get /move_base/global_costmap/inflation_layer/inflation_radius)"
SCRIPT
chmod +x "$APPLY_SCRIPT"
info "Quick-fix script written → $APPLY_SCRIPT"
echo "    Run anytime with: ~/apply_inflation_fix.sh"
echo ""

# ── 5. Verify ──────────────────────────────────────────────────────────────
echo "============================================================"
info "All done. Steps to confirm the fix:"
echo ""
echo "  1. Restart amcl_demo.launch:"
echo "       roslaunch turtlebot_navigation amcl_demo.launch map_file:=\$HOME/my_map4.yaml"
echo ""
echo "  2. Check the live value:"
echo "       rosparam get /move_base/global_costmap/inflation_layer/inflation_radius"
echo "       # Must show: $TARGET"
echo ""
echo "  3. If it still shows 0.55, run the quick-fix:"
echo "       ~/apply_inflation_fix.sh"
echo "       # This loads the override YAML and clears costmaps"
echo "============================================================"
