# NL2BT-Verify: Natural Language to Behavior Tree Compiler

A Neuro-Symbolic compiler that translates plain English commands into verified, executable robot Behavior Trees.

## Pipeline
```
NL Input → LLM (Claude/GPT-4) → XML Behavior Tree → SMT Verifier (Z3) → ROS 2 Executor (py_trees_ros) → Gazebo
```

## Team
- **Riddhi Jain** — LLM module, web interface, benchmark dataset
- **Dilip Kumar** — SMT verification engine, ROS 2 executor, Gazebo integration

## Project Structure
```
NL2BT-Verify/
├── llm_module/          # Stage 1: LLM → XML BT
├── verification/        # Stage 2: SMT/Z3 safety checks
├── ros2_executor/       # Stage 3: py_trees_ros + Nav2
├── web_interface/       # Streamlit UI
├── benchmark/           # 100+ NL command dataset
├── tests/               # Unit + integration tests
└── pipeline.py          # End-to-end entry point
```

## Setup

### Prerequisites
- Ubuntu 22.04
- ROS 2 Humble
- Python 3.10+

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the pipeline
```bash
python pipeline.py --input "Go to Room A and pick up the box"
```

### Run the web interface
```bash
streamlit run web_interface/app.py
```

## Evaluation Targets
| Metric | Target |
|--------|--------|
| Syntax Accuracy | ≥ 90% |
| Safety Verification Rate | 100% |
| Task Success Rate (Gazebo) | ≥ 85% |
