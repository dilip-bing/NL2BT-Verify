"""
End-to-end pipeline: Natural Language → XML BT → SMT Verify → ROS 2 Execute
"""
import argparse
import sys
import time
from llm_module.llm_client import generate_behavior_tree
from verification.smt_verifier import SMTVerifier
from verification.config import ALLOWED_ACTIONS, MAP_WIDTH, MAP_HEIGHT, LOOP_THRESHOLD


def run_pipeline(nl_input: str, execute: bool = False) -> dict:
    print(f"\n[Stage 1] LLM Translation")
    print(f"  Input: {nl_input}")
    t0 = time.perf_counter()
    xml_bt = generate_behavior_tree(nl_input)
    llm_ms = (time.perf_counter() - t0) * 1000
    if not xml_bt:
        return {"status": "error", "stage": "llm", "message": "LLM failed to generate BT"}
    print(f"  Output XML BT generated ({len(xml_bt)} chars) in {llm_ms:.0f} ms")

    print(f"\n[Stage 2] SMT Verification")
    verifier = SMTVerifier(
        allowed_actions=ALLOWED_ACTIONS,
        map_width=MAP_WIDTH,
        map_height=MAP_HEIGHT,
        loop_threshold=LOOP_THRESHOLD,
    )
    t1 = time.perf_counter()
    result = verifier.verify(xml_bt)
    smt_ms = (time.perf_counter() - t1) * 1000
    if not result["passed"]:
        print(f"  REJECTED in {smt_ms:.1f} ms: {result['errors']}")
        for chk in result["checks"]:
            icon = "✓" if chk["passed"] else "✗"
            print(f"    [{icon}] {chk['name']}: {chk['detail']}")
        return {"status": "rejected", "stage": "verification", "errors": result["errors"], "xml": xml_bt}
    print(f"  PASSED all {len(result['checks'])} safety properties in {smt_ms:.1f} ms")
    for chk in result["checks"]:
        print(f"    [✓] {chk['name']}: {chk['detail']}")

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
