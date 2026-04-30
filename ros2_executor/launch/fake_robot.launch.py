"""
Custom launch file for TurtleBot3 fake node without gazebo dependency.
Starts: robot_state_publisher (with xacro) + turtlebot3_fake_node
"""
import os
import subprocess
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

FAKE_NODE_PARAMS = os.path.join(
    get_package_share_directory("turtlebot3_fake_node"),
    "param", "burger.yaml"
)

URDF_FILE = os.path.join(
    get_package_share_directory("turtlebot3_description"),
    "urdf", "turtlebot3_burger.urdf"
)

# Process xacro to resolve ${namespace} → ""
def get_robot_description():
    result = subprocess.run(
        ["xacro", URDF_FILE, "namespace:="],
        capture_output=True, text=True
    )
    return result.stdout


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time", default="false")
    robot_description = get_robot_description()

    return LaunchDescription([
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="false",
            description="Use simulation time",
        ),

        # Publishes TF tree from processed URDF
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{
                "use_sim_time": use_sim_time,
                "robot_description": robot_description,
            }],
        ),

        # Fake node — simulates odometry and TF without physics
        Node(
            package="turtlebot3_fake_node",
            executable="turtlebot3_fake_node",
            name="turtlebot3_fake_node",
            output="screen",
            parameters=[
                FAKE_NODE_PARAMS,
                {"use_sim_time": use_sim_time},
            ],
        ),
    ])
