import click


@click.command()
@click.argument("envelope_json")
def inspect(envelope_json):
    """Parse and pretty-print a TPCP envelope JSON string."""
    from tpcp.schemas.envelope import TPCPEnvelope
    import json

    try:
        data = json.loads(envelope_json)
        env = TPCPEnvelope.model_validate(data)
        click.echo(f"Intent:    {env.header.intent}")
        click.echo(f"Sender:    {env.header.sender_id}")
        click.echo(f"Receiver:  {env.header.receiver_id}")
        click.echo(f"Msg ID:    {env.header.message_id}")
        click.echo(f"Protocol:  {env.header.protocol_version}")
        click.echo(f"Timestamp: {env.header.timestamp}")
        click.echo(f"Signed:    {'yes' if env.signature else 'no'}")
        click.echo(f"Payload:   {env.payload.model_dump_json(indent=2)}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
