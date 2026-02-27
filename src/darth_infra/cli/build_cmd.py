"""``darth-infra build`` — build Docker images for all services."""

from __future__ import annotations

import click

from .helpers import require_config
from .image_ops import build_images


@click.command()
@click.option(
    "--service",
    "service_name",
    default=None,
    help="Build only a specific service. Builds all if omitted.",
)
def build(service_name: str | None) -> None:
    """Build Docker images for configured services."""
    config, project_dir = require_config()
    build_images(config, project_dir, service_name)
