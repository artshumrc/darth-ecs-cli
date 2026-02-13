"""``darth-infra init`` — interactive project setup using Textual TUI."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command("init")
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for the CDK project. Defaults to ./<project-name>-infra.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Skip the TUI and use a config file instead.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to an existing darth-infra.toml (for non-interactive mode).",
)
def init_cmd(
    output_dir: Path | None,
    non_interactive: bool,
    config_path: Path | None,
) -> None:
    """Interactively scaffold a new darth-infra CDK project."""
    from ..config.loader import load_config
    from ..scaffold.generator import generate_project

    if non_interactive:
        if config_path is None:
            raise click.UsageError("--config is required when using --non-interactive")
        config = load_config(config_path)
        out = output_dir or Path.cwd() / f"{config.project_name}-infra"
        result = generate_project(config, out)
        console.print(f"[green]Project scaffolded at {result}[/green]")
        return

    # Interactive TUI
    from ..tui.app import DarthEcsInitApp

    app = DarthEcsInitApp()
    app.run()

    if app.result_config is None:
        console.print("[yellow]Setup cancelled.[/yellow]")
        return

    config = app.result_config
    out = output_dir or Path.cwd() / f"{config.project_name}-infra"
    result = generate_project(config, out)
    console.print(f"\n[green]✓ Project scaffolded at {result}[/green]")
    console.print(
        f"\n[dim]Next steps:[/dim]\n  cd {result.name}\n  darth-infra deploy --env prod\n"
    )
