import click
from tpcp.cli.commands.send import send
from tpcp.cli.commands.listen import listen
from tpcp.cli.commands.ping import ping
from tpcp.cli.commands.inspect import inspect
from tpcp.cli.commands.keygen import keygen

@click.group()
@click.version_option(version="0.4.0")
def cli():
    """TPCP — Telepathy Communication Protocol CLI"""

cli.add_command(send)
cli.add_command(listen)
cli.add_command(ping)
cli.add_command(inspect)
cli.add_command(keygen)

if __name__ == "__main__":
    cli()
