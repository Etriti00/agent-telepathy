"""
MockTPCPNode — in-process TPCP node for unit testing.

Does not open any network sockets. Messages are delivered by direct
in-process method calls. Use MockTPCPNode.connect_pair() to link two mock nodes.
"""
from __future__ import annotations
import asyncio
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID
from tpcp.schemas.envelope import (
    AgentIdentity, Intent, TPCPEnvelope, MessageHeader
)


class MockTPCPNode:
    """
    In-process mock TPCP node for unit testing — no network sockets.

    Usage::

        alice, bob = MockTPCPNode.connect_pair()

        received = []
        bob.register_handler(Intent.TASK_REQUEST, lambda env: received.append(env))

        await alice.send_message(bob.agent_id, Intent.TASK_REQUEST,
                                 TextPayload(content="hello"))
        assert len(received) == 1
    """

    def __init__(self, framework: str = "mock-agent"):
        self.identity = AgentIdentity(
            framework=framework,
            public_key="",
        )
        self.agent_id: UUID = self.identity.agent_id
        self._handlers: Dict[Intent, List[Callable]] = {}
        self._peers: Dict[UUID, "MockTPCPNode"] = {}
        self.sent: List[TPCPEnvelope] = []   # all envelopes sent by this node
        self.received: List[TPCPEnvelope] = []  # all envelopes received by this node
        self.dlq: List[TPCPEnvelope] = []  # unhandled envelopes

    @classmethod
    def connect_pair(cls, type_a: str = "mock-a", type_b: str = "mock-b"):
        """Create two mock nodes linked to each other."""
        a = cls(framework=type_a)
        b = cls(framework=type_b)
        a._peers[b.agent_id] = b
        b._peers[a.agent_id] = a
        return a, b

    def register_handler(self, intent: Intent, handler: Callable[[TPCPEnvelope], Any]):
        self._handlers.setdefault(intent, []).append(handler)

    async def send_message(
        self,
        target_id: UUID,
        intent: Intent,
        payload: Any,
    ) -> Optional[TPCPEnvelope]:
        """Deliver a message directly to the target mock node."""
        header = MessageHeader(
            sender_id=self.agent_id,
            receiver_id=target_id,
            intent=intent,
        )
        envelope = TPCPEnvelope(header=header, payload=payload)

        target = self._peers.get(target_id)
        if target is None:
            raise ValueError(f"No peer with id {target_id}")

        self.sent.append(envelope)
        await target._receive(envelope)
        return envelope

    async def _receive(self, envelope: TPCPEnvelope):
        """Internal: receive and dispatch an envelope."""
        self.received.append(envelope)
        handlers = self._handlers.get(envelope.header.intent, [])
        if not handlers:
            self.dlq.append(envelope)
            return
        for handler in handlers:
            result = handler(envelope)
            if asyncio.iscoroutine(result):
                await result

    def assert_received(self, intent: Intent, count: int = 1):
        """Test helper: assert this node received `count` messages with `intent`."""
        actual = [e for e in self.received if e.header.intent == intent]
        assert len(actual) == count, (
            f"Expected {count} {intent} messages, got {len(actual)}"
        )

    def assert_sent(self, intent: Intent, count: int = 1):
        """Test helper: assert this node sent `count` messages with `intent`."""
        actual = [e for e in self.sent if e.header.intent == intent]
        assert len(actual) == count, (
            f"Expected {count} sent {intent} messages, got {len(actual)}"
        )

    def clear(self):
        """Reset sent/received/dlq lists."""
        self.sent.clear()
        self.received.clear()
        self.dlq.clear()
