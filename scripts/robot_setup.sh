#!/usr/bin/env bash
# =============================================================================
# robot_setup.sh — Run this ON the TurtleBot2 (Kobuki) laptop.
#
# What it does:
#   1. Clones / updates the NL2BT-Verify repo
#   2. Installs Python dependencies (py_trees, z3-solver, etc.)
#   3. Creates a convenient run alias
#   4. Prints a quick-start guide
#
# Usage:
#   chmod +x robot_setup.sh && ./robot_setup.sh
# =============================================================================

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/NL2BT-Verify.git"   # ← update this
INSTALL_DIR="$HOME/NL2BT-Verify"

# ── 1. Clone or update repo ───────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Repo already exists — pulling latest …"
    git -C "$INSTALL_DIR" pull
else
    info "Cloning repo …"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── 2. Install Python dependencies ───────────────────────────────────────────
info "Installing Python dependencies …"

# Core packages (no ROS 2 / Nav2 dependencies needed on this machine)
pip3 install --user \
    py_trees==2.2.3 \
    z3-solver \
    python-dotenv \
    google-generativeai \
    openai \
    anthropic \
    lxml \
    streamlit

info "Python packages installed ✓"

# ── 3. Create .env file if missing ───────────────────────────────────────────
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    info "Creating .env file — add your API keys here:"
    cat > "$INSTALL_DIR/.env" << 'EOF'
# NL2BT-Verify API keys — fill in at least one LLM provider
GOOGLE_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
EOF
    warn ".env created — edit it: nano $INSTALL_DIR/.env"
fi

# ── 4. Confirm maps ───────────────────────────────────────────────────────────
info "Available maps on this laptop:"
find ~ -maxdepth 6 \( -name "*.yaml" \) 2>/dev/null \
    | grep -v "ros\|opt\|snap\|\.ros\|catkin_tools\|build" \
    | head -15

info "Best maps to try (from previous students):"
for m in ~/my_map4.yaml ~/ru_bri_map.yaml ~/jakedavid.yaml; do
    [[ -f "$m" ]] && echo "  → $m"
done

# ── 5. Quick-start guide ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}  Setup complete! Quick-start guide:${NC}"
echo ""
echo "  STEP 1 — Edit your API key:"
echo "    nano ~/NL2BT-Verify/.env"
echo ""
echo "  STEP 2 — Launch TurtleBot + Navigation (run in separate terminals):"
echo "    Terminal 1:  roscore"
echo "    Terminal 2:  roslaunch turtlebot_bringup minimal.launch"
echo "    Terminal 3:  roslaunch astra_launch astra.launch"
echo "    Terminal 4:  roslaunch turtlebot_navigation amcl_demo.launch \\"
echo "                   map_file:=\$HOME/my_map4.yaml"
echo ""
echo "  STEP 3 — In RViz: click '2D Pose Estimate', click where robot IS on map"
echo ""
echo "  STEP 4 — Run NL2BT pipeline:"
echo "    cd ~/NL2BT-Verify"
echo "    python3 -m pipeline"
echo "    # OR web UI (accessible from your Mac browser):"
echo "    streamlit run web_interface/app.py --server.address 0.0.0.0"
echo "    # Then open http://149.125.12.137:8501 on your Mac"
echo ""
echo "  STEP 5 — (Optional) Use the all-in-one launcher:"
echo "    chmod +x ~/NL2BT-Verify/ros1_executor/launch/hardware.sh"
echo "    ~/NL2BT-Verify/ros1_executor/launch/hardware.sh ~/my_map4.yaml"
echo -e "${GREEN}================================================================${NC}"
