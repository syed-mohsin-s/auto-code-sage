# Optimization & Performance Standards

- **Time Complexity**: Avoid nested loops (O(n^2) or worse) unless strictly necessary and operating on very small datasets. Use sets/dictionaries for O(1) lookups.
- **Database Access**: Avoid N+1 query patterns. Use `JOIN` or batch queries to fetch related data.
- **Connections**: Database connections must be explicitly closed or managed via context managers (`with` statement) or connection pools.
