#!/usr/bin/env bash
# =============================================================================
# robot_info.sh — Run this ON the robot Linux laptop.
# Collects everything needed to set up NL2BT-Verify hardware integration.
#
# HOW TO RUN:
#   1. Copy this file to the robot laptop (USB drive or scp)
#   2. chmod +x robot_info.sh
#   3. ./robot_info.sh
#   4. It saves a file called robot_info.txt in the same folder
#   5. Send that file back (or just read it)
# =============================================================================

OUT="robot_info.txt"
exec > >(tee "$OUT") 2>&1   # print to screen AND save to file

SEP="================================================================"
section() { echo ""; echo "$SEP"; echo "  $1"; echo "$SEP"; }

echo "$SEP"
echo "  NL2BT-Verify — Robot Laptop Info Collector"
echo "  $(date)"
echo "$SEP"

# ── 1. Network ────────────────────────────────────────────────────────────────
section "1. IP ADDRESS / NETWORK"
echo "--- hostname ---"
hostname
echo ""
echo "--- all IPs ---"
ip addr show | grep "inet " | awk '{print $2, $NF}'
echo ""
echo "--- WiFi SSID (connected network) ---"
nmcli -t -f active,ssid dev wifi 2>/dev/null | grep "^yes" || echo "nmcli not available"

# ── 2. OS / Hardware ─────────────────────────────────────────────────────────
section "2. OS AND HARDWARE"
echo "--- OS version ---"
lsb_release -a 2>/dev/null || cat /etc/os-release
echo ""
echo "--- CPU ---"
lscpu | grep -E "Architecture|Model name|CPU\(s\)"
echo ""
echo "--- RAM ---"
free -h | grep Mem
echo ""
echo "--- Disk space ---"
df -h /

# ── 3. ROS ────────────────────────────────────────────────────────────────────
section "3. ROS INSTALLATION"
echo "--- ROS_DISTRO ---"
printenv ROS_DISTRO || echo "NOT SET — ROS may not be sourced"
echo ""
echo "--- ROS2 binary location ---"
which ros2 || echo "ros2 not in PATH"
echo ""
echo "--- Available ROS installations ---"
ls /opt/ros/ 2>/dev/null || echo "No /opt/ros found"

# ── 4. ROS Workspaces ─────────────────────────────────────────────────────────
section "4. ROS WORKSPACES IN HOME DIRECTORY"
echo "--- Folders in ~ ---"
ls -la ~ | grep "^d"
echo ""
echo "--- Looking for ROS workspaces (install/setup.bash) ---"
find ~ -maxdepth 4 -name "setup.bash" 2>/dev/null | grep install

# ── 5. .bashrc ────────────────────────────────────────────────────────────────
section "5. BASHRC CONTENTS (what is auto-sourced)"
cat ~/.bashrc

# ── 6. Relevant ROS packages installed ───────────────────────────────────────
section "6. INSTALLED ROS PACKAGES (kobuki / nav2 / slam / realsense / tb)"
# Try sourcing ROS first
for d in /opt/ros/*/setup.bash; do source "$d" 2>/dev/null; done
find ~ -name "setup.bash" -path "*/install/*" 2>/dev/null | while read f; do
    source "$f" 2>/dev/null
done

ros2 pkg list 2>/dev/null | grep -iE "kobuki|turtlebot|nav2|slam|realsense|navigation|camera" \
    || echo "Could not list ROS packages — source ROS first"

# ── 7. USB devices (Kobuki + camera) ─────────────────────────────────────────
section "7. USB / SERIAL DEVICES"
echo "--- /dev/ttyUSB* ---"
ls -la /dev/ttyUSB* 2>/dev/null || echo "No ttyUSB devices found"
echo ""
echo "--- /dev/kobuki ---"
ls -la /dev/kobuki 2>/dev/null || echo "No /dev/kobuki symlink"
echo ""
echo "--- /dev/video* (cameras) ---"
ls -la /dev/video* 2>/dev/null || echo "No video devices found"
echo ""
echo "--- lsusb (all USB devices) ---"
lsusb 2>/dev/null || echo "lsusb not available"

# ── 8. RealSense ──────────────────────────────────────────────────────────────
section "8. INTEL REALSENSE"
echo "--- realsense library version ---"
dpkg -l | grep -i realsense 2>/dev/null || echo "realsense not installed via apt"
echo ""
echo "--- rs-enumerate-devices ---"
rs-enumerate-devices 2>/dev/null | head -20 || echo "rs-enumerate-devices not found (RealSense SDK not installed)"

# ── 9. Python ─────────────────────────────────────────────────────────────────
section "9. PYTHON"
echo "--- python versions ---"
python3 --version 2>/dev/null || echo "python3 not found"
pip3 --version   2>/dev/null || echo "pip3 not found"
echo ""
echo "--- relevant pip packages ---"
pip3 list 2>/dev/null | grep -iE "z3|streamlit|google|anthropic|openai|dotenv|py.trees|nav2" \
    || echo "Could not list pip packages"

# ── 10. Network reachability ─────────────────────────────────────────────────
section "10. NETWORK — CAN IT REACH THE INTERNET?"
echo "--- ping google.com ---"
ping -c 2 google.com 2>/dev/null && echo "Internet: REACHABLE" || echo "Internet: NOT REACHABLE"

# ── 11. Currently running ROS nodes ──────────────────────────────────────────
section "11. CURRENTLY RUNNING ROS NODES AND TOPICS"
echo "--- ros2 node list ---"
timeout 5 ros2 node list 2>/dev/null || echo "No ROS nodes running (or ROS not sourced)"
echo ""
echo "--- ros2 topic list ---"
timeout 5 ros2 topic list 2>/dev/null || echo "No topics found"

# ── 12. Existing maps ─────────────────────────────────────────────────────────
section "12. EXISTING MAP FILES"
find ~ -name "*.pgm" -o -name "*.yaml" 2>/dev/null | grep -v "ros\|opt\|snap" | head -20 \
    || echo "No map files found"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "  DONE — output saved to: $OUT"
echo "  Send this file back or paste its contents."
echo "$SEP"
