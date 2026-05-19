"""
mTLS (Mutual TLS) Configuration for STT Platform

This module implements mutual TLS authentication for service-to-service
communication within the STT Platform. It handles:
- TLS certificate generation and rotation
- Client certificate validation
- mTLS enforcement for internal services
- Certificate revocation checking
"""

import logging
import ssl
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("Cryptography library not installed. mTLS features will be disabled.")


class CertificateAuthority:
    """
    Manages the internal certificate authority for mTLS.
    
    Generates and signs certificates for internal services.
    """
    
    def __init__(self, ca_cert_path: str, ca_key_path: str, common_name: str = "STT Platform CA"):
        """
        Initialize certificate authority.
        
        Args:
            ca_cert_path: Path to CA certificate file
            ca_key_path: Path to CA private key file
            common_name: Common name for the CA
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError("Cryptography library is required for mTLS functionality")
        
        self.ca_cert_path = Path(ca_cert_path)
        self.ca_key_path = Path(ca_key_path)
        self.common_name = common_name
        
        # Load or create CA
        if self.ca_cert_path.exists() and self.ca_key_path.exists():
            self._load_ca()
        else:
            self._create_ca()
    
    def _create_ca(self):
        """Create a new certificate authority."""
        logger.info("Creating new certificate authority")
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "STT Platform"),
            x509.NameAttribute(NameOID.COMMON_NAME, self.common_name),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=3650)  # 10 years
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        # Save certificate and key
        self.ca_cert_path.parent.mkdir(parents=True, exist_ok=True)
        self.ca_key_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.ca_cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(self.ca_key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        self.ca_cert = cert
        self.ca_key = private_key
        
        logger.info(f"Certificate authority created: {self.ca_cert_path}")
    
    def _load_ca(self):
        """Load existing certificate authority."""
        logger.info("Loading existing certificate authority")
        
        with open(self.ca_cert_path, "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        
        with open(self.ca_key_path, "rb") as f:
            self.ca_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        
        logger.info(f"Certificate authority loaded: {self.ca_cert_path}")
    
    def generate_service_certificate(
        self,
        common_name: str,
        dns_names: List[str],
        validity_days: int = 365
    ) -> Tuple[bytes, bytes]:
        """
        Generate a service certificate signed by the CA.
        
        Args:
            common_name: Common name for the certificate
            dns_names: List of DNS names for the certificate
            validity_days: Certificate validity in days
            
        Returns:
            Tuple of (certificate, private_key) as PEM bytes
        """
        logger.info(f"Generating service certificate for {common_name}")
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Create certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "STT Platform"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # Build SAN extension
        san_names = [x509.DNSName(dns) for dns in dns_names]
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            self.ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=validity_days)
        ).add_extension(
            x509.SubjectAlternativeName(san_names),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=True,
        ).sign(self.ca_key, hashes.SHA256(), default_backend())
        
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        logger.info(f"Service certificate generated for {common_name}")
        return cert_pem, key_pem


class mTLSValidator:
    """
    Validates client certificates for mTLS authentication.
    
    Checks certificate validity, chain of trust, and revocation status.
    """
    
    def __init__(self, ca_cert_path: str, crl_path: Optional[str] = None):
        """
        Initialize mTLS validator.
        
        Args:
            ca_cert_path: Path to CA certificate
            crl_path: Optional path to certificate revocation list
        """
        self.ca_cert_path = Path(ca_cert_path)
        self.crl_path = Path(crl_path) if crl_path else None
        
        # Load CA certificate
        with open(self.ca_cert_path, "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        
        # Load CRL if available
        self.crl = None
        if self.crl_path and self.crl_path.exists():
            with open(self.crl_path, "rb") as f:
                self.crl = x509.load_pem_x509_crl(f.read(), default_backend())
        
        logger.info("mTLS validator initialized")
    
    def validate_certificate(self, cert_pem: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate a client certificate.
        
        Args:
            cert_pem: Certificate in PEM format
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
            
            # Check certificate validity period
            now = datetime.utcnow()
            if now < cert.not_valid_before:
                return False, "Certificate not yet valid"
            if now > cert.not_valid_after:
                return False, "Certificate expired"
            
            # Check certificate chain
            try:
                cert.verify_directly_issued_by(self.ca_cert)
            except Exception as exc:
                return False, f"Certificate not issued by trusted CA: {exc}"
            
            # Check CRL if available
            if self.crl:
                try:
                    self.crl.get_revoked_certificate(cert.serial_number)
                    return False, "Certificate revoked"
                except Exception:
                    # Not in CRL, which is good
                    pass
            
            # Extract common name for logging
            cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            logger.info(f"Certificate validated for {cn}")
            
            return True, None
        except Exception as exc:
            logger.error(f"Certificate validation failed: {exc}")
            return False, str(exc)
    
    def extract_common_name(self, cert_pem: bytes) -> Optional[str]:
        """
        Extract common name from certificate.
        
        Args:
            cert_pem: Certificate in PEM format
            
        Returns:
            Common name or None
        """
        try:
            cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
            cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            return cn
        except Exception as exc:
            logger.error(f"Failed to extract common name: {exc}")
            return None


class mTLSContext:
    """
    Creates SSL contexts for mTLS communication.
    
    Provides server and client SSL contexts with proper certificate
    validation and enforcement.
    """
    
    def __init__(
        self,
        cert_path: str,
        key_path: str,
        ca_cert_path: str,
        require_client_cert: bool = True
    ):
        """
        Initialize mTLS context.
        
        Args:
            cert_path: Path to server/client certificate
            key_path: Path to private key
            ca_cert_path: Path to CA certificate
            require_client_cert: Whether to require client certificates
        """
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.ca_cert_path = Path(ca_cert_path)
        self.require_client_cert = require_client_cert
        
        logger.info("mTLS context initialized")
    
    def create_server_context(self) -> ssl.SSLContext:
        """
        Create SSL context for server with mTLS.
        
        Returns:
            SSL context configured for server mTLS
        """
        context = ssl.create_server_context(ssl.PROTOCOL_TLS_SERVER)
        
        # Load server certificate and key
        context.load_cert_chain(
            str(self.cert_path),
            str(self.key_path)
        )
        
        # Load CA for client certificate validation
        context.load_verify_locations(str(self.ca_cert_path))
        
        # Require client certificate
        if self.require_client_cert:
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.verify_mode = ssl.CERT_OPTIONAL
        
        logger.info("Server mTLS context created")
        return context
    
    def create_client_context(self) -> ssl.SSLContext:
        """
        Create SSL context for client with mTLS.
        
        Returns:
            SSL context configured for client mTLS
        """
        context = ssl.create_client_context()
        
        # Load client certificate and key
        context.load_cert_chain(
            str(self.cert_path),
            str(self.key_path)
        )
        
        # Load CA for server certificate validation
        context.load_verify_locations(str(self.ca_cert_path))
        
        # Require server certificate validation
        context.verify_mode = ssl.CERT_REQUIRED
        
        logger.info("Client mTLS context created")
        return context


class ServiceCertificateManager:
    """
    Manages certificate lifecycle for services.
    
    Handles certificate generation, rotation, and distribution
    for all internal services.
    """
    
    def __init__(self, ca: CertificateAuthority, cert_dir: str):
        """
        Initialize service certificate manager.
        
        Args:
            ca: Certificate authority instance
            cert_dir: Directory to store service certificates
        """
        self.ca = ca
        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Service certificate manager initialized")
    
    def generate_gateway_certificate(self) -> Tuple[str, str]:
        """
        Generate certificate for STT Gateway.
        
        Returns:
            Tuple of (cert_path, key_path)
        """
        cert_name = "stt-gateway"
        dns_names = [
            "stt-gateway.stt.svc.cluster.local",
            "stt-gateway",
            "*.stt.example.com",  # Production domain
        ]
        
        cert_pem, key_pem = self.ca.generate_service_certificate(
            common_name=cert_name,
            dns_names=dns_names
        )
        
        cert_path = self.cert_dir / f"{cert_name}.crt"
        key_path = self.cert_dir / f"{cert_name}.key"
        
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)
        
        logger.info(f"Gateway certificate generated: {cert_path}")
        return str(cert_path), str(key_path)
    
    def generate_triton_certificate(self) -> Tuple[str, str]:
        """
        Generate certificate for Triton backend.
        
        Returns:
            Tuple of (cert_path, key_path)
        """
        cert_name = "triton-parakeet"
        dns_names = [
            "triton-parakeet.stt.svc.cluster.local",
            "triton-parakeet",
        ]
        
        cert_pem, key_pem = self.ca.generate_service_certificate(
            common_name=cert_name,
            dns_names=dns_names
        )
        
        cert_path = self.cert_dir / f"{cert_name}.crt"
        key_path = self.cert_dir / f"{cert_name}.key"
        
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)
        
        logger.info(f"Triton certificate generated: {cert_path}")
        return str(cert_path), str(key_path)
    
    def generate_postgres_certificate(self) -> Tuple[str, str]:
        """
        Generate certificate for PostgreSQL.
        
        Returns:
            Tuple of (cert_path, key_path)
        """
        cert_name = "postgres"
        dns_names = [
            "postgres.stt.svc.cluster.local",
            "postgres",
        ]
        
        cert_pem, key_pem = self.ca.generate_service_certificate(
            common_name=cert_name,
            dns_names=dns_names
        )
        
        cert_path = self.cert_dir / f"{cert_name}.crt"
        key_path = self.cert_dir / f"{cert_name}.key"
        
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)
        
        logger.info(f"PostgreSQL certificate generated: {cert_path}")
        return str(cert_path), str(key_path)


# Factory function for creating mTLS components
def create_ca(ca_dir: str = "/etc/stt/certs") -> CertificateAuthority:
    """
    Create or load certificate authority.
    
    Args:
        ca_dir: Directory to store CA certificates
        
    Returns:
        CertificateAuthority instance
    """
    ca_dir_path = Path(ca_dir)
    ca_dir_path.mkdir(parents=True, exist_ok=True)
    
    return CertificateAuthority(
        ca_cert_path=str(ca_dir_path / "ca.crt"),
        ca_key_path=str(ca_dir_path / "ca.key"),
        common_name="STT Platform CA"
    )


def create_mtls_validator(ca_cert_path: str) -> mTLSValidator:
    """
    Create mTLS validator.
    
    Args:
        ca_cert_path: Path to CA certificate
        
    Returns:
        mTLSValidator instance
    """
    return mTLSValidator(ca_cert_path=ca_cert_path)
