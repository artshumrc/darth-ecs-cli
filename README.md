# darth-infra

A CLI tool for deploying websites to AWS ECS with multi-environment support.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
# Interactive project setup
darth-infra init

# Deploy production
darth-infra deploy --env prod

# Deploy a feature environment
darth-infra deploy --env feature-xyz

# Build & push Docker images
darth-infra build
darth-infra push --env prod

# Operations
darth-infra logs django --env prod -f
darth-infra exec django --env prod
darth-infra status --env prod
darth-infra destroy --env dev
```

## How It Works

1. **`darth-infra init`** — Interactive Textual TUI that walks you through project setup:
   - Project name, region, VPC
   - ECS services (name, Dockerfile, port, domain)
   - Optional RDS PostgreSQL database
   - Optional S3 buckets (with optional CloudFront)
   - ALB mode (shared or dedicated)
   - Secrets management (auto-generated or from env vars)

2. The TUI scaffolds a **complete CDK Python project** that you own and can customize.

3. **`darth-infra deploy --env <name>`** deploys via CDK under the hood. Prod must be deployed first.

4. Adding a new environment is as simple as editing `darth-infra.toml`:
   ```toml
   [project]
   environments = ["prod", "dev", "feature-xyz"]
   ```
   Then: `darth-infra deploy --env feature-xyz`

5. Non-prod environments automatically:
   - Clone RDS from the latest prod snapshot
   - Create fresh S3 buckets with the same config
   - Generate new secrets
   - Get environment-prefixed domains (e.g., `dev-myapp.example.com`)

## Configuration

The `darth-infra.toml` file is the source of truth. Example:

```toml
[project]
name = "my-webapp"
aws_region = "us-east-1"
vpc_name = "artshumrc-prod-standard"
environments = ["prod", "dev"]

[[services]]
name = "django"
dockerfile = "Dockerfile"
port = 8000
domain = "myapp.example.com"
secrets = ["DJANGO_SECRET_KEY"]
s3_access = ["media"]

[rds]
database_name = "myapp"
instance_type = "t4g.micro"
expose_to = ["django"]

[[s3_buckets]]
name = "media"
cloudfront = true

[alb]
mode = "shared"

[[secrets]]
name = "DJANGO_SECRET_KEY"
source = "generate"
```

## Architecture

Each scaffolded project contains:

```
my-webapp-infra/
  darth-infra.toml        # Config (source of truth)
  app.py                  # CDK app entrypoint
  cdk.json                # CDK config (uses uv run)
  pyproject.toml           # CDK project dependencies
  stacks/
    main_stack.py          # Orchestrator: loops envs, creates constructs
    constructs/
      ecs_service.py       # Fargate service + ALB integration
      rds_database.py      # PostgreSQL RDS (optional)
      s3_bucket.py         # S3 buckets (optional)
      cloudfront_distribution.py  # CloudFront for S3 (optional)
      ecr_repository.py    # ECR repos (shared across envs)
      alb.py               # ALB shared lookup or dedicated
      secrets.py           # Secrets Manager integration
```

## Contributing

This project uses [changesets](https://github.com/changesets/changesets) for version management and releases.

When you make a change that should be released, add a changeset before opening your PR:

```bash
npx @changesets/cli init 
npx @changesets/cli
```

You'll be prompted to select a version bump type (major, minor, or patch) and write a summary of your change. Commit the generated changeset file alongside your code.

When changesets are merged to `main`, a "Version Release" PR is automatically opened. Merging that PR triggers a GitHub release with the built Python wheel attached.

### Installing from a GitHub Release

```bash
pip install https://github.com/artshumrc/darth-infra-cli/releases/download/v0.1.0/darth_infra-0.1.0-py3-none-any.whl
```
