#!/bin/bash
# Starts fake robot + Nav2 inside a single container and waits until Nav2 is active.
set -e

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger

echo ""
echo "================================================"
echo " NL2BT-Verify — ROS 2 Stack Startup"
echo "================================================"

# ── 1. Fake robot ────────────────────────────────────
echo "[1/3] Starting fake robot (robot_state_publisher + fake node)..."
ros2 launch /workspace/ros2_executor/launch/fake_robot.launch.py \
  > /tmp/fake_robot.log 2>&1 &
FAKE_PID=$!

# Wait until fake node says it's initialised
for i in $(seq 1 20); do
  if grep -q "Turtlebot3 fake node has been initialised" /tmp/fake_robot.log 2>/dev/null; then
    echo "    ✓ Fake robot ready"
    break
  fi
  sleep 1
  if [ $i -eq 20 ]; then
    echo "    ✗ Fake robot failed to start. Log:"
    cat /tmp/fake_robot.log
    exit 1
  fi
done

# ── 2. Nav2 ──────────────────────────────────────────
echo "[2/3] Starting Nav2..."
ros2 launch nav2_bringup navigation_launch.py \
  use_sim_time:=True \
  map:=/opt/ros/humble/share/turtlebot3_navigation2/map/map.yaml \
  params_file:=/workspace/ros2_executor/nav2_params.yaml \
  > /tmp/nav2.log 2>&1 &
NAV2_PID=$!

# Wait until Nav2 lifecycle manager says nodes are active
echo "    Waiting for Nav2 to become active (up to 60s)..."
for i in $(seq 1 60); do
  if grep -q "Managed nodes are active" /tmp/nav2.log 2>/dev/null; then
    echo "    ✓ Nav2 active"
    break
  fi
  # Check for fatal errors
  if grep -q "FATAL\|Aborting bringup" /tmp/nav2.log 2>/dev/null; then
    echo "    ✗ Nav2 failed. Last 20 lines:"
    tail -20 /tmp/nav2.log
    kill $FAKE_PID $NAV2_PID 2>/dev/null
    exit 1
  fi
  sleep 1
  if [ $i -eq 60 ]; then
    echo "    ✗ Nav2 timed out. Last 20 lines:"
    tail -20 /tmp/nav2.log
    kill $FAKE_PID $NAV2_PID 2>/dev/null
    exit 1
  fi
done

# ── 3. Verify TF ─────────────────────────────────────
echo "[3/3] Verifying TF tree..."
TF_CHECK=$(timeout 5 ros2 run tf2_ros tf2_echo odom base_footprint 2>&1 | head -5 || true)
if echo "$TF_CHECK" | grep -q "Translation\|transform"; then
  echo "    ✓ TF working: odom → base_footprint"
else
  echo "    ✗ TF check failed:"
  echo "$TF_CHECK"
  echo ""
  echo "    Checking available frames..."
  ros2 run tf2_tools view_frames 2>/dev/null || true
fi

echo ""
echo "================================================"
echo " Stack is UP. Run your pipeline in this shell:"
echo " python3 /workspace/pipeline.py --input 'Go to Room A' --execute"
echo "================================================"
echo ""

# Keep logs streaming so you can see what's happening
tail -f /tmp/fake_robot.log /tmp/nav2.log
