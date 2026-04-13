# user-service

User domain microservice:
- access token verification (`PyJWT`)
- user profile management
- RBAC (roles and permissions)
- audit logging for security-sensitive user actions
- Redis rate-limiting on mutating endpoints
- privacy-safe HMAC client fingerprints for anti-abuse keys
