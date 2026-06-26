"""
Tests for the Amazon SP-API Auth module (STS AssumeRole + AWS Signature V4).
"""

from unittest.mock import MagicMock, patch

import pytest

from forgeflow.providers.amazon.auth import (
    AmazonAuthManager,
    AWSSigV4Error,
    STSCredentials,
    _parse_sts_response,
    _sign_aws_request,
    _sp_api_region,
)

# ═══════════════════════════════════════════════════════════════════════════
# Region mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestSPAPIRegion:
    def test_na_maps_to_us_east_1(self):
        assert _sp_api_region("na") == "us-east-1"

    def test_eu_maps_to_eu_west_1(self):
        assert _sp_api_region("eu") == "eu-west-1"

    def test_fe_maps_to_us_west_2(self):
        assert _sp_api_region("fe") == "us-west-2"

    def test_unknown_falls_back_to_us_east_1(self):
        assert _sp_api_region("unknown") == "us-east-1"


# ═══════════════════════════════════════════════════════════════════════════
# AWS Signature V4 signing
# ═══════════════════════════════════════════════════════════════════════════


class TestAWSSigV4Signing:
    def test_produces_valid_authorization_header(self):
        """Should generate a properly formatted Authorization header."""
        amz_date, auth_header = _sign_aws_request(
            method="POST",
            host="sellingpartnerapi-na.amazon.com",
            path="/orders/v0/orders/113-1234567-1234567/refund",
            query_string="",
            region="us-east-1",
            service="execute-api",
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            body='{"amount":49.99}',
        )

        assert auth_header.startswith("AWS4-HMAC-SHA256")
        assert "Credential=AKIAIOSFODNN7EXAMPLE/" in auth_header
        assert "SignedHeaders=host;x-amz-date" in auth_header
        assert "Signature=" in auth_header
        assert amz_date.endswith("Z")

    def test_includes_session_token_when_provided(self):
        """Should include x-amz-security-token when session token is given."""
        amz_date, auth_header = _sign_aws_request(
            method="GET",
            host="sts.amazonaws.com",
            path="/",
            query_string="Action=AssumeRole&RoleArn=arn%3Aaws%3Aiam%3A%3A123456789%3Arole%2FSPAPIRole",
            region="us-east-1",
            service="sts",
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            session_token="FQoGZXIvYXdzEJr...",
        )

        assert "AWS4-HMAC-SHA256" in auth_header

    def test_different_methods_produce_different_signatures(self):
        """GET and POST to the same path should produce different signatures."""
        _, auth_get = _sign_aws_request(
            method="GET",
            host="sellingpartnerapi-na.amazon.com",
            path="/orders/v0/orders/113-1234567-1234567",
            query_string="",
            region="us-east-1",
            service="execute-api",
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            body="",
        )

        _, auth_post = _sign_aws_request(
            method="POST",
            host="sellingpartnerapi-na.amazon.com",
            path="/orders/v0/orders/113-1234567-1234567",
            query_string="",
            region="us-east-1",
            service="execute-api",
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            body="",
        )

        assert auth_get != auth_post


# ═══════════════════════════════════════════════════════════════════════════
# STS response parsing
# ═══════════════════════════════════════════════════════════════════════════


class TestParseSTSResponse:
    def test_parses_valid_sts_response(self):
        """Should extract all credential fields from a valid STS XML response."""
        xml = """<AssumeRoleResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
  <AssumeRoleResult>
    <Credentials>
      <AccessKeyId>ASIAIOSFODNN7EXAMPLE</AccessKeyId>
      <SecretAccessKey>wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY</SecretAccessKey>
      <SessionToken>FQoGZXIvYXdzEJr...EXAMPLE</SessionToken>
      <Expiration>2024-12-15T12:00:00Z</Expiration>
    </Credentials>
  </AssumeRoleResult>
</AssumeRoleResponse>"""

        result = _parse_sts_response(xml)

        assert result["AccessKeyId"] == "ASIAIOSFODNN7EXAMPLE"
        assert result["SecretAccessKey"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert result["SessionToken"] == "FQoGZXIvYXdzEJr...EXAMPLE"

    def test_raises_on_invalid_xml(self):
        """Should raise AWSSigV4Error for invalid XML."""
        with pytest.raises(AWSSigV4Error, match="Failed to parse"):
            _parse_sts_response("not XML at all")


# ═══════════════════════════════════════════════════════════════════════════
# AmazonAuthManager lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestAmazonAuthManager:
    def test_not_configured_without_role_arn(self):
        """is_configured should be False when role_arn is empty."""
        mgr = AmazonAuthManager(role_arn="")
        assert mgr.is_configured is False

    def test_configured_with_role_arn(self):
        """is_configured should be True when role_arn is set."""
        mgr = AmazonAuthManager(role_arn="arn:aws:iam::123456789:role/SPAPIRole")
        assert mgr.is_configured is True

    def test_default_session_name(self):
        """Should use ForgeFlowSPAPI as default session name."""
        mgr = AmazonAuthManager(role_arn="arn:aws:iam::123456789:role/SPAPIRole")
        assert mgr.role_session_name == "ForgeFlowSPAPI"

    def test_custom_session_name(self):
        """Should accept custom session name."""
        mgr = AmazonAuthManager(
            role_arn="arn:aws:iam::123456789:role/SPAPIRole",
            role_session_name="CustomSession",
        )
        assert mgr.role_session_name == "CustomSession"

    def test_clear_cache(self):
        """Should clear cached credentials."""
        from datetime import UTC, datetime, timedelta

        mgr = AmazonAuthManager(role_arn="arn:aws:iam::123456789:role/SPAPIRole")
        mgr._credentials = STSCredentials(
            access_key_id="test",
            secret_access_key="test",
            session_token="test",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        mgr.clear_cache()
        assert mgr._credentials is None

    @pytest.mark.asyncio
    async def test_assume_role_raises_without_iam_user_keys(self):
        """Should raise AWSSigV4Error when IAM user keys are not configured."""
        mgr = AmazonAuthManager(role_arn="arn:aws:iam::123456789:role/SPAPIRole")

        # Patch get_settings at its source (core.config) since it's imported
        # locally inside assume_role()
        with patch("forgeflow.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                amazon_iam_access_key="",
                amazon_iam_secret_key="",
            )
            with pytest.raises(AWSSigV4Error, match="IAM user credentials"):
                await mgr.assume_role()

    @pytest.mark.asyncio
    async def test_sign_sp_api_request_without_credentials_raises(self):
        """Should raise if sign_sp_api_request is called before assume_role."""
        mgr = AmazonAuthManager(role_arn="arn:aws:iam::123456789:role/SPAPIRole")

        with pytest.raises(AWSSigV4Error, match="No STS credentials"):
            mgr.sign_sp_api_request("POST", "/test", "{}")


# ═══════════════════════════════════════════════════════════════════════════
# STSCredentials
# ═══════════════════════════════════════════════════════════════════════════


class TestSTSCredentials:
    def test_not_expired_when_fresh(self):
        from datetime import UTC, datetime, timedelta

        creds = STSCredentials(
            access_key_id="test",
            secret_access_key="test",
            session_token="test",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert creds.is_expired is False

    def test_expired_when_past(self):
        from datetime import UTC, datetime, timedelta

        creds = STSCredentials(
            access_key_id="test",
            secret_access_key="test",
            session_token="test",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        assert creds.is_expired is True
