"""Shared Docker/ECR operations for build, push, and deploy flows."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import boto3

from ..config.models import ProjectConfig, ServiceConfig
from .helpers import console


def select_services(
    config: ProjectConfig,
    service_name: str | None,
) -> list[ServiceConfig]:
    """Return selected services or exit if the requested service is missing."""
    services = config.services
    if service_name:
        services = [service for service in services if service.name == service_name]
        if not services:
            console.print(
                f"[red]Service '{service_name}' not found. "
                f"Available: {', '.join(s.name for s in config.services)}[/red]"
            )
            raise SystemExit(1)
    return services


def select_internal_services(
    config: ProjectConfig,
    service_name: str | None,
) -> list[ServiceConfig]:
    """Return selected services that are built/pushed internally."""
    services = select_services(config, service_name)
    return [service for service in services if not service.image]


def build_images(
    config: ProjectConfig,
    project_dir: Path,
    service_name: str | None,
) -> None:
    """Build local Docker images for internal services."""
    ensure_docker_buildx()
    services = select_services(config, service_name)

    for service in services:
        if service.image:
            console.print(
                f"[dim]Skipping {service.name} — uses external image: {service.image}[/dim]"
            )
            continue

        tag = local_image_tag(config.project_name, service.name)
        console.print(f"[bold]Building {service.name}...[/bold]")

        cmd = [
            "docker",
            "buildx",
            "build",
            "--load",
            "-t",
            tag,
            "-f",
            service.dockerfile,
        ]
        if service.docker_build_target:
            cmd.extend(["--target", service.docker_build_target])
        cmd.append(service.build_context)
        console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
        result = subprocess.run(cmd, cwd=str(project_dir))
        if result.returncode != 0:
            console.print(
                f"[red]Build failed for {service.name} (exit {result.returncode})[/red]"
            )
            raise SystemExit(result.returncode)

        console.print(f"[green]✓ Built {tag}[/green]")


def push_images(
    config: ProjectConfig,
    env_name: str,
    service_name: str | None,
) -> None:
    """Tag and push local Docker images to ECR with latest + immutable tags."""
    services = select_services(config, service_name)
    account = boto3.client("sts").get_caller_identity()["Account"]
    registry = ecr_registry_uri(account, config.aws_region)

    console.print("[bold]Logging in to ECR...[/bold]")
    login_cmd = (
        f"aws ecr get-login-password --region {config.aws_region} "
        f"| docker login --username AWS --password-stdin {registry}"
    )
    result = subprocess.run(login_cmd, shell=True)
    if result.returncode != 0:
        console.print("[red]ECR login failed[/red]")
        raise SystemExit(1)

    immutable_tag = build_immutable_tag()
    for service in services:
        if service.image:
            console.print(
                f"[dim]Skipping {service.name} — uses external image: {service.image}[/dim]"
            )
            continue

        local_tag = local_image_tag(config.project_name, service.name)
        repo = ecr_repo_name(config.project_name, env_name, service.name)
        latest_remote_tag = f"{registry}/{repo}:latest"
        immutable_remote_tag = f"{registry}/{repo}:{immutable_tag}"

        console.print(
            f"[bold]Pushing {service.name} → {latest_remote_tag} ({immutable_tag})[/bold]"
        )

        subprocess.run(["docker", "tag", local_tag, immutable_remote_tag], check=True)
        result = subprocess.run(["docker", "push", immutable_remote_tag])
        if result.returncode != 0:
            console.print(
                f"[red]Push failed for {service.name} ({immutable_remote_tag})[/red]"
            )
            raise SystemExit(result.returncode)

        subprocess.run(
            ["docker", "tag", immutable_remote_tag, latest_remote_tag], check=True
        )
        result = subprocess.run(["docker", "push", latest_remote_tag])
        if result.returncode != 0:
            console.print(
                f"[red]Push failed for {service.name} ({latest_remote_tag})[/red]"
            )
            raise SystemExit(result.returncode)

        console.print(
            f"[green]✓ Pushed {latest_remote_tag} and {immutable_remote_tag}[/green]"
        )


def local_image_tag(project_name: str, service_name: str) -> str:
    return f"{project_name}-{service_name}:latest"


def ecr_registry_uri(account_id: str, region: str) -> str:
    return f"{account_id}.dkr.ecr.{region}.amazonaws.com"


def ecr_repo_name(project_name: str, env_name: str, service_name: str) -> str:
    return f"{project_name}/{env_name}/{service_name}"


def build_immutable_tag() -> str:
    return datetime.now(UTC).strftime("build-%Y%m%d%H%M%S")


def ensure_docker_buildx() -> None:
    """Exit with guidance when Docker buildx is not installed/available."""
    result = subprocess.run(
        ["docker", "buildx", "version"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return

    console.print("[red]Docker buildx is required for image builds.[/red]")
    console.print(
        "[yellow]Install/enable Docker buildx to use BuildKit:[/yellow] "
        "[blue]https://docs.docker.com/go/buildx/[/blue]"
    )
    raise SystemExit(1)
