# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Features

Agentic ESG implements multiple layers of security:

### 🔒 Data Protection
- **No Personal Data Storage** - Only climate data and anonymous session IDs
- **LGPD/GDPR Compliant** - 24-hour TTL on session cookies
- **Environment Variables** - All secrets stored in `.env` (never committed)
- **MongoDB TLS** - Encrypted database connections

### 🛡️ API Security
- **Rate Limiting** - slowapi protecting all endpoints (10 requests/hour for analysis)
- **Input Validation** - Pydantic models validate all inputs
- **CORS Configuration** - Configurable allowed origins (no wildcard in production)
- **Request Size Limits** - CSV uploads capped at 500KB, max 5 rows per batch

### 🔐 Infrastructure Security
- **HTTPS Only** - All production traffic encrypted
- **Security Headers** - X-Content-Type-Options, X-Frame-Options, CSP
- **Error Handling** - No sensitive data leaked in error messages
- **Retry Logic** - Tenacity prevents DOS on external APIs

### 📊 Transparency & Auditability
- **EU AI Act Art. 13 Compliance** - Full transparency layer showing:
  - Risk score composition (weighted factors)
  - Agent reasoning chain (what each agent received/concluded)
  - Validation audit trail (confidence scores, flags)
- **Data Provenance** - NASA endpoint URLs and timestamps logged per analysis
- **Token Tracking** - LLM usage tracked per agent for cost transparency

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

### 📧 Contact
- **Email:** beatrizcostaleal1996@gmail.com
- **Subject:** [SECURITY] Agentic ESG Vulnerability Report

### 📝 What to Include
1. **Description** - Clear explanation of the vulnerability
2. **Impact** - Potential security impact (data leak, DOS, etc.)
3. **Reproduction Steps** - How to reproduce the issue
4. **Suggested Fix** - If you have one (optional)

### ⏱️ Response Time
- **Initial Response:** Within 48 hours
- **Status Update:** Within 7 days
- **Fix Timeline:** Depends on severity
  - Critical: 24-48 hours
  - High: 1 week
  - Medium: 2 weeks
  - Low: 1 month

### 🎁 Recognition
Security researchers who responsibly disclose vulnerabilities will be:
- Credited in the CHANGELOG (if desired)
- Listed in SECURITY.md acknowledgments
- Mentioned in release notes

## Security Best Practices for Users

### 🔑 API Keys
```bash
# Never commit .env files
echo ".env" >> .gitignore

# Use strong, unique API keys
ANTHROPIC_API_KEY=sk-ant-xxxxx  # Get from console.anthropic.com
MONGO_URL=mongodb+srv://...      # Use Railway or MongoDB Atlas

# Rotate keys regularly (every 90 days)
```

### 🌐 CORS Configuration
```bash
# Development (localhost only)
ALLOWED_ORIGINS=http://localhost:8001

# Production (explicit domains)
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# NEVER use wildcard in production
# ALLOWED_ORIGINS=*  ❌ INSECURE
```

### 🔒 MongoDB Security
```bash
# Use connection string with authentication
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/dbname

# Enable IP whitelist in MongoDB Atlas
# Enable TLS/SSL connections
# Use strong passwords (20+ characters)
```

### 📊 Rate Limiting
```python
# Adjust rate limits per environment
@router.post("/api/analyze")
@limiter.limit("10/hour")  # Production: strict
# @limiter.limit("100/hour")  # Development: relaxed
```

## Known Limitations

### 🔍 Current Scope
- **No User Authentication** - Session-based only (by design for demo)
- **Public API** - No API key requirement (can be added via middleware)
- **Single-Tenant** - No multi-tenancy isolation

### 🎯 Future Enhancements
- [ ] API key authentication middleware
- [ ] OAuth2/JWT for user accounts
- [ ] Audit logging to separate service
- [ ] Advanced rate limiting per user
- [ ] Webhook security (HMAC signatures)

## Compliance & Standards

### ✅ Implemented
- **LGPD (Brazilian GDPR)** - Anonymous sessions, 24h TTL
- **EU AI Act Article 13** - Transparency layer with reasoning chain
- **OWASP Top 10** - Input validation, error handling, secure headers

### 📋 Certifications
- No formal certifications yet (open-source project)
- Code follows industry best practices
- Regular dependency updates via Dependabot

## Security Scanning

### 🔍 Automated Checks
```bash
# Install security tools
pip install safety bandit

# Check for known vulnerabilities
safety check

# Static security analysis
bandit -r src/

# Dependency audit
pip-audit
```

### 🤖 CI/CD Integration
- GitHub Actions runs security scans on every push
- Dependabot monitors dependencies weekly
- Test suite includes security-focused tests

## Acknowledgments

### 🙏 Security Researchers
None yet - be the first to responsibly disclose a vulnerability!

### 🛠️ Security Tools
- [slowapi](https://github.com/laurentS/slowapi) - Rate limiting
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Input validation
- [tenacity](https://github.com/jd/tenacity) - Retry logic
- [safety](https://github.com/pyupio/safety) - Vulnerability scanning
- [bandit](https://github.com/PyCQA/bandit) - Security linting

---

**Last Updated:** 2026-06-03  
**Version:** 1.0.0  
**Maintainer:** Beatriz Costa Leal (beatrizcostaleal1996@gmail.com)