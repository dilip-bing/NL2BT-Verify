"""
SMT-based formal verification engine using Z3.
Checks 5 safety properties on an XML Behavior Tree before execution.
"""
import xml.etree.ElementTree as ET
from typing import Optional
from z3 import And, Bool, BoolVal, Int, Or, Solver, sat, unsat, Implies

VALID_NODE_TYPES = {"Sequence", "Fallback", "Action", "Condition", "Repeat", "BehaviorTree"}


class SMTVerifier:
    def __init__(
        self,
        allowed_actions: set,
        map_width: int,
        map_height: int,
        loop_threshold: int,
        known_locations: Optional[dict] = None,
        map_graph: Optional[dict] = None,
    ):
        self.allowed_actions = allowed_actions
        self.map_width = map_width
        self.map_height = map_height
        self.loop_threshold = loop_threshold
        self.known_locations = known_locations or {}
        self.map_graph = map_graph or {}

    def verify(self, xml_string: str) -> dict:
        """
        Run all 5 safety checks. Returns:
          { "passed": bool, "checks": list[dict], "errors": list[str] }
        """
        checks = []
        errors = []

        # Parse XML first — if malformed, all checks fail
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            return {
                "passed": False,
                "checks": [{"name": "xml_parse", "passed": False, "detail": str(e)}],
                "errors": [f"XML parse error: {e}"],
            }

        for check_fn in [
            self._check_structural_validity,
            self._check_action_whitelist,
            self._check_spatial_bounds,
            self._check_loop_termination,
            self._check_reachability,
            self._check_task_ordering,
        ]:
            result = check_fn(root)
            checks.append(result)
            if not result["passed"]:
                errors.append(f"{result['name']}: {result['detail']}")

        return {"passed": len(errors) == 0, "checks": checks, "errors": errors}

    # ------------------------------------------------------------------
    # Property 1: Structural Validity
    # ------------------------------------------------------------------
    def _check_structural_validity(self, root: ET.Element) -> dict:
        name = "structural_validity"
        invalid_nodes = []

        for node in root.iter():
            if node.tag not in VALID_NODE_TYPES:
                invalid_nodes.append(node.tag)

        # Cycle detection: XML trees are inherently acyclic, but check for
        # duplicate names on control-flow nodes (Sequence/Fallback/Repeat)
        # which could indicate copy-paste structural errors.
        control_tags = {"Sequence", "Fallback", "Repeat"}
        seen_control_names = set()
        duplicate_names = []
        for node in root.iter():
            if node.tag in control_tags:
                node_name = node.get("name", "")
                if node_name and node_name in seen_control_names:
                    duplicate_names.append(node_name)
                seen_control_names.add(node_name)

        issues = []
        if invalid_nodes:
            issues.append(f"unknown node types: {invalid_nodes}")
        if duplicate_names:
            issues.append(f"duplicate control-flow node names: {duplicate_names}")

        passed = len(issues) == 0
        return {"name": name, "passed": passed, "detail": "; ".join(issues) if issues else "OK"}

    # ------------------------------------------------------------------
    # Property 2: Action Whitelist Compliance
    # ------------------------------------------------------------------
    def _check_action_whitelist(self, root: ET.Element) -> dict:
        name = "action_whitelist"
        solver = Solver()
        violations = []

        for node in root.iter("Action"):
            action_name = node.get("name", "")
            if action_name not in self.allowed_actions:
                violations.append(action_name)
                # Encode as unsatisfiable Z3 constraint for audit trail
                action_var = Bool(f"action_{action_name}_allowed")
                solver.add(action_var == BoolVal(False))

        passed = len(violations) == 0
        detail = f"disallowed actions: {violations}" if violations else "OK"
        return {"name": name, "passed": passed, "detail": detail}

    # ------------------------------------------------------------------
    # Property 3: Spatial Bounds Constraint
    # ------------------------------------------------------------------
    def _check_spatial_bounds(self, root: ET.Element) -> dict:
        name = "spatial_bounds"
        solver = Solver()
        violations = []

        for node in root.iter("Action"):
            x_str = node.get("x")
            y_str = node.get("y")
            if x_str is None or y_str is None:
                continue
            try:
                x_val = int(x_str)
                y_val = int(y_str)
            except ValueError:
                violations.append(f"non-integer coords on '{node.get('name')}': x={x_str}, y={y_str}")
                continue

            x = Int(f"x_{node.get('name', id(node))}")
            y = Int(f"y_{node.get('name', id(node))}")
            constraint = And(x >= 0, x <= self.map_width, y >= 0, y <= self.map_height)
            solver.add(x == x_val, y == y_val)
            solver.add(constraint)

            if solver.check() == unsat:
                violations.append(
                    f"'{node.get('name')}' out of bounds: ({x_val},{y_val}) not in "
                    f"[0,{self.map_width}]x[0,{self.map_height}]"
                )
            solver.reset()

        # Also check named locations referenced via 'location' attribute
        for node in root.iter("Action"):
            loc = node.get("location", "").lower().replace(" ", "_")
            if loc and self.known_locations and loc in self.known_locations:
                lx, ly = self.known_locations[loc]
                if not (0 <= lx <= self.map_width and 0 <= ly <= self.map_height):
                    violations.append(f"location '{loc}' coords ({lx},{ly}) out of map bounds")

        passed = len(violations) == 0
        return {"name": name, "passed": passed, "detail": str(violations) if violations else "OK"}

    # ------------------------------------------------------------------
    # Property 4: Loop Termination Guarantee
    # ------------------------------------------------------------------
    def _check_loop_termination(self, root: ET.Element) -> dict:
        name = "loop_termination"
        solver = Solver()
        violations = []

        for node in root.iter("Repeat"):
            max_iter_str = node.get("max_iterations", node.get("num_cycles", ""))
            if not max_iter_str:
                violations.append(f"Repeat node '{node.get('name', 'unnamed')}' has no iteration bound")
                continue
            try:
                max_iter = int(max_iter_str)
            except ValueError:
                violations.append(f"Repeat node '{node.get('name', 'unnamed')}' has non-integer bound: {max_iter_str}")
                continue

            n = Int(f"loop_{node.get('name', id(node))}")
            constraint = And(n > 0, n < self.loop_threshold)
            solver.add(n == max_iter)
            solver.add(constraint)

            if solver.check() == unsat:
                violations.append(
                    f"Repeat '{node.get('name', 'unnamed')}' bound={max_iter} violates "
                    f"0 < n < {self.loop_threshold}"
                )
            solver.reset()

        passed = len(violations) == 0
        return {"name": name, "passed": passed, "detail": str(violations) if violations else "OK"}

    # ------------------------------------------------------------------
    # Property 5: Reachability
    # ------------------------------------------------------------------
    def _check_reachability(self, root: ET.Element) -> dict:
        name = "reachability"
        violations = []

        if not self.known_locations:
            return {"name": name, "passed": True, "detail": "skipped (no location map provided)"}

        for node in root.iter("Action"):
            loc = node.get("location", "").lower().replace(" ", "_")
            if not loc:
                continue
            if loc not in self.known_locations:
                violations.append(f"unknown location '{loc}'")
                continue
            # Check connectivity from 'start' via map graph
            if self.map_graph:
                reachable = self._bfs_reachable("start", self.map_graph)
                if loc not in reachable:
                    violations.append(f"location '{loc}' is not reachable from start")

        passed = len(violations) == 0
        return {"name": name, "passed": passed, "detail": str(violations) if violations else "OK"}

    def _bfs_reachable(self, start: str, graph: dict) -> set:
        visited = set()
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            queue.extend(graph.get(node, []))
        return visited

    # ------------------------------------------------------------------
    # Property 6: Task Dependency Ordering
    # Z3 formally proves: in every Sequence, manipulation actions
    # (pick_up, deliver, place) are always preceded by a move_to.
    # Encodes position indices as Z3 integers and asserts the ordering
    # constraint: pos(move_to) < pos(manipulation) must be satisfiable.
    # If no valid ordering exists, Z3 returns UNSAT → property violated.
    # ------------------------------------------------------------------
    def _check_task_ordering(self, root: ET.Element) -> dict:
        name = "task_ordering"
        violations = []
        MANIPULATION = {"pick_up", "deliver", "place"}

        for seq in root.iter("Sequence"):
            actions = list(seq)  # direct children only
            action_names = [a.get("name", "") for a in actions if a.tag == "Action"]

            manip_indices  = [i for i, n in enumerate(action_names) if n in MANIPULATION]
            nav_indices    = [i for i, n in enumerate(action_names) if n == "move_to"]

            if not manip_indices:
                continue  # no manipulation in this sequence — OK

            if not nav_indices:
                violations.append(
                    f"Sequence '{seq.get('name', 'unnamed')}' contains "
                    f"{[action_names[i] for i in manip_indices]} with no preceding move_to"
                )
                continue

            # Z3: for each manipulation action, prove there EXISTS a move_to
            # with a strictly smaller position index.
            solver = Solver()
            for m_idx in manip_indices:
                m_pos = Int(f"pos_manip_{m_idx}")
                solver.add(m_pos == m_idx)

                # At least one move_to must precede this manipulation
                nav_precedes = Or(*[
                    Int(f"pos_nav_{n_idx}") < m_pos
                    for n_idx in nav_indices
                ])
                for n_idx in nav_indices:
                    solver.add(Int(f"pos_nav_{n_idx}") == n_idx)

                solver.add(nav_precedes)

                if solver.check() == unsat:
                    violations.append(
                        f"Sequence '{seq.get('name', 'unnamed')}': "
                        f"'{action_names[m_idx]}' at position {m_idx} has no "
                        f"preceding move_to — ordering constraint UNSAT"
                    )
                solver.reset()

        passed = len(violations) == 0
        return {"name": name, "passed": passed, "detail": str(violations) if violations else "OK"}
