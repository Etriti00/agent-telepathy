import pytest
from uuid import uuid4
from tpcp.schemas.envelope import AgentIdentity, Intent
from tpcp.adapters.mqtt_adapter import MQTTAdapter


def test_adapter_raises_without_identity_manager():
    identity = AgentIdentity(framework="test", public_key="AAAA" * 11)
    adapter = MQTTAdapter(identity, broker_host="localhost", identity_manager=None)
    with pytest.raises(RuntimeError, match="identity_manager is required"):
        adapter.pack_thought(uuid4(), {"topic": "test", "payload": "val"}, Intent.TASK_REQUEST)


def test_mqtt_topic_whitelist_blocks_disallowed():
    identity = AgentIdentity(framework="test", public_key="AAAA" * 11)
    adapter = MQTTAdapter(identity, broker_host="localhost", allowed_topics=["sensors/temp"])
    assert not adapter._is_topic_allowed("sensors/pressure")


def test_mqtt_topic_whitelist_allows_permitted():
    identity = AgentIdentity(framework="test", public_key="AAAA" * 11)
    adapter = MQTTAdapter(identity, broker_host="localhost", allowed_topics=["sensors/temp"])
    assert adapter._is_topic_allowed("sensors/temp")


def test_mqtt_no_whitelist_allows_all():
    identity = AgentIdentity(framework="test", public_key="AAAA" * 11)
    adapter = MQTTAdapter(identity, broker_host="localhost")
    assert adapter._is_topic_allowed("any/topic")
