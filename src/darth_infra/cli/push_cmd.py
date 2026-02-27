"""``darth-infra push`` — tag and push Docker images to ECR."""

from __future__ import annotations

import click

from .helpers import require_config
from .image_ops import push_images


@click.command()
@click.option(
    "--env",
    "env_name",
    required=True,
    help="Target environment (used for image tagging).",
)
@click.option(
    "--service",
    "service_name",
    default=None,
    help="Push only a specific service. Pushes all if omitted.",
)
def push(env_name: str, service_name: str | None) -> None:
    """Tag and push Docker images to ECR."""
    config, _ = require_config()
    push_images(config, env_name, service_name)
