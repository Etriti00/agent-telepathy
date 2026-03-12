# Universal Edge Architecture

TPCP doesn't just connect software agents. **Phase 9: The Universal Edge Expansion** provides standard bridges letting real-world hardware interfaces (robotics, smart homes, IoT sensors, and HTTP triggers) synchronize natively into the TPCP swarm.

Using bridging node adapters, hardware telemetry translates seamlessly into `CRDTSyncPayloads` or `ImagePayloads`, appearing to the AI agents as native, mathematical swarm updates.

---

## 1. The Heavy Robotics Bridge (ROS2)

**Targets:** Nvidia Jetson, autonomous drones, TurtleBot, industrial robotics.

TPCP hooks directly into ROS2 (Robot Operating System) via `rclpy`. 

### How It Works:
1. The `ROS2Adapter` spins an `rclpy` node.
2. When a physical camera (`/robot/camera_front/image_raw`) publishes a frame, `CvBridge` converts it to OpenCV.
3. The Adapter encodes it into a standard TPCP `ImagePayload` (Base64), signs it with Ed25519, and broadcasts it to the swarm as a `MEDIA_SHARE` intent.
4. When generic JSON telemetry hits `/robot/telemetry`, it is packaged into the node's LWW-Map CRDT and broadcast as a `STATE_SYNC`.

*Requirements:* `rclpy`, `cv_bridge`, `opencv-python` installed on the target edge device.

---

## 2. The Smart Home / Matter Bridge (HomeAssistant)

**Targets:** Apple HomeKit, Samsung SmartThings, Philips Hue, smart locks, thermostats.

The `HomeAssistantAdapter` bridges TPCP to local home hubs via HomeAssistant's Server-Sent Events (SSE) and extensive REST APIs.

### How It Works:
1. **Inbound SSE Stream:** The adapter connects to the HA local network stream (`/api/stream`). If a user flips a physical light switch, HA emits a physical state change. The adapter wraps this into a TPCP `CRDTSyncPayload` and forces the swarm to synchronize on the new real-world reality immediately.
2. **Outbound Execution:** If a LangGraph agent decides the house is too hot, it sends a TPCP `Task_Request` to the bridging node containing `{"domain": "climate", "service": "set_temperature", "entity_id": "climate.livingroom"}`. The adapter executes this physically via an HA REST Post locally, bypassing external cloud servers.

---

## 3. The Industrial IoT Bridge (MQTT)

**Targets:** ESP32, Arduino, Raspberry Pi Pico, standard industrial sensor grids.

The `MQTTAdapter` acts as a seamless Paho-MQTT subscriber. Countless cheap sensors use MQTT; bridging them provides raw data pipelines straight to autonomous agent logic.

### How It Works:
1. The adapter loops locally, targeting specific hardware sensor topics (e.g., `factory/floor1/temp`).
2. Incoming MQTT dictionaries are translated automatically into internal TPCP CRDT memories (`mqtt_factory_floor1_temp`).
3. Whenever the temperature changes, the TPCP system naturally propagates the change to all connected AI frameworks (CrewAI, LangGraph) using deterministic CRDT math.
4. Outbound `Task_Requests` to specific topics are intercepted by the node and seamlessly published out onto the MQTT Broker via QoS 1.

---

## 4. The Stateless Webhook Gateway

**Targets:** Siri Shortcuts, Zapier, Retool, custom iOS/Android Apps.

Sometimes, you need a quick "one-off" push into the TPCP Swarm from an external cloud provider that can't run persistent WebSockets or maintain full TPCP state tracking.

The `webhook.py` gateway is a scalable FastAPI router:
1. Accept standard HTTP `POST /webhook/intent` containing target UUIDs and raw JSON text.
2. The Gateway holds a pre-configured `AgentIdentityManager` and key.
3. The Gateway instantly wraps the raw body into a cryptographically validated TPCP payload.
4. It pushes the payload deeply into local Node routing tables, distributing the action across long-living WebSockets.

---

## Quick Setup Summary

```bash
# To utilize the Universal Edge bridging modules, ensure you have the extra dependencies:
pip install "tpcp-core[edge]"
```

*Note: ROS2 must be installed natively (via apt) containing rclpy packages specifically; Python `pip` cannot install full ROS distributions.*
