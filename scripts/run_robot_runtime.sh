#!/usr/bin/env bash
set -eo pipefail

RUNTIME_WORKDIR="${ROBOT_RUNTIME_WORKDIR:-/opt/robot_ws}"
ROS_SETUP="${ROBOT_RUNTIME_ROS_SETUP:-/opt/ros/humble/setup.bash}"
WORKSPACE_SETUP="${ROBOT_RUNTIME_WORKSPACE_SETUP:-/opt/robot_ws/install/setup.bash}"
LAUNCH_COMMAND="${ROBOT_RUNTIME_LAUNCH_COMMAND:-ros2 launch robot_bringup bringup.launch.py}"

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "Missing ROS setup file: ${ROS_SETUP}" >&2
  exit 1
fi

if [[ ! -f "${WORKSPACE_SETUP}" ]]; then
  echo "Missing workspace install setup file: ${WORKSPACE_SETUP}" >&2
  exit 1
fi

if [[ -z "${LAUNCH_COMMAND}" ]]; then
  echo "ROBOT_RUNTIME_LAUNCH_COMMAND must not be empty" >&2
  exit 1
fi

cd "${RUNTIME_WORKDIR}"
# ROS setup scripts may reference unset vars; avoid nounset failures while sourcing.
set +u
source "${ROS_SETUP}"
source "${WORKSPACE_SETUP}"
set -u

exec bash -lc "${LAUNCH_COMMAND}"
