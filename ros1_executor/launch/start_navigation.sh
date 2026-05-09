#!/usr/bin/env bash
# =============================================================================
# Start turtlebot navigation and automatically fix inflation_radius to 0.05.
# Use this INSTEAD of running amcl_demo.launch manually.
#
# Usage:
#   chmod +x ~/NL2BT-Verify/ros1_executor/launch/start_navigation.sh
#   ~/NL2BT-Verify/ros1_executor/launch/start_navigation.sh
# =============================================================================

source /opt/ros/noetic/setup.bash
[[ -f ~/catkin_ws/devel/setup.bash ]] && source ~/catkin_ws/devel/setup.bash

export TURTLEBOT_BASE=kobuki
export TURTLEBOT_3D_SENSOR=astra

MAP_FILE="${1:-$HOME/my_map4.yaml}"

echo "[Nav] Starting amcl_demo.launch with map: $MAP_FILE"

# Launch navigation in background
roslaunch turtlebot_navigation amcl_demo.launch map_file:="$MAP_FILE" &
LAUNCH_PID=$!

# Wait until move_base is fully up (clear_costmaps service appears)
echo "[Nav] Waiting for move_base to finish loading..."
until rosservice list 2>/dev/null | grep -q "/move_base/clear_costmaps"; do
    sleep 2
done
sleep 4   # extra buffer for costmap plugins to fully initialise

# Apply inflation fix using dynamic_reconfigure (the correct runtime API)
echo "[Nav] Applying inflation_radius = 0.05 ..."
rosrun dynamic_reconfigure dynparam set /move_base/global_costmap/inflation_layer inflation_radius 0.05
rosrun dynamic_reconfigure dynparam set /move_base/local_costmap/inflation_layer inflation_radius 0.05
rosservice call /move_base/clear_costmaps "{}"

CURRENT=$(rosparam get /move_base/global_costmap/inflation_layer/inflation_radius 2>/dev/null || echo "unknown")
if [[ "$CURRENT" == "0.05" ]]; then
    echo "[Nav] ✓ inflation_radius = $CURRENT — navigation ready!"
else
    echo "[Nav] ✗ inflation_radius = $CURRENT — applying dynparam again..."
    rosrun dynamic_reconfigure dynparam set /move_base/global_costmap/inflation_layer inflation_radius 0.05
    rosrun dynamic_reconfigure dynparam set /move_base/local_costmap/inflation_layer inflation_radius 0.05
    rosservice call /move_base/clear_costmaps "{}"
    echo "[Nav] inflation_radius = $(rosparam get /move_base/global_costmap/inflation_layer/inflation_radius)"
fi

echo ""
echo "========================================"
echo "  Navigation is ready."
echo "  Set initial pose in RViz, then run:"
echo "  streamlit run web_interface/app.py --server.address 0.0.0.0"
echo "========================================"

# Keep running until user presses Ctrl+C (keeps roslaunch alive)
wait $LAUNCH_PID
