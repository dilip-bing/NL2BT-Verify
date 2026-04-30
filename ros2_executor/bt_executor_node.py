"""
ROS 2 node that loads a verified XML BT and ticks it via py_trees_ros.
Run with: python3 ros2_executor/bt_executor_node.py <xml_file_or_string>
"""
import sys
import rclpy
from rclpy.node import Node
import py_trees
import py_trees_ros
from nav2_simple_commander.robot_navigator import BasicNavigator
from ros2_executor.xml_loader import load_tree_from_xml


class BTExecutorNode(Node):
    def __init__(self, xml_string: str):
        super().__init__("bt_executor")
        self.xml_string = xml_string
        self.navigator = None
        self.tree = None
        # Tick the BT at 10 Hz
        self.timer = self.create_timer(0.1, self._tick)
        self.get_logger().info("BTExecutorNode started")

    def setup(self):
        self.navigator = BasicNavigator()
        # Nav2 is already confirmed active before the pipeline runs (checked in run.sh).
        # Calling waitUntilNav2Active() here blocks because the lifecycle service
        # discovery requires a running executor — skip it and proceed directly.
        self.get_logger().info("Nav2 already active — building behavior tree")

        from std_msgs.msg import String
        self.box_pub = self.create_publisher(String, "/box_state", 10)
        # Box starts on shelf_1
        msg = String(); msg.data = "on_shelf"
        self.box_pub.publish(msg)

        root = load_tree_from_xml(self.xml_string, navigator=self.navigator, box_pub=self.box_pub)
        self.tree = py_trees_ros.trees.BehaviourTree(root=root, unicode_tree_debug=True)
        self.tree.setup(timeout=15.0)
        self.get_logger().info("Behavior tree ready — starting execution")

    def _tick(self):
        if self.tree is None:
            return

        self.tree.tick()
        status = self.tree.root.status

        if status == py_trees.common.Status.SUCCESS:
            self.get_logger().info("Task COMPLETED successfully")
            self.timer.cancel()
            rclpy.shutdown()

        elif status == py_trees.common.Status.FAILURE:
            self.get_logger().error("Task FAILED")
            self.timer.cancel()
            rclpy.shutdown()


def execute_behavior_tree(xml_string: str):
    """Entry point called from pipeline.py Stage 3."""
    rclpy.init()
    node = BTExecutorNode(xml_string)
    node.setup()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 bt_executor_node.py <xml_file>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        xml = f.read()

    execute_behavior_tree(xml)
