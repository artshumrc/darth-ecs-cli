"""``darth-infra logs`` — tail CloudWatch logs from an ECS service."""

from __future__ import annotations

import subprocess

import click

from .helpers import console, require_config


@click.command()
@click.argument("service")
@click.option("--env", "env_name", required=True, help="Environment name.")
@click.option("-f", "--follow", is_flag=True, help="Follow (tail) the log stream.")
@click.option("--since", default="1h", help="How far back to start (e.g. 1h, 30m).")
def logs(service: str, env_name: str, follow: bool, since: str) -> None:
    """Tail CloudWatch logs from an ECS service container."""
    config, _ = require_config()

    svc = next((s for s in config.services if s.name == service), None)
    if svc is None:
        console.print(
            f"[red]Service '{service}' not found. "
            f"Available: {', '.join(s.name for s in config.services)}[/red]"
        )
        raise SystemExit(1)

    log_group = f"/ecs/{config.project_name}-{env_name}-{service}"
    console.print(f"[bold]Tailing logs from [cyan]{log_group}[/cyan]...[/bold]")

    cmd = [
        "aws",
        "logs",
        "tail",
        log_group,
        "--region",
        config.aws_region,
        "--since",
        since,
        "--format",
        "short",
    ]
    if follow:
        cmd.append("--follow")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass
