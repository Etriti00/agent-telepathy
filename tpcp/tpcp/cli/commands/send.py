import click


@click.command()
@click.argument("target_url")
@click.argument("intent")
@click.argument("message")
@click.option("--identity", type=click.Path(exists=True), default=None, help="JSON identity file from keygen")
def send(target_url, intent, message, identity):
    """Send a TPCP message to a node.

    TARGET_URL: WebSocket URL, e.g. ws://localhost:8765
    INTENT: e.g. TASK_REQUEST, STATE_SYNC
    MESSAGE: text content
    """
    import asyncio
    import json
    from tpcp.core.node import TPCPNode
    from tpcp.schemas.envelope import AgentIdentity, Intent as IntentEnum, TextPayload
    from tpcp.security.crypto import AgentIdentityManager

    async def _send():
        if identity:
            with open(identity) as f:
                data = json.load(f)
            mgr = AgentIdentityManager(
                private_key_bytes=__import__("base64").b64decode(data["private_key_b64"])
            )
            agent_identity = AgentIdentity(
                framework=data.get("framework", "cli-agent"),
                public_key=data["public_key"],
            )
        else:
            mgr = AgentIdentityManager()
            agent_identity = AgentIdentity(
                framework="cli-agent",
                public_key=mgr.get_public_key_string(),
            )

        node = TPCPNode(identity=agent_identity, identity_manager=mgr)
        try:
            intent_enum = IntentEnum(intent)
        except ValueError:
            click.echo(f"Unknown intent '{intent}'. Valid: {[i.value for i in IntentEnum]}", err=True)
            return

        try:
            await asyncio.wait_for(node.connect_to_peer(target_url), timeout=5.0)
            peer_ids = list(node.peer_registry.keys())
            if peer_ids:
                await node.send_message(peer_ids[0], intent_enum, TextPayload(content=message))
                click.echo(f"Sent {intent} to {target_url}")
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await node.stop_listening()

    asyncio.run(_send())
