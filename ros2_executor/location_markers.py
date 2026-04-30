"""
Publishes visualization markers for all named locations on the map.
Box animates: on shelf → disappears on pickup → follows robot → appears at destination.
"""
import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import String, ColorRGBA
from nav_msgs.msg import Odometry

LOCATIONS = {
    "Room A":           (1.0,  1.0,  0.2, 1.0, 0.2),
    "Room B":           (3.0,  1.0,  0.2, 0.4, 1.0),
    "Room C":           (1.0,  3.0,  1.0, 0.8, 0.2),
    "Room D":           (3.0,  3.0,  1.0, 0.4, 0.2),
    "Shelf 1":          (1.5,  1.5,  0.8, 0.2, 0.8),
    "Shelf 2":          (2.0,  1.5,  0.8, 0.2, 0.8),
    "Shelf 3":          (2.5,  1.5,  0.8, 0.2, 0.8),
    "Shelf 4":          (1.5,  2.5,  0.8, 0.2, 0.8),
    "Shelf 5":          (2.0,  2.5,  0.8, 0.2, 0.8),
    "Loading Dock":     (2.0,  0.5,  1.0, 0.2, 0.2),
    "Charging Station": (0.5,  0.5,  0.2, 0.9, 0.9),
    "Start":            (0.0,  0.0,  0.9, 0.9, 0.9),
}

BOX_HOME = (1.5, 1.5)   # Shelf 1
DELIVER_SPOT = (2.0, 0.5)  # Loading Dock


class LocationMarkerPublisher(Node):
    def __init__(self):
        super().__init__("location_marker_publisher")
        self.pub = self.create_publisher(MarkerArray, "/location_markers", 10)
        self.create_subscription(String, "/box_state", self._on_box_state, 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)

        self.box_state = "on_shelf"   # on_shelf | picking_up | carried | placed | delivered
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.box_x = BOX_HOME[0]
        self.box_y = BOX_HOME[1]

        self.create_timer(0.2, self.publish_markers)  # 5Hz
        self.get_logger().info("Location marker publisher started")

    def _on_box_state(self, msg: String):
        prev = self.box_state
        self.box_state = msg.data
        if self.box_state != prev:
            self.get_logger().info(f"Box state: {prev} → {self.box_state}")

        if self.box_state == "on_shelf":
            self.box_x, self.box_y = BOX_HOME
        elif self.box_state in ("placed", "delivered"):
            self.box_x, self.box_y = DELIVER_SPOT

    def _on_odom(self, msg: Odometry):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y
        # Box follows robot when carried
        if self.box_state == "carried":
            self.box_x = self.robot_x + 0.15
            self.box_y = self.robot_y + 0.15

    def publish_markers(self):
        markers = MarkerArray()
        mid = 0

        # Location spheres + labels
        for name, (x, y, r, g, b) in LOCATIONS.items():
            sphere = Marker()
            sphere.header.frame_id = "map"
            sphere.header.stamp = self.get_clock().now().to_msg()
            sphere.ns = "locations"
            sphere.id = mid
            sphere.type = Marker.SPHERE
            sphere.action = Marker.ADD
            sphere.pose.position.x = x
            sphere.pose.position.y = y
            sphere.pose.position.z = 0.1
            sphere.pose.orientation.w = 1.0
            sphere.scale.x = sphere.scale.y = sphere.scale.z = 0.2
            sphere.color = ColorRGBA(r=r, g=g, b=b, a=0.85)
            sphere.lifetime.sec = 1
            markers.markers.append(sphere)
            mid += 1

            text = Marker()
            text.header.frame_id = "map"
            text.header.stamp = self.get_clock().now().to_msg()
            text.ns = "location_labels"
            text.id = mid
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = x
            text.pose.position.y = y
            text.pose.position.z = 0.45
            text.pose.orientation.w = 1.0
            text.scale.z = 0.14
            text.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0)
            text.text = name
            text.lifetime.sec = 1
            markers.markers.append(text)
            mid += 1

        # Box marker — animated based on state
        if self.box_state != "picking_up":
            box_color = {
                "on_shelf":  ColorRGBA(r=1.0, g=0.5, b=0.0, a=1.0),   # orange
                "carried":   ColorRGBA(r=0.0, g=1.0, b=0.3, a=1.0),   # green (being carried)
                "placed":    ColorRGBA(r=0.2, g=0.6, b=1.0, a=1.0),   # blue (delivered)
                "delivered": ColorRGBA(r=0.2, g=0.6, b=1.0, a=1.0),
            }.get(self.box_state, ColorRGBA(r=1.0, g=0.5, b=0.0, a=1.0))

            box = Marker()
            box.header.frame_id = "map"
            box.header.stamp = self.get_clock().now().to_msg()
            box.ns = "box"
            box.id = mid
            box.type = Marker.CUBE
            box.action = Marker.ADD
            box.pose.position.x = self.box_x
            box.pose.position.y = self.box_y
            box.pose.position.z = 0.12
            box.pose.orientation.w = 1.0
            box.scale.x = box.scale.y = box.scale.z = 0.18
            box.color = box_color
            box.lifetime.sec = 1
            markers.markers.append(box)
            mid += 1

            # Box label
            state_labels = {
                "on_shelf":  "Box",
                "carried":   "Box [carried]",
                "placed":    "Box [delivered]",
                "delivered": "Box [delivered]",
            }
            label = Marker()
            label.header.frame_id = "map"
            label.header.stamp = self.get_clock().now().to_msg()
            label.ns = "box_label"
            label.id = mid
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose.position.x = self.box_x
            label.pose.position.y = self.box_y
            label.pose.position.z = 0.4
            label.pose.orientation.w = 1.0
            label.scale.z = 0.13
            label.color = ColorRGBA(r=1.0, g=1.0, b=0.0, a=1.0)
            label.text = state_labels.get(self.box_state, "Box")
            label.lifetime.sec = 1
            markers.markers.append(label)

        self.pub.publish(markers)


def main():
    rclpy.init()
    node = LocationMarkerPublisher()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
