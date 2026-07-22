"""Local FastAPI backend for the LensTrace Studio desktop app.

The backend binds to 127.0.0.1 only, on an ephemeral port chosen by the
launcher, and authenticates every request with a per-session token. It is never
intended to be exposed on a network interface.
"""
