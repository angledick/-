"""Tests for compliance_rules — the deterministic compliance data & scoring layer."""

import pytest
from app.core.compliance_rules import (
    lookup_hs,
    lookup_vat,
    get_certifications,
    get_risk_flags,
    check_compliance,
)


class TestHSLookup:
    def test_exact_match_led(self):
        result = lookup_hs("LED灯具")
        assert result is not None
        assert result["code"] == "9405.40"
        assert "LED" in result["description_cn"]

    def test_partial_match(self):
        result = lookup_hs("灯具")
        assert result is not None
        assert result["category"] == "电子产品"

    def test_no_match(self):
        result = lookup_hs("星际战舰")
        assert result is None

    def test_smartphone_match(self):
        result = lookup_hs("智能手机")
        assert result is not None
        assert result["code"] == "8517.12"


class TestVATLookup:
    def test_germany_standard(self):
        assert lookup_vat("德国") == 19.0

    def test_france_standard(self):
        assert lookup_vat("法国") == 20.0

    def test_usa_no_federal_vat(self):
        assert lookup_vat("美国") == 0.0

    def test_unknown_country_default_zero(self):
        assert lookup_vat("火星") == 0.0


class TestCertifications:
    def test_germany_certs(self):
        certs = get_certifications("德国")
        assert "CE认证" in certs
        assert "WEEE注册(EAR)" in certs

    def test_uk_certs_different(self):
        certs = get_certifications("英国")
        assert "UKCA认证" in certs
        assert "CE认证" not in certs

    def test_unknown_country_default_eu(self):
        certs = get_certifications("未知国")
        assert len(certs) > 0


class TestRiskFlags:
    def test_high_risk_battery(self):
        flags = get_risk_flags("德国", "锂电池")
        assert any("锂电池" in f for f in flags)

    def test_eu_gpsr_flag(self):
        flags = get_risk_flags("法国", "LED灯")
        assert any("GPSR" in f for f in flags)

    def test_low_risk_normal_product(self):
        flags = get_risk_flags("新加坡", "棉制T恤")
        # Cotton T-shirt to Singapore — no special risk flags beyond maybe GPSR
        # Singapore is not in EU, so no GPSR flag
        assert all("GPSR" not in f for f in flags) or len(flags) <= 1


class TestCheckCompliance:
    def test_led_to_germany(self):
        result = check_compliance("LED灯", "德国")
        assert result["hs_code"] == "9405.40"
        assert result["vat_rate"] == 19.0
        assert result["risk_level"] in ("low", "medium", "high")
        assert len(result["certifications"]) > 0
        assert len(result["checklist"]) > 0

    def test_smartphone_to_usa(self):
        result = check_compliance("智能手机", "美国")
        assert result["hs_code"] == "8517.12"
        assert result["vat_rate"] == 0.0

    def test_unknown_product_graceful(self):
        result = check_compliance("不明物体", "德国")
        assert isinstance(result["hs_code"], str)
        assert result["hs_description"]  # falls back to description with warning

    def test_battery_logistics_and_documents(self):
        result = check_compliance("锂电池", "德国")
        assert result["hs_code"] == "8507.60"
        assert result["risk_score"] >= 40
        assert any("UN38.3" in item for item in result["logistics_flags"])
        assert "MSDS" in result["customs_documents"]
        assert result["remediation_steps"]

    def test_market_localization_notes(self):
        result = check_compliance("玩具", "法国")
        assert result["cultural_notes"]
        assert any("法语" in item or "儿童" in item for item in result["cultural_notes"])
