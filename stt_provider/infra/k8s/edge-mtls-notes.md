# Phase 3 Step 1: mTLS at the Edge

## Target

Use Envoy or an equivalent ingress layer to terminate public TLS and support optional mTLS for enterprise/private connectivity.

## Public TLS

Use:

- cert-manager
- Let's Encrypt for public certificates
- Automatic certificate renewal
- HTTPS-only ingress

## Internal service-to-service TLS

Use a private CA for internal certificates.

Approved options:

- Smallstep
- AWS Private CA
- HashiCorp Vault PKI

## mTLS policy

Default launch policy:

- Public API: TLS required
- Enterprise/private connectivity: mTLS required when contracted
- Internal service-to-service traffic: mTLS preferred
- PrivateLink-style connectivity: mTLS required

## Certificate requirements

- Public certificates must auto-renew.
- Internal certificates must have short lifetimes.
- Certificate rotation must not require application redeploys.
- Gateway logs must include certificate verification failures with trace IDs.

## Acceptance checks

- HTTP traffic redirects to HTTPS.
- Public TLS certificate renews through cert-manager.
- Enterprise mTLS clients can connect with valid client certificates.
- Invalid client certificates are rejected.
- Gateway-to-Triton traffic remains private inside the cluster or VPC.

This starts Phase 3 enterprise hardening by defining TLS termination, optional enterprise mTLS, private CA usage, and certificate rotation expectations. The guide marks mTLS at the edge as the first enterprise-hardening step.
