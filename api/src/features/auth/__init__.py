"""Auth feature module (hexagonal).

Layers:
- domain/        — entities + value objects (no IO)
- application/   — use cases
- infrastructure/ — SQLAlchemy ORM, argon2id hasher, JWT service, email client
- presentation/  — FastAPI router + dependencies
"""