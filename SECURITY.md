# Security Policy

## Reporting a vulnerability

Please report security issues privately rather than opening a public issue.
Use the repository's private vulnerability reporting (GitHub Security Advisories)
or contact a maintainer directly. We aim to acknowledge reports promptly and
will coordinate a fix and disclosure timeline with you.

## Security design of LensTrace Studio

The project is built around a few deliberate safeguards:

### Local backend isolation

- The desktop backend binds to `127.0.0.1` only — **never** `0.0.0.0` or a
  public interface.
- It listens on an ephemeral port chosen at launch, not a fixed well-known port.
- Every API request (except `/health`) must carry a per-session token in the
  `X-LensTrace-Token` header, compared in constant time. The token is generated
  by the launcher and passed to the backend and the Electron app via environment
  variables — it is never written to logs.

### File & path safety

- All caller-supplied filenames are sanitised (`core/validation.py`): directory
  separators, illegal characters, Windows reserved names, and traversal (`..`)
  are neutralised.
- Output paths are validated to stay within their intended directory.
- Original files are never modified; exports always go to a separate location.
- Metadata values are treated purely as data — never executed as commands.

### Privacy

- Desktop processing is entirely local; images are never uploaded to an external
  server.
- Bot temporary files live in isolated per-request workspaces and are deleted
  after the response is delivered.
- Address search (optional) sends only the typed query to OpenStreetMap
  Nominatim — never the image — and is rate-limited per Nominatim's policy.

### Secrets & logging

- Bot tokens and other secrets are read from environment variables / `.env`
  (git-ignored). `.env.example` contains no real values.
- A logging redaction filter scrubs token-shaped strings from log output.
- At normal log levels the app avoids logging image bytes, exact private paths,
  personal coordinates, or full user messages.

## Supported versions

This is a young project (0.x). Security fixes target the `main` branch.
