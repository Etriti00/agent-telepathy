import click


@click.command()
@click.option("--framework", default="cli-agent", help="Framework label for the agent identity")
@click.option("--output", type=click.Path(), default=None, help="Save to JSON file")
def keygen(framework, output):
    """Generate a new Ed25519 identity keypair."""
    from tpcp.security.crypto import AgentIdentityManager
    from uuid import uuid4
    import json, base64

    mgr = AgentIdentityManager()
    agent_id = str(uuid4())
    pub_b64 = mgr.get_public_key_string()
    priv_b64 = base64.b64encode(mgr.get_private_key_bytes()).decode()
    identity = {
        "agent_id": agent_id,
        "framework": framework,
        "public_key": pub_b64,
        "private_key_b64": priv_b64,
    }
    if output:
        with open(output, "w") as f:
            json.dump(identity, f, indent=2)
        click.echo(f"Identity saved to {output}")
    else:
        click.echo(json.dumps(identity, indent=2))
