FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble

# Add OSRF Gazebo repo (needed for ignition-fortress on ARM64)
RUN apt-get update && apt-get install -y curl gnupg2 lsb-release && \
    curl https://packages.osrfoundation.org/gazebo.gpg \
      --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
      http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
      > /etc/apt/sources.list.d/gazebo-stable.list && \
    rm -rf /var/lib/apt/lists/*

# Core packages: ROS 2 + Nav2 + py_trees + TurtleBot3 + Ignition Gazebo
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    python3-z3 \
    ros-humble-nav2-bringup \
    ros-humble-nav2-msgs \
    ros-humble-nav2-common \
    ros-humble-nav2-simple-commander \
    ros-humble-turtlebot3 \
    ros-humble-turtlebot3-msgs \
    ros-humble-turtlebot3-fake-node \
    ros-humble-turtlebot3-navigation2 \
    ros-humble-py-trees \
    ros-humble-py-trees-ros \
    ros-humble-py-trees-ros-interfaces \
    ros-humble-foxglove-bridge \
    ignition-fortress \
    ros-humble-ros-ign-bridge \
    ros-humble-ros-ign-gazebo \
    && rm -rf /var/lib/apt/lists/*

# Python deps
RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install google-genai python-dotenv && \
    pip3 install --force-reinstall --break-system-packages "pytest>=8.0"

ENV TURTLEBOT3_MODEL=burger
ENV IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib

WORKDIR /workspace
COPY . /workspace/

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

SHELL ["/bin/bash", "-c"]
