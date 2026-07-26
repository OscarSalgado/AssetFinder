# Security Policy & Hardening Guide - AssetFinder

## Overview
AssetFinder implements comprehensive security measures for production deployment covering OWASP Top 10 and industry best practices.

## Security Features Implemented

### 1. Input Validation & Sanitization
- **Query Parameter Validation**: Maximum length (1000 chars), SQL injection pattern detection
- **Asset ID Validation**: Alphanumeric and hyphen/underscore only, max 100 chars
- **Type Validation**: Whitelist of valid types (inmueble, vehiculo, mueble, otros)
- **Price Validation**: Non-negative float values only
- **Date Validation**: YYYY-MM-DD format enforcement
- **Pagination Safety**: Limit clamped to max 10,000, offset clamped to max 1,000,000

### 2. Security Headers
All responses include security headers:
```
X-Content-Type-Options: nosniff          # Prevent MIME sniffing
X-Frame-Options: DENY                    # Prevent clickjacking
X-XSS-Protection: 1; mode=block          # XSS protection
Strict-Transport-Security: max-age=31536000  # HSTS (1 year)
Content-Security-Policy: strict          # CSP with 'self' only
Referrer-Policy: strict-origin-when-cross-origin  # Referrer leakage prevention
Permissions-Policy: restrict all         # Feature policy
```

### 3. Rate Limiting
- **Per-IP Rate Limiting**: 100 requests per hour by default
- **Sliding Window Algorithm**: Accurate rate limiting without blocked windows
- **Independent Tracking**: Each IP/user tracked separately

### 4. Logging & Monitoring
- **Request Logging**: All requests logged with method, path, IP, timestamp
- **Security Event Logging**: SQL injection attempts, rate limit violations logged
- **Error Sanitization**: Generic error messages to prevent information disclosure
- **Sensitive Data Hashing**: Sensitive values hashed in logs (one-way)

### 5. Database Security
- **Parameterized Queries**: SQLite ORM prevents SQL injection
- **Connection Pooling**: Efficient resource management
- **Data Validation**: Input validation before database operations

### 6. Frontend Security
- **XSS Protection**: HTML escaping on all user inputs
- **Content Security Policy**: Prevents inline scripts, only allows same-origin resources
- **Directory Traversal Prevention**: Frontend server validates file paths
- **Cache Control**: HTML cached with no-store, static files cached with 1-year expiry

### 7. API Security
- **CORS Control**: Configurable per-origin
- **HTTP Methods**: GET/POST only, OPTIONS for preflight
- **Content Type Validation**: JSON parsing with type checks
- **Error Handling**: Safe error messages, no stack traces to clients

## Environment Configuration

### Development
```bash
# .env.development
FLASK_ENV=development
DEBUG=False
SECRET_KEY=dev-key-change-in-production
API_PORT=5000
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600
```

### Production
```bash
# .env.production
FLASK_ENV=production
DEBUG=False
SECRET_KEY=$(openssl rand -hex 32)  # Generate random key
API_PORT=5000
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=3600
LOG_LEVEL=WARNING
```

## Deployment Security Checklist

- [ ] Change Flask SECRET_KEY to random value (32+ bytes)
- [ ] Set DEBUG=False in production
- [ ] Enable HTTPS/TLS on web server (nginx/Apache)
- [ ] Configure HSTS headers (Strict-Transport-Security)
- [ ] Set up WAF (Web Application Firewall) if possible
- [ ] Enable logging and monitoring
- [ ] Regular dependency updates (pip audit, npm audit)
- [ ] Database backups (daily minimum)
- [ ] Access logs reviewed regularly
- [ ] Security patches applied within 24 hours
- [ ] CORS origin whitelist configured
- [ ] Database credentials in environment variables
- [ ] API rate limits adjusted for expected load
- [ ] Security headers tested (securityheaders.com)

## OWASP Top 10 Coverage

1. **Broken Access Control**: ✓ Validated endpoints, proper error responses
2. **Cryptographic Failures**: ✓ HTTPS/TLS enforcement, no sensitive data in logs
3. **Injection**: ✓ Input validation, SQL parameterized queries, safe string handling
4. **Insecure Design**: ✓ Security by default, rate limiting, input validation
5. **Security Misconfiguration**: ✓ Security headers, safe defaults, detailed guide
6. **Vulnerable Components**: ✓ Regular dependency updates, known CVE scanning
7. **Authentication Failures**: ✓ Rate limiting, secure headers, session management
8. **Software Integrity Failures**: ✓ Code reviewed, tests passing, dependencies pinned
9. **Logging Failures**: ✓ Comprehensive logging, security event tracking
10. **SSRF**: ✓ Internal requests only, no user-controlled URLs

## Testing Security

### Run Security Tests
```bash
cd backend
python -m pytest tests/test_security.py -v
```

### Security Test Coverage
- 43 security-focused tests
- Rate limiting validation
- Input validation edge cases
- SQL injection pattern detection
- Security headers verification
- Error sanitization testing
- CORS configuration testing

## Common Vulnerabilities & Mitigations

### SQL Injection
- **Mitigation**: SQLite parameterized queries, input validation
- **Test**: `test_validate_query_rejects_sql_injection`

### XSS (Cross-Site Scripting)
- **Mitigation**: HTML escaping on frontend, CSP headers
- **Test**: XSS tests in UI module

### CSRF (Cross-Site Request Forgery)
- **Mitigation**: SameSite cookies, CORS origin validation
- **Test**: CORS validation in security tests

### Rate Limiting / DoS
- **Mitigation**: Per-IP rate limiting (100/hour default)
- **Test**: `test_rate_limiter_blocks_requests_exceeding_limit`

### Information Disclosure
- **Mitigation**: Error sanitization, safe error messages
- **Test**: `test_sanitize_error_message`

### Directory Traversal
- **Mitigation**: Frontend server validates paths
- **Test**: Manual testing with `../` sequences

## Monitoring & Alerts

### Log Monitoring
```bash
# Watch for suspicious patterns
tail -f backend/assetfinder.log | grep -i "security\|warning\|error"

# SQL injection attempts
grep "Suspicious query" backend/assetfinder.log

# Rate limit violations
grep "Rate limit exceeded" backend/assetfinder.log
```

### Performance Monitoring
- Response times per endpoint
- Database query performance
- Rate limiter efficiency
- Memory usage

## Incident Response

### If Security Issue Found
1. Immediately create GitHub issue with SECURITY label
2. Document steps to reproduce
3. Don't publish details publicly until patched
4. Deploy patch and test thoroughly
5. Notify affected parties (if any)
6. Post-incident review

## Security Update Process

1. **Monitor**: Check vulnerabilities daily
   ```bash
   pip audit  # Python dependencies
   npm audit  # JavaScript dependencies
   ```

2. **Test**: Run full test suite after updates
   ```bash
   python -m pytest --cov=src  # Backend
   npm test                     # Frontend
   ```

3. **Deploy**: Update production with patches
4. **Verify**: Confirm security headers in production

## Dependencies & Vulnerabilities

### Current Dependencies
- flask==3.0.0 (Web framework)
- requests==2.31.0 (HTTP client)
- beautifulsoup4==4.12.2 (HTML parser)
- pytest==7.4.2 (Testing)

### Known Security Considerations
- BeautifulSoup4: Always keep updated for HTML parsing security
- Flask: Enable all security middleware in production
- Requests: Validate SSL certificates in all requests

## Additional Resources

- [OWASP Top 10](https://owasp.org/Top10/)
- [Flask Security](https://flask.palletsprojects.com/en/3.0.x/security/)
- [Security Headers Project](https://securityheaders.com/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [SANS Top 25](https://www.sans.org/top25-software-errors/)

## Version History

- **v1.0.0**: Initial security hardening
  - Rate limiting implementation
  - Comprehensive input validation
  - Security headers configuration
  - Error sanitization
  - Logging framework
