#!/usr/bin/env bash
set -euo pipefail

# Read version from package.json (source of truth for changesets)
VERSION=$(node -p "require('./package.json').version")
echo "Publishing version $VERSION"

# Build the Python package
python -m build

# Create a local git tag and push it
git tag "v${VERSION}"
git push origin "v${VERSION}"

# Create a GitHub release with the wheel and sdist
gh release create "v${VERSION}" \
  --title "v${VERSION}" \
  --generate-notes \
  dist/*

echo "Published darth-infra v${VERSION}"
