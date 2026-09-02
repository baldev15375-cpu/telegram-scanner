---
name: Python package installation
description: Environment-specific guidance for installing Python dependencies in this workspace.
---

Use a Python tools runtime that includes pip before installing Python packages; the minimal base runtime can be externally managed and omit pip.

**Why:** Direct installation into the minimal Nix-managed interpreter can fail with a missing-pip or externally-managed-environment error.

**How to apply:** Check available Python modules first, install a tools module when needed, then install dependencies through the managed package installer.