#!/usr/bin/env bash
# =============================================================================
# Permanently set inflation_radius to 0.05 in the turtlebot_navigation
# costmap params file.  Run ONCE on the TurtleBot2 laptop (requires sudo).
#
# What it does:
#   1. Backs up the original file to costmap_common_params.yaml.bak
#   2. Replaces every "inflation_radius: X.X" with "inflation_radius: 0.05"
#   3. Prints before/after so you can verify
#
# After running this, amcl_demo.launch will always start with 0.05 —
# no need for the rosparam set workaround anymore.
#
# Usage:
#   chmod +x scripts/fix_inflation_permanent.sh
#   ./scripts/fix_inflation_permanent.sh
# =============================================================================

set -e

PARAM_FILE="/opt/ros/noetic/share/turtlebot_navigation/param/costmap_common_params.yaml"

if [[ ! -f "$PARAM_FILE" ]]; then
    echo "[ERROR] File not found: $PARAM_FILE"
    echo "  Check the correct path with:"
    echo "    find /opt/ros/noetic/share/turtlebot_navigation/param -name '*.yaml' | xargs grep -l inflation_radius"
    exit 1
fi

echo "=== Before ==="
grep "inflation_radius" "$PARAM_FILE"

# Back up the original (only if backup doesn't already exist)
BACKUP="${PARAM_FILE}.bak"
if [[ ! -f "$BACKUP" ]]; then
    sudo cp "$PARAM_FILE" "$BACKUP"
    echo "Backup saved → $BACKUP"
else
    echo "Backup already exists at $BACKUP — skipping"
fi

# Apply the change
sudo sed -i 's/inflation_radius: [0-9.]*/inflation_radius: 0.05/g' "$PARAM_FILE"

echo ""
echo "=== After ==="
grep "inflation_radius" "$PARAM_FILE"

echo ""
echo "Done. Restart amcl_demo.launch and verify:"
echo "  rosparam get /move_base/global_costmap/inflation_layer/inflation_radius"
echo "  # Should show: 0.05"
