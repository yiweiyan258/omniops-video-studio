# Public Repository Boundary

This repository is the public, platform-independent OmniOps Video Studio
desktop application only.

The private OmniOps control plane, Worker governance, knowledge graph, merchant
assets, model routing, runtime reports and deployment credentials are not part
of this repository.

The old public history that mixed internal OmniOps files with the desktop
application was replaced on 2026-08-08 after a local verified Git bundle was
created.

Allowed product runtime source includes `backend/`, `runtime/`, `tests/`, and
`tools/`. These directories may contain only portable application code,
descriptive manifests, local-only bridges, regression tests, and boundary
automation. They must not contain the private production workbench, model
credentials, merchant identity assets, knowledge graph data, generated media,
or external-platform write capabilities.
