import click


@click.command()
@click.argument("target_url")
@click.option("--timeout", default=5.0, help="Timeout in seconds")
def ping(target_url, timeout):
    """Send a HANDSHAKE to a TPCP node and wait for ACK."""
    import asyncio
    from tpcp.core.node import TPCPNode
    from tpcp.schemas.envelope import AgentIdentity, Intent, TextPayload
    from tpcp.security.crypto import AgentIdentityManager

    async def _ping():
        mgr = AgentIdentityManager()
        identity = AgentIdentity(
            framework="cli-ping",
            public_key=mgr.get_public_key_string(),
        )
        node = TPCPNode(identity=identity, identity_manager=mgr)
        click.echo(f"Pinging {target_url}...")
        try:
            await asyncio.wait_for(
                node.connect_to_peer(target_url),
                timeout=timeout,
            )
            click.echo("Connected.")
            peer_ids = list(node.peer_registry.keys())
            if peer_ids:
                await node.send_message(
                    target_id=peer_ids[0],
                    intent=Intent.HANDSHAKE,
                    payload=TextPayload(content="ping"),
                )
                click.echo("HANDSHAKE sent.")
        except asyncio.TimeoutError:
            click.echo("Timeout — no response", err=True)
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await node.stop_listening()

    asyncio.run(_ping())
