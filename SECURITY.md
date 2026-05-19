# Security Policy

## Reporting vulnerabilities

Do not open public issues for security problems. Report them privately to the repository owner with reproduction steps, affected files/endpoints, and impact.

## Secrets

- Use `.env.example` as a template.
- Never commit `.env`, API keys, JWT secrets, downloaded private model files, or generated user audio.
- Rotate `JWT_SECRET` and credentials before production deployment.

## Supported surface

Security fixes focus on the active backend, frontend, and `translator-mobile/` app. Archived and research directories are not production surfaces.
