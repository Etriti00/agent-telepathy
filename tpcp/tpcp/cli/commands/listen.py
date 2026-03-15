import click


@click.command()
@click.option("--port", default=8765, help="Port to listen on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
def listen(port, host):
    """Start a TPCP node that prints all received messages."""
    import asyncio
    from tpcp.core.node import TPCPNode
    from tpcp.schemas.envelope import AgentIdentity, Intent, TPCPEnvelope
    from tpcp.security.crypto import AgentIdentityManager

    async def _listen():
        mgr = AgentIdentityManager()
        identity = AgentIdentity(
            framework="cli-listener",
            public_key=mgr.get_public_key_string(),
        )
        node = TPCPNode(identity=identity, host=host, port=port, identity_manager=mgr)

        def print_handler(env: TPCPEnvelope):
            click.echo(f"[{env.header.intent}] from {env.header.sender_id}: {env.payload}")

        for intent in Intent:
            node.register_handler(intent, print_handler)

        click.echo(f"Listening on {host}:{port} — press Ctrl+C to stop")
        try:
            await node.start_listening()
        finally:
            await node.stop_listening()

    try:
        asyncio.run(_listen())
    except KeyboardInterrupt:
        pass
