"""
TPCP Per-Agent Access Control List (ACL).

Allows fine-grained control over which agents may send which intents to this node.
Critical for safety: use ACL to prevent untrusted agents from sending TERMINATE
to a safety-critical robot or industrial controller node.
"""
from __future__ import annotations

from typing import Dict, Tuple
from uuid import UUID

from tpcp.schemas.envelope import Intent


class ACLPolicy:
    """
    Per-agent access control policy for a TPCPNode.

    Rules are stored as (agent_id, intent) -> bool.
    The default_allow parameter controls behavior when no specific rule exists.

    Usage::

        policy = ACLPolicy(default_allow=True)
        # Block all agents from sending TERMINATE (safety-critical protection)
        policy.deny_all(Intent.TERMINATE)
        # Allow a specific trusted agent to send TERMINATE
        policy.allow(trusted_agent_uuid, Intent.TERMINATE)
    """

    def __init__(self, default_allow: bool = True) -> None:
        self.default_allow = default_allow
        # Maps (agent_id, intent) -> True (allow) or False (deny)
        self._rules: Dict[Tuple[UUID, Intent], bool] = {}
        # Maps intent -> bool for intent-wide rules (no specific agent)
        self._intent_rules: Dict[Intent, bool] = {}

    def allow(self, agent_id: UUID, intent: Intent) -> None:
        """Explicitly allow agent_id to send intent to this node."""
        self._rules[(agent_id, intent)] = True

    def deny(self, agent_id: UUID, intent: Intent) -> None:
        """Explicitly deny agent_id from sending intent to this node."""
        self._rules[(agent_id, intent)] = False

    def allow_all(self, intent: Intent) -> None:
        """Allow all agents to send this intent (overrides default_allow=False for this intent)."""
        self._intent_rules[intent] = True

    def deny_all(self, intent: Intent) -> None:
        """Deny all agents from sending this intent (e.g., block TERMINATE globally)."""
        self._intent_rules[intent] = False

    def is_allowed(self, agent_id: UUID, intent: Intent) -> bool:
        """
        Return True if agent_id is allowed to send intent to this node.

        Lookup order:
        1. Specific (agent_id, intent) rule — highest precedence
        2. Intent-wide rule (deny_all / allow_all)
        3. default_allow — lowest precedence
        """
        # Specific per-agent rule takes highest precedence
        rule = self._rules.get((agent_id, intent))
        if rule is not None:
            return rule
        # Intent-wide rule
        intent_rule = self._intent_rules.get(intent)
        if intent_rule is not None:
            return intent_rule
        # Fall back to default
        return self.default_allow
