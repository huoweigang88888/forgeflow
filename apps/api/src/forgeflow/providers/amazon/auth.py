"""
ForgeFlow AI - Amazon SP-API Auth Module (Phase 2).

Implements STS AssumeRole + AWS Signature V4 for SP-API write operations
(create_refund, track_shipment, and any other restricted SP-API endpoints).

Auth flow:
    1. LWA OAuth 2.0 client credentials → access token (Phase 1, in client.py)
    2. STS AssumeRole → temporary AWS credentials (this module)
    3. AWS Signature V4 signing → authorized SP-API write request (this module)

Reference:
    https://developer-docs.amazon.com/sp-api/docs/connecting-using-aws-signature-v4
    https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from forgeflow.core.exceptions import ProviderError


class AWSSigV4Error(ProviderError):
    """Error during AWS Signature V4 signing or STS AssumeRole."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__("amazon", message, retryable=retryable)


# ── STS endpoints by region ──
_STS_ENDPOINTS: dict[str, str] = {
    "na": "https://sts.amazonaws.com",
    "eu": "https://sts.eu-west-1.amazonaws.com",
    "fe": "https://sts.ap-southeast-1.amazonaws.com",
}

# SP-API service names for SigV4 (different from endpoint host)
# North America: "execute-api", Europe: "execute-api", Far East: "execute-api"
_SP_API_SERVICE_NAME = "execute-api"

# Regional STS endpoints for SigV4 signing
_SP_API_REGIONAL_HOSTS: dict[str, str] = {
    "na": "sellingpartnerapi-na.amazon.com",
    "eu": "sellingpartnerapi-eu.amazon.com",
    "fe": "sellingpartnerapi-fe.amazon.com",
}


class STSCredentials:
    """Temporary AWS credentials from STS AssumeRole."""

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        session_token: str,
        expires_at: datetime,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.expires_at = expires_at

    @property
    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if credentials are expired (with buffer)."""
        return datetime.now(UTC) >= (
            self.expires_at - __import__("datetime").timedelta(seconds=buffer_seconds)
        )


class AmazonAuthManager:
    """Manages STS AssumeRole and AWS Signature V4 signing for Amazon SP-API.

    Usage:
        auth = AmazonAuthManager(
            role_arn="arn:aws:iam::123456789:role/SPAPIRole",
            region="na",
        )
        creds = await auth.assume_role()
        headers = auth.sign_request(
            method="POST",
            path="/applications/v1/...",
            body=json_payload,
            credentials=creds,
        )
    """

    # STS session duration — max 1 hour
    _STS_SESSION_DURATION = 3600
    # Credential refresh buffer — refresh when < 5 minutes remaining
    _CREDENTIAL_REFRESH_BUFFER = 300

    def __init__(
        self,
        role_arn: str = "",
        role_session_name: str = "ForgeFlowSPAPI",
        region: str = "na",
    ):
        """Initialize the auth manager.

        Args:
            role_arn: AWS IAM role ARN for SP-API access.
            role_session_name: STS session name (for audit logs).
            region: SP-API region: na | eu | fe.
        """
        self.role_arn = role_arn
        self.role_session_name = role_session_name
        self.region = region

        self._sts_endpoint = _STS_ENDPOINTS.get(region, _STS_ENDPOINTS["na"])
        self._sp_api_host = _SP_API_REGIONAL_HOSTS.get(region, _SP_API_REGIONAL_HOSTS["na"])

        # Credential cache
        self._credentials: STSCredentials | None = None

    @property
    def is_configured(self) -> bool:
        """Check if IAM role is configured for Phase 2 operations."""
        return bool(self.role_arn)

    async def assume_role(self) -> STSCredentials:
        """Obtain temporary AWS credentials via STS AssumeRole.

        Uses the AWS STS AssumeRole API with an IAM role that has
        permission to call SP-API write endpoints.

        Credentials are cached and reused until near expiry.

        Returns:
            STSCredentials with access key, secret key, and session token.

        Raises:
            AWSSigV4Error: If the role ARN is not configured or STS call fails.
        """
        if not self.role_arn:
            raise AWSSigV4Error(
                "IAM role ARN not configured. Set AMAZON_ROLE_ARN in environment. "
                "Phase 2 write operations (refunds, tracking) require an IAM role "
                "with SP-API permissions.",
                retryable=False,
            )

        # Return cached credentials if still valid
        if self._credentials and not self._credentials.is_expired(self._CREDENTIAL_REFRESH_BUFFER):
            return self._credentials

        # Build STS AssumeRole request
        # STS uses AWS Signature V4 — but for AssumeRole we use the
        # long-lived IAM user credentials or the instance profile.
        # In production, use the IAM user keys configured in env.
        from forgeflow.core.config import get_settings

        settings = get_settings()

        if not settings.amazon_iam_access_key or not settings.amazon_iam_secret_key:
            raise AWSSigV4Error(
                "AWS IAM user credentials not configured. "
                "Set AMAZON_IAM_ACCESS_KEY_ID and AMAZON_IAM_SECRET_ACCESS_KEY.",
                retryable=False,
            )

        # Build the STS AssumeRole request
        params = {
            "Action": "AssumeRole",
            "RoleArn": self.role_arn,
            "RoleSessionName": self.role_session_name,
            "DurationSeconds": str(self._STS_SESSION_DURATION),
            "Version": "2011-06-15",
        }

        # Sign the STS request with AWS Signature V4 using the IAM user key
        sts_host = urlparse(self._sts_endpoint).netloc
        sts_url = self._sts_endpoint

        # Build query string
        query_parts = []
        for k in sorted(params.keys()):
            query_parts.append(f"{quote(k, safe='')}={quote(params[k], safe='')}")
        query_string = "&".join(query_parts)

        # Sign the request
        amz_date, auth_header = _sign_aws_request(
            method="GET",
            host=sts_host,
            path="/",
            query_string=query_string,
            region="us-east-1",  # STS is always us-east-1 for global endpoint
            service="sts",
            access_key=settings.amazon_iam_access_key,
            secret_key=settings.amazon_iam_secret_key,
            body="",
        )

        headers = {
            "Authorization": auth_header,
            "x-amz-date": amz_date,
            "Accept": "application/xml",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{sts_url}/?{query_string}",
                    headers=headers,
                )
                response.raise_for_status()
                creds_data = _parse_sts_response(response.text)

                self._credentials = STSCredentials(
                    access_key_id=creds_data["AccessKeyId"],
                    secret_access_key=creds_data["SecretAccessKey"],
                    session_token=creds_data["SessionToken"],
                    expires_at=creds_data["Expiration"],
                )
                return self._credentials

            except httpx.TimeoutException:
                raise AWSSigV4Error("STS AssumeRole timed out", retryable=True) from None
            except httpx.HTTPStatusError as e:
                raise AWSSigV4Error(
                    f"STS AssumeRole failed: HTTP {e.response.status_code} - "
                    f"{e.response.text[:500] if e.response else 'no response'}",
                    retryable=e.response.status_code >= 500 if e.response else False,
                ) from e

    def sign_sp_api_request(
        self,
        method: str,
        path: str,
        body: str = "",
        credentials: STSCredentials | None = None,
    ) -> dict[str, str]:
        """Sign an SP-API request with AWS Signature V4.

        Produces the Authorization header and x-amz-date header required
        for SP-API write endpoints.

        Args:
            method: HTTP method (POST, PUT, DELETE).
            path: Request path including query string (e.g., "/orders/v0/orders/123-456/...")
            body: JSON request body as string.
            credentials: STSCredentials from assume_role(). Uses cached if None.

        Returns:
            Dict with 'Authorization' and 'x-amz-date' headers.

        Raises:
            AWSSigV4Error: If no credentials are available.
        """
        if credentials is None:
            if self._credentials is None:
                raise AWSSigV4Error(
                    "No STS credentials. Call assume_role() first.",
                    retryable=False,
                )
            credentials = self._credentials

        amz_date, auth_header = _sign_aws_request(
            method=method,
            host=self._sp_api_host,
            path=path,
            query_string="",
            region=_sp_api_region(self.region),
            service=_SP_API_SERVICE_NAME,
            access_key=credentials.access_key_id,
            secret_key=credentials.secret_access_key,
            session_token=credentials.session_token,
            body=body,
        )

        headers = {
            "Authorization": auth_header,
            "x-amz-date": amz_date,
        }

        if credentials.session_token:
            headers["x-amz-security-token"] = credentials.session_token

        return headers

    def clear_cache(self) -> None:
        """Clear cached STS credentials."""
        self._credentials = None


# ── AWS Signature V4 implementation ──


def _sp_api_region(region: str) -> str:
    """Map SP-API region code to AWS region for SigV4."""
    mapping = {
        "na": "us-east-1",
        "eu": "eu-west-1",
        "fe": "us-west-2",
    }
    return mapping.get(region, "us-east-1")


def _sign_aws_request(
    method: str,
    host: str,
    path: str,
    query_string: str,
    region: str,
    service: str,
    access_key: str,
    secret_key: str,
    body: str = "",
    session_token: str | None = None,
) -> tuple[str, str]:
    """Sign a request with AWS Signature Version 4.

    Implements the full SigV4 signing process:
    1. Create a canonical request
    2. Create a string to sign
    3. Calculate the signature
    4. Build the Authorization header

    Args:
        method: HTTP method (uppercase).
        host: API hostname.
        path: Request path (URL-encoded).
        query_string: URL query string (raw, not encoded).
        region: AWS region.
        service: AWS service name (e.g., "execute-api", "sts").
        access_key: AWS access key ID.
        secret_key: AWS secret access key.
        body: Request body string.
        session_token: Optional STS session token.

    Returns:
        Tuple of (x-amz-date value, Authorization header value).
    """
    # Step 1: Build timestamp
    t = datetime.now(UTC)
    amz_date = t.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = t.strftime("%Y%m%d")

    # Step 2: Build canonical request
    canonical_uri = path if path else "/"
    canonical_querystring = query_string

    # Headers to sign (must be sorted, lowercase)
    headers_to_sign: dict[str, str] = {
        "host": host,
        "x-amz-date": amz_date,
    }
    if session_token:
        headers_to_sign["x-amz-security-token"] = session_token

    signed_headers = ";".join(sorted(headers_to_sign.keys()))
    canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items()))

    # Payload hash
    payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    # Step 3: Build string to sign
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"

    string_to_sign = "\n".join(
        [
            algorithm,
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    # Step 4: Calculate signature
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")

    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    # Step 5: Build Authorization header
    auth_header = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    return amz_date, auth_header


def _parse_sts_response(xml_text: str) -> dict[str, Any]:
    """Parse STS AssumeRole XML response.

    STS returns XML, not JSON. Extract the credential fields.

    Args:
        xml_text: Raw XML response from STS AssumeRole.

    Returns:
        Dict with AccessKeyId, SecretAccessKey, SessionToken, Expiration.

    Raises:
        AWSSigV4Error: If parsing fails.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_text)
        # STS response is wrapped in <AssumeRoleResponse>
        # Namespace handling
        ns = {"sts": "https://sts.amazonaws.com/doc/2011-06-15/"}
        # Try with namespace first, then without (for different STS endpoints)
        creds_elem = root.find(".//sts:Credentials", ns)
        if creds_elem is None:
            creds_elem = root.find(".//Credentials")
        if creds_elem is None:
            # Try AssumeRoleResult path
            result_elem = root.find(".//sts:AssumeRoleResult", ns)
            if result_elem is None:
                result_elem = root.find(".//AssumeRoleResult")
            if result_elem is not None:
                creds_elem = result_elem.find("sts:Credentials", ns)
                if creds_elem is None:
                    creds_elem = result_elem.find("Credentials")

        if creds_elem is None:
            raise AWSSigV4Error(
                f"Failed to parse STS response: {xml_text[:500]}",
                retryable=True,
            )

        def _find_text(elem: Any, tag: str) -> str:
            child = elem.find(tag)
            if child is None:
                # Try with namespace
                child = elem.find(f"{{https://sts.amazonaws.com/doc/2011-06-15/}}{tag}")
            return (child.text or "") if child is not None else ""

        expiration_str = _find_text(creds_elem, "Expiration")
        try:
            expiration = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            expiration = datetime.now(UTC) + __import__("datetime").timedelta(hours=1)

        return {
            "AccessKeyId": _find_text(creds_elem, "AccessKeyId"),
            "SecretAccessKey": _find_text(creds_elem, "SecretAccessKey"),
            "SessionToken": _find_text(creds_elem, "SessionToken"),
            "Expiration": expiration,
        }

    except ET.ParseError as e:
        raise AWSSigV4Error(
            f"Failed to parse STS XML response: {e}",
            retryable=True,
        ) from e


# ── SP-API Auth Helper ──


_ISO8601 = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now_str() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime(_ISO8601)
