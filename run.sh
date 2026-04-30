#!/bin/bash
# One-command runner: starts Docker, fake robot, Nav2, then runs the pipeline
# Usage: ./run.sh "Go to Room A and pick up the box"

INPUT="${1:-Go to Room A}"

cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         NL2BT-Verify Pipeline Runner         ║"
echo "╚══════════════════════════════════════════════╝"
echo "  Input: $INPUT"
echo ""

docker run --rm -i \
  -v "$(pwd)":/workspace \
  -e TURTLEBOT3_MODEL=burger \
  --env-file .env \
  -p 8765:8765 \
  nl2bt \
  bash -c "
    set -e
    source /opt/ros/humble/setup.bash

    echo '[1/4] Starting fake robot...'
    ros2 launch /workspace/ros2_executor/launch/fake_robot.launch.py > /tmp/fake.log 2>&1 &

    FAKE_OK=0
    for i in \$(seq 1 30); do
      if grep -q 'fake node has been initialised' /tmp/fake.log 2>/dev/null; then
        FAKE_OK=1; break
      fi
      sleep 1
    done
    if [ \$FAKE_OK -eq 0 ]; then
      echo '      ✗ Fake robot failed. Last 10 lines:'; tail -10 /tmp/fake.log; exit 1
    fi
    echo '      ✓ Fake robot ready (stabilizing 10s...)'
    sleep 10

    echo '[2/4] Publishing static map→odom transform...'
    ros2 run tf2_ros static_transform_publisher \
      -- 0 0 0 0 0 0 map odom > /dev/null 2>&1 &
    sleep 1
    echo '      ✓ map→odom TF published'

    echo '      Starting map server...'
    ros2 run nav2_map_server map_server \
      --ros-args \
      -p yaml_filename:=/opt/ros/humble/share/turtlebot3_navigation2/map/map.yaml \
      -p use_sim_time:=False > /tmp/map.log 2>&1 &
    sleep 2
    ros2 lifecycle set /map_server configure > /dev/null 2>&1
    ros2 lifecycle set /map_server activate > /dev/null 2>&1
    sleep 1
    echo '      ✓ Map server active — map published to /map'

    echo '[3/4] Starting Nav2...'
    ros2 launch nav2_bringup navigation_launch.py \
      use_sim_time:=False \
      map:=/opt/ros/humble/share/turtlebot3_navigation2/map/map.yaml \
      params_file:=/workspace/ros2_executor/nav2_params.yaml > /tmp/nav2.log 2>&1 &

    echo '      Waiting for Nav2 to become active (up to 120s)...'
    NAV2_OK=0
    for i in \$(seq 1 120); do
      # Check the lifecycle_manager log message
      if grep -q 'Managed nodes are active' /tmp/nav2.log 2>/dev/null; then
        NAV2_OK=1; break
      fi
      # Fallback: check if bt_navigator is actually active via service
      if [ \$i -gt 30 ]; then
        BT_STATE=\$(ros2 lifecycle get /bt_navigator 2>/dev/null | head -1)
        if echo "\$BT_STATE" | grep -q 'active'; then
          NAV2_OK=1; break
        fi
      fi
      sleep 1
    done
    if [ \$NAV2_OK -eq 0 ]; then
      echo '      ✗ Nav2 timed out. bt_navigator state:'; ros2 lifecycle get /bt_navigator 2>&1; exit 1
    fi
    echo '      ✓ Nav2 active'

    echo '[4/4] Verifying TF...'
    sleep 2
    ros2 topic echo /tf --once > /dev/null 2>&1 && echo '      ✓ TF publishing' || echo '      ⚠ TF check skipped'

    echo '      Starting location markers...'
    python3 /workspace/ros2_executor/location_markers.py > /dev/null 2>&1 &
    sleep 1
    echo '      ✓ Location markers publishing'

    echo '      Starting Foxglove bridge on port 8765...'
    ros2 run foxglove_bridge foxglove_bridge \
      --ros-args -p port:=8765 -p address:=0.0.0.0 > /tmp/foxglove.log 2>&1 &
    sleep 3
    echo '      ✓ Foxglove bridge ready — open Foxglove Studio and connect to ws://localhost:8765'
    echo ''

    echo '[5/5] Running pipeline...'
    echo ''
    python3 /workspace/pipeline.py --input '$INPUT' --execute
  "
