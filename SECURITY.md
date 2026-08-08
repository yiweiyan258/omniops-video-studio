# Security Boundary

This public repository contains only the OmniOps Video Studio desktop source.

Do not submit:

- API credentials, private keys or live `.env` files
- merchant identity, voice or authorization assets
- internal OmniOps control-plane scripts or knowledge-graph data
- generated media, paid model outputs or private QA reports
- platform account automation or social engagement controls

The application references credentials through the operating-system credential
store or process environment. Credentials must never be bundled into source or
installers.

