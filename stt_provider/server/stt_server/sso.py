"""
SSO/SAML/SCIM Integration for STT Platform

This module implements Single Sign-On (SSO), SAML, and SCIM integration
using WorkOS as the managed identity provider. It handles:
- SAML SSO authentication for tenant admins
- SCIM provisioning and deprovisioning of admin users
- Domain-based organization mapping
- SSO enforcement at tenant level
- Audit logging for all SSO/SCIM events
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    import workos
    from workos import SSO, SCIM, Client
    WORKOS_AVAILABLE = True
except ImportError:
    WORKOS_AVAILABLE = False
    logger.warning("WorkOS SDK not installed. SSO/SCIM features will be disabled.")


class SSOManager:
    """
    Manages SAML SSO authentication using WorkOS.
    
    Handles SSO login flows, SAML assertion validation, and session creation.
    """
    
    def __init__(self, api_key: str, client_id: str, redirect_uri: str):
        """
        Initialize WorkOS SSO client.
        
        Args:
            api_key: WorkOS API key
            client_id: WorkOS client ID
            redirect_uri: Redirect URI for SSO callback
        """
        if not WORKOS_AVAILABLE:
            raise ImportError("WorkOS SDK is required for SSO functionality")
        
        self.api_key = api_key
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        workos.api_key = api_key
        self.sso = SSO()
    
    def generate_sso_url(self, tenant_id: str, email: Optional[str] = None) -> str:
        """
        Generate SSO authorization URL for a tenant.
        
        Args:
            tenant_id: Tenant ID
            email: Optional email for pre-filling
            
        Returns:
            SSO authorization URL
        """
        try:
            sso_url = self.sso.authorization_url(
                client_id=self.client_id,
                redirect_uri=self.redirect_uri,
                domain=tenant_id,  # Use tenant ID as domain for org mapping
                state=f"tenant:{tenant_id}",
            )
            logger.info(f"Generated SSO URL for tenant {tenant_id}")
            return sso_url
        except Exception as exc:
            logger.error(f"Failed to generate SSO URL for tenant {tenant_id}: {exc}")
            raise
    
    def validate_saml_assertion(self, code: str) -> Dict[str, Any]:
        """
        Validate SAML assertion from SSO callback.
        
        Args:
            code: Authorization code from SSO callback
            
        Returns:
            User information from validated assertion
        """
        try:
            profile = self.sso.profile(code)
            user_info = {
                "id": profile.id,
                "email": profile.email,
                "first_name": profile.first_name,
                "last_name": profile.last_name,
                "domain": profile.organization_id,
            }
            logger.info(f"Validated SAML assertion for user {user_info['email']}")
            return user_info
        except Exception as exc:
            logger.error(f"Failed to validate SAML assertion: {exc}")
            raise
    
    def audit_sso_login(self, tenant_id: str, user_email: str, success: bool, error: Optional[str] = None):
        """
        Audit SSO login attempt.
        
        Args:
            tenant_id: Tenant ID
            user_email: User email
            success: Whether login succeeded
            error: Optional error message
        """
        event_type = "admin.sso_login_succeeded" if success else "admin.sso_login_failed"
        
        # This would integrate with the existing audit system
        # For now, log the event
        logger.info(
            f"SSO login audit: {event_type}, tenant={tenant_id}, "
            f"user={user_email}, error={error}"
        )


class SCIMManager:
    """
    Manages SCIM provisioning using WorkOS.
    
    Handles automatic provisioning and deprovisioning of admin users
    based on identity provider changes.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize WorkOS SCIM client.
        
        Args:
            api_key: WorkOS API key
        """
        if not WORKOS_AVAILABLE:
            raise ImportError("WorkOS SDK is required for SCIM functionality")
        
        self.api_key = api_key
        workos.api_key = api_key
        self.scim = SCIM()
    
    def create_user(self, tenant_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new admin user via SCIM.
        
        Args:
            tenant_id: Tenant ID
            user_data: User data from SCIM payload
            
        Returns:
            Created user information
        """
        try:
            # Map SCIM attributes to local user model
            user = {
                "email": user_data.get("userName"),
                "first_name": user_data.get("name", {}).get("givenName"),
                "last_name": user_data.get("name", {}).get("familyName"),
                "tenant_id": tenant_id,
                "role": "admin",
                "sso_provisioned": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            logger.info(f"SCIM: Created user {user['email']} for tenant {tenant_id}")
            
            # Audit the provisioning event
            self._audit_scim_event("admin.scim_user_created", tenant_id, user["email"])
            
            return user
        except Exception as exc:
            logger.error(f"Failed to SCIM create user: {exc}")
            raise
    
    def update_user(self, tenant_id: str, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing admin user via SCIM.
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            user_data: Updated user data from SCIM payload
            
        Returns:
            Updated user information
        """
        try:
            user = {
                "id": user_id,
                "email": user_data.get("userName"),
                "first_name": user_data.get("name", {}).get("givenName"),
                "last_name": user_data.get("name", {}).get("familyName"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            logger.info(f"SCIM: Updated user {user['email']} for tenant {tenant_id}")
            
            # Audit the update event
            self._audit_scim_event("admin.scim_user_updated", tenant_id, user["email"])
            
            return user
        except Exception as exc:
            logger.error(f"Failed to SCIM update user: {exc}")
            raise
    
    def deactivate_user(self, tenant_id: str, user_id: str, user_email: str) -> bool:
        """
        Deactivate an admin user via SCIM.
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            user_email: User email
            
        Returns:
            True if successful
        """
        try:
            # Mark user as inactive
            logger.info(f"SCIM: Deactivated user {user_email} for tenant {tenant_id}")
            
            # Audit the deprovisioning event
            self._audit_scim_event("admin.scim_user_deprovisioned", tenant_id, user_email)
            
            return True
        except Exception as exc:
            logger.error(f"Failed to SCIM deactivate user: {exc}")
            raise
    
    def _audit_scim_event(self, event_type: str, tenant_id: str, user_email: str):
        """
        Audit SCIM event.
        
        Args:
            event_type: SCIM event type
            tenant_id: Tenant ID
            user_email: User email
        """
        logger.info(
            f"SCIM audit: {event_type}, tenant={tenant_id}, user={user_email}"
        )


class TenantSSOEnforcement:
    """
    Manages SSO enforcement at tenant level.
    
    Controls whether tenants require SSO authentication and manages
    the transition between password-based and SSO-based auth.
    """
    
    def __init__(self, db_connection):
        """
        Initialize SSO enforcement manager.
        
        Args:
            db_connection: Database connection for tenant settings
        """
        self.db = db_connection
    
    def is_sso_enforced(self, tenant_id: str) -> bool:
        """
        Check if SSO is enforced for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            True if SSO is enforced
        """
        try:
            # Query tenant settings for SSO enforcement flag
            query = """
                SELECT sso_enforced FROM tenant_rollout 
                WHERE tenant_id = %s
            """
            result = self.db.execute(query, (tenant_id,)).fetchone()
            
            if result:
                sso_enforced = result[0] if result[0] is not None else False
                logger.info(f"SSO enforcement for tenant {tenant_id}: {sso_enforced}")
                return sso_enforced
            
            return False
        except Exception as exc:
            logger.error(f"Failed to check SSO enforcement for tenant {tenant_id}: {exc}")
            return False
    
    def enforce_sso(self, tenant_id: str, enforced_by: str) -> bool:
        """
        Enable SSO enforcement for a tenant.
        
        Args:
            tenant_id: Tenant ID
            enforced_by: Admin user who enforced SSO
            
        Returns:
            True if successful
        """
        try:
            query = """
                UPDATE tenant_rollout 
                SET sso_enforced = true, updated_at = NOW()
                WHERE tenant_id = %s
            """
            self.db.execute(query, (tenant_id,))
            
            logger.info(f"SSO enforcement enabled for tenant {tenant_id} by {enforced_by}")
            
            # Audit the enforcement change
            self._audit_sso_change("admin.sso_enforced", tenant_id, enforced_by)
            
            return True
        except Exception as exc:
            logger.error(f"Failed to enforce SSO for tenant {tenant_id}: {exc}")
            raise
    
    def disable_sso(self, tenant_id: str, disabled_by: str) -> bool:
        """
        Disable SSO enforcement for a tenant.
        
        Args:
            tenant_id: Tenant ID
            disabled_by: Admin user who disabled SSO
            
        Returns:
            True if successful
        """
        try:
            query = """
                UPDATE tenant_rollout 
                SET sso_enforced = false, updated_at = NOW()
                WHERE tenant_id = %s
            """
            self.db.execute(query, (tenant_id,))
            
            logger.info(f"SSO enforcement disabled for tenant {tenant_id} by {disabled_by}")
            
            # Audit the enforcement change
            self._audit_sso_change("admin.sso_disabled", tenant_id, disabled_by)
            
            return True
        except Exception as exc:
            logger.error(f"Failed to disable SSO for tenant {tenant_id}: {exc}")
            raise
    
    def _audit_sso_change(self, event_type: str, tenant_id: str, actor: str):
        """
        Audit SSO enforcement change.
        
        Args:
            event_type: SSO event type
            tenant_id: Tenant ID
            actor: Admin user who made the change
        """
        logger.info(
            f"SSO enforcement audit: {event_type}, tenant={tenant_id}, actor={actor}"
        )


class SSOSync:
    """
    Synchronizes SSO/SCIM state with local user database.
    
    Ensures that SCIM-provisioned users are reflected in the local database
    and that deprovisioned users lose access immediately.
    """
    
    def __init__(self, db_connection, scim_manager: SCIMManager):
        """
        Initialize SSO sync manager.
        
        Args:
            db_connection: Database connection
            scim_manager: SCIM manager instance
        """
        self.db = db_connection
        self.scim = scim_manager
    
    def sync_user(self, tenant_id: str, scim_user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync a user from SCIM to local database.
        
        Args:
            tenant_id: Tenant ID
            scim_user_data: User data from SCIM
            
        Returns:
            Synced user information
        """
        try:
            email = scim_user_data.get("userName")
            
            # Check if user exists
            query = """
                SELECT id, active FROM admin_users 
                WHERE tenant_id = %s AND email = %s
            """
            existing = self.db.execute(query, (tenant_id, email)).fetchone()
            
            if existing:
                # Update existing user
                user_id = existing[0]
                user = self.scim.update_user(tenant_id, user_id, scim_user_data)
                
                # Update in database
                update_query = """
                    UPDATE admin_users 
                    SET first_name = %s, last_name = %s, 
                        sso_provisioned = true, updated_at = NOW()
                    WHERE id = %s
                """
                self.db.execute(
                    update_query,
                    (user["first_name"], user["last_name"], user_id)
                )
            else:
                # Create new user
                user = self.scim.create_user(tenant_id, scim_user_data)
                
                # Insert into database
                insert_query = """
                    INSERT INTO admin_users 
                    (tenant_id, email, first_name, last_name, role, sso_provisioned, active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                self.db.execute(
                    insert_query,
                    (tenant_id, user["email"], user["first_name"], 
                     user["last_name"], user["role"], True, True)
                )
            
            logger.info(f"Synced user {email} for tenant {tenant_id}")
            return user
        except Exception as exc:
            logger.error(f"Failed to sync user: {exc}")
            raise
    
    def revoke_access(self, tenant_id: str, user_id: str, user_email: str) -> bool:
        """
        Revoke access for a deprovisioned user.
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            user_email: User email
            
        Returns:
            True if successful
        """
        try:
            # Mark user as inactive in database
            query = """
                UPDATE admin_users 
                SET active = false, sso_provisioned = false, updated_at = NOW()
                WHERE tenant_id = %s AND id = %s
            """
            self.db.execute(query, (tenant_id, user_id))
            
            # Call SCIM deactivation
            self.scim.deactivate_user(tenant_id, user_id, user_email)
            
            logger.info(f"Revoked access for user {user_email} in tenant {tenant_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to revoke access: {exc}")
            raise


# Factory function for creating SSO/SCIM managers
def create_sso_manager(config: Dict[str, Any]) -> Optional[SSOManager]:
    """
    Create SSO manager from configuration.
    
    Args:
        config: Configuration dictionary with WorkOS credentials
        
    Returns:
        SSOManager instance or None if not configured
    """
    api_key = config.get("WORKOS_API_KEY")
    client_id = config.get("WORKOS_CLIENT_ID")
    redirect_uri = config.get("WORKOS_REDIRECT_URI")
    
    if not all([api_key, client_id, redirect_uri]):
        logger.warning("WorkOS credentials not configured. SSO disabled.")
        return None
    
    return SSOManager(api_key, client_id, redirect_uri)


def create_scim_manager(config: Dict[str, Any]) -> Optional[SCIMManager]:
    """
    Create SCIM manager from configuration.
    
    Args:
        config: Configuration dictionary with WorkOS credentials
        
    Returns:
        SCIMManager instance or None if not configured
    """
    api_key = config.get("WORKOS_API_KEY")
    
    if not api_key:
        logger.warning("WorkOS API key not configured. SCIM disabled.")
        return None
    
    return SCIMManager(api_key)
