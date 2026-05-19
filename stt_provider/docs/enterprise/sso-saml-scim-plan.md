# Phase 3 Step 2: SSO / SAML / SCIM for Tenant Admins

## Target

Enterprise tenant admins must be able to authenticate through their identity provider, and admin users must be provisioned and deprovisioned automatically.

## Provider decision

Use a managed identity integration provider instead of building SAML and SCIM directly.

Approved options:

- WorkOS
- Auth0
- Stytch

Default choice:

- WorkOS

## Required capabilities

- SAML SSO
- OIDC where available
- SCIM provisioning
- Domain-based organization mapping
- Org-level SSO enforcement
- Admin role assignment
- Automatic deprovisioning
- Audit events for login and provisioning changes

## Tenant policy

Enterprise tenants may enforce SSO at the organization level.

When SSO is enforced:

- Password login is disabled for tenant admins.
- Admin users must authenticate through the tenant identity provider.
- SCIM becomes the source of truth for admin user lifecycle.
- Deprovisioned users lose access immediately.

## Audit events

Record the following events in `audit_log`:

- `admin.sso_login_succeeded`
- `admin.sso_login_failed`
- `admin.scim_user_created`
- `admin.scim_user_updated`
- `admin.scim_user_deprovisioned`
- `admin.sso_enforced`
- `admin.sso_disabled`

## Acceptance checks

- Enterprise tenant can configure SAML SSO.
- Enterprise tenant can enforce SSO.
- SCIM can provision an admin user.
- SCIM can deprovision an admin user.
- Deprovisioned admins cannot access tenant settings.
- SSO and SCIM changes are written to the audit log.

This implements Phase 3, Step 2: use a managed provider for SSO, SAML, and SCIM rather than building it yourself, enforce SSO for enterprise tenants, and automatically provision/deprovision tenant admins.
