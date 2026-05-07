# Security Policies

- **Passwords & Secrets**: No hardcoded passwords, API keys, or tokens in source code under any circumstance.
- **SQL Injection**: All database queries must use parameterized statements or an ORM. String concatenation for SQL is strictly forbidden.
- **Logging**: Do not log sensitive user data (PII, passwords, payment info).
