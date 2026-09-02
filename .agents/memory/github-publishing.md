---
name: GitHub publishing in the conversation sandbox
description: Use the connected GitHub proxy for repository operations from the conversation sandbox.
---

Use the GitHub connection through `listConnections('github')` inside a `"use impure"` function and call `proxyFetch`; the advertised `connectorFetch` helper may not be available in the conversation sandbox.

**Why:** The connection setup text can describe a callback that is not registered in the current sandbox, while the connector proxy remains available.

**How to apply:** Resolve the GitHub connection first, then use the proxy for authenticated repository reads and writes without exposing credentials.