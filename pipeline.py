"""
End-to-end pipeline: Natural Language → XML BT → SMT Verify → ROS 2 Execute
"""
import argparse
import sys
from llm_module.llm_client import generate_behavior_tree
from verification.smt_verifier import SMTVerifier
from verification.config import ALLOWED_ACTIONS, MAP_WIDTH, MAP_HEIGHT, LOOP_THRESHOLD


def run_pipeline(nl_input: str, execute: bool = False) -> dict:
    print(f"\n[Stage 1] LLM Translation")
    print(f"  Input: {nl_input}")
    xml_bt = generate_behavior_tree(nl_input)
    if not xml_bt:
        return {"status": "error", "stage": "llm", "message": "LLM failed to generate BT"}
    print(f"  Output XML BT generated ({len(xml_bt)} chars)")

    print(f"\n[Stage 2] SMT Verification")
    verifier = SMTVerifier(
        allowed_actions=ALLOWED_ACTIONS,
        map_width=MAP_WIDTH,
        map_height=MAP_HEIGHT,
        loop_threshold=LOOP_THRESHOLD,
    )
    result = verifier.verify(xml_bt)
    if not result["passed"]:
        print(f"  REJECTED: {result['errors']}")
        return {"status": "rejected", "stage": "verification", "errors": result["errors"], "xml": xml_bt}
    print(f"  PASSED all {len(result['checks'])} safety properties")

    if execute:
        print(f"\n[Stage 3] ROS 2 Execution")
        # Import only when ROS 2 is available
        from ros2_executor.bt_executor import execute_behavior_tree
        execute_behavior_tree(xml_bt)

    return {"status": "success", "xml": xml_bt, "checks": result["checks"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NL2BT-Verify Pipeline")
    parser.add_argument("--input", type=str, required=True, help="Natural language command")
    parser.add_argument("--execute", action="store_true", help="Execute on robot after verification")
    args = parser.parse_args()

    result = run_pipeline(args.input, execute=args.execute)
    if result["status"] == "success":
        print("\n[Done] Verified BT:")
        print(result["xml"])
    else:
        print(f"\n[Failed] {result}")
        sys.exit(1)
