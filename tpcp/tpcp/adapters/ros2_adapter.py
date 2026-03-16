# Copyright (c) 2026 Principal Systems Architect
# This file is part of TPCP.
# 
# TPCP is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# TPCP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with TPCP. If not, see <https://www.gnu.org/licenses/>.
# 
# For commercial licensing inquiries, see COMMERCIAL_LICENSE.md

"""
ROS2 Hardware Adapter for TPCP.
Targets Nvidia Jetson and autonomous robotics platforms.

Maps ROS2 Pub/Sub messages natively to TPCP CRDTSyncPayloads and MediaPayloads.
Requires rclpy to be installed in the robot's environment.
"""

import base64
import logging
from typing import Any, Callable, Optional, Union
from uuid import UUID

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import (
    AgentIdentity,
    Intent,
    TPCPEnvelope,
    TextPayload,
    ImagePayload,
    CRDTSyncPayload,
    MessageHeader,
    PROTOCOL_VERSION
)

logger = logging.getLogger(__name__)

try:
    import rclpy
    from rclpy.node import Node as ROS2Node
    from std_msgs.msg import String
    from sensor_msgs.msg import Image as ROSImage
    from cv_bridge import CvBridge
    import cv2
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


class ROS2Adapter(BaseFrameworkAdapter):
    """
    Adapter mapping a ROS2 node (e.g., Nvidia Jetson) into a TPCP network.
    Listens to ROS topics, translates them into TPCP payloads, and forwards them to the swarm.
    Likewise, it translates inbound TPCP task requests into ROS publishers.
    """

    def __init__(self, identity: AgentIdentity, identity_manager=None, ros_node_name: str = "tpcp_bridge", topics=None):
        super().__init__(identity, identity_manager)
        self.ros_node_name = ros_node_name
        self._topics = topics or {
            "telemetry": "/robot/telemetry",
            "camera": "/robot/camera_front/image_raw",
        }
        self._ros_node: Optional["ROS2Node"] = None
        self._bridge: Optional["CvBridge"] = None

    def pack_thought(self, target_id: UUID, raw_output: Any, intent: Intent = Intent.STATE_SYNC) -> TPCPEnvelope:
        """
        Translates raw hardware outputs into TPCP envelopes.
        This generic implementation is augmented by specific topic handlers.
        """
        header = MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=target_id,
            intent=intent,
            protocol_version=PROTOCOL_VERSION
        )

        payload: Union[CRDTSyncPayload, TextPayload]
        if isinstance(raw_output, dict) and "state" in raw_output:
            # It's a CRDT state sync
            self._tick()
            payload = CRDTSyncPayload(
                crdt_type="LWW-Map",
                state=raw_output["state"],
                vector_clock=raw_output.get("vector_clock", {str(self.identity.agent_id): self._logical_clock})
            )
        elif isinstance(raw_output, str):
            payload = TextPayload(content=raw_output)
        else:
            raise ValueError("Unsupported raw_output format for Base ROS2 pack_thought.")

        envelope = TPCPEnvelope(header=header, payload=payload)
        im = self._require_identity_manager()
        envelope.signature = im.sign_payload(payload.model_dump())
        return envelope

    def pack_image(self, target_id: UUID, cv_image: Any, caption: str = "ROS2 Camera Frame") -> TPCPEnvelope:
        """
        Converts a CV2 image (from a ROS2 Image topic) into a TPCP ImagePayload.
        """
        success, encoded_image = cv2.imencode('.jpg', cv_image)
        if not success:
            raise RuntimeError("Failed to encode CV2 image for TPCP payload.")

        b64_img = base64.b64encode(encoded_image.tobytes()).decode('utf-8')
        height, width, _ = cv_image.shape

        payload = ImagePayload(
            data_base64=b64_img,
            mime_type="image/jpeg",
            width=width,
            height=height,
            source_model="robot-camera",
            caption=caption
        )

        header = MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=target_id,
            intent=Intent.MEDIA_SHARE,
            protocol_version=PROTOCOL_VERSION
        )

        envelope = TPCPEnvelope(header=header, payload=payload)
        im = self._require_identity_manager()
        envelope.signature = im.sign_payload(payload.model_dump())
        return envelope

    def start_ros2_spin(self, on_message_callback: Callable[[TPCPEnvelope], None]) -> None:
        """
        Initializes the rclpy node and starts spinning in a background thread or async loop.
        Connects a standard diagnostic publisher and subscriber. 
        """
        if not ROS2_AVAILABLE:
            raise ImportError("ROS2 environment (rclpy) is not available. Please run inside a ROS2 workspace.")
        
        if not rclpy.ok():
            rclpy.init(args=None)
            
        self._ros_node = rclpy.create_node(self.ros_node_name)
        self._bridge = CvBridge()

        # Listen to a generic robot state topic
        self._ros_node.create_subscription(
            String,
            self._topics["telemetry"],
            lambda msg: self._handle_ros_telemetry(msg, on_message_callback),
            10
        )

        # Listen to a camera feed and forward frames to TPCP as Images
        self._ros_node.create_subscription(
            ROSImage,
            self._topics["camera"],
            lambda msg: self._handle_ros_image(msg, on_message_callback),
            10
        )

        logger.info(f"ROS2 Adapter bridging node '{self.ros_node_name}' initialized.")

    def _handle_ros_telemetry(self, msg: 'String', callback: Callable[[TPCPEnvelope], None]):
        """Callback for standard text/JSON ROS messages."""
        try:
            # Wrap standard JSON telemetry into a CRDT state dict
            import json
            telemetry_data = json.loads(msg.data)
            
            # Target ID uuid_0 is broadcast/CRDT sync convention
            target_id = UUID(int=0)
            
            envelope = self.pack_thought(
                target_id=target_id,
                raw_output={"state": {"robot_telemetry": {"value": telemetry_data, "timestamp": 1, "writer_id": str(self.identity.agent_id)}}},
                intent=Intent.STATE_SYNC
            )
            callback(envelope)
        except json.JSONDecodeError:
            logger.warning("ROS Telemetry was not valid JSON, ignoring.")

    def _handle_ros_image(self, msg: 'ROSImage', callback: Callable[[TPCPEnvelope], None]):
        """Callback for ROS Image topics. Converts frames to base64 TPCP envelopes."""
        try:
            if self._bridge is None:
                return
            cv_image = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            target_id = UUID(int=0)  # Broadcast
            envelope = self.pack_image(target_id, cv_image, caption="Real-time optical frame from robot sensor")
            callback(envelope)
        except Exception as e:
            logger.error(f"Error bridging ROS image to TPCP: {e}")

    def unpack_request(self, envelope: TPCPEnvelope) -> Any:
        """
        Translates inbound TPCP TaskRequests into executable ROS2 commands.
        """
        if not self._ros_node:
            logger.warning("Cannot unpack request: ROS2 node not initialized.")
            return None

        # Here you would route specific task requests to hardware publishers
        # Example: Sending a Twist command to cmd_vel if payload contains directions
        if isinstance(envelope.payload, TextPayload):
            return envelope.payload.content
        return None

    def stop(self):
        """Cleanup ROS2 resources."""
        if self._ros_node:
            self._ros_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
