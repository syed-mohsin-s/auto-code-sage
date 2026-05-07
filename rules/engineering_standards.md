# Company Plausible Engineering Standards

## Database Operations
- **Query Timeouts**: CRITICAL: All database queries must include a `timeout=5` parameter. Any database query (including SQLite, PostgreSQL, etc.) that does not explicitly pass `timeout=5` is considered a HIGH severity performance and reliability issue and must be flagged.

## Authentication
- **Custom Auth Wrappers**: Never use standard FastAPI dependency injection for auth; always use our custom `verify_sage_token` wrapper. Standard auth mechanisms are considered a security vulnerability in this project.
