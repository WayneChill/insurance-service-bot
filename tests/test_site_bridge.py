import unittest

from site_bridge import (
    bearer_authorized,
    build_case_import_rows,
    mask_policy_number,
    mask_vehicle_number,
    validate_case_payload,
)


VALID = {
    "lineUserId": "U12345678901234567890",
    "caseId": "case-1",
    "idempotencyKey": "claim:case-1",
    "documentType": "claim",
    "customerDisplayName": "王小明",
    "insurers": ["全球人壽"],
    "createdAt": "2026-09-26T03:45:00.000Z",
    "status": "待聯絡",
}


class SiteBridgeTests(unittest.TestCase):
    def test_bearer_auth_requires_exact_secret(self):
        self.assertTrue(bearer_authorized("Bearer abc", "abc"))
        self.assertFalse(bearer_authorized("Bearer abc", "abd"))
        self.assertFalse(bearer_authorized("abc", "abc"))
        self.assertFalse(bearer_authorized("Bearer abc", ""))

    def test_valid_case_is_normalized(self):
        cleaned, error = validate_case_payload(dict(VALID))
        self.assertIsNone(error)
        self.assertEqual(cleaned["caseId"], "case-1")
        self.assertEqual(cleaned["insurers"], ["全球人壽"])

    def test_sensitive_fields_are_rejected(self):
        payload = dict(VALID, cardNumber="4111111111111111")
        cleaned, error = validate_case_payload(payload)
        self.assertIsNone(cleaned)
        self.assertEqual(error, "SENSITIVE_FIELD_REJECTED")

    def test_unknown_fields_are_rejected(self):
        payload = dict(VALID, tenantId="someone-else")
        cleaned, error = validate_case_payload(payload)
        self.assertIsNone(cleaned)
        self.assertEqual(error, "UNKNOWN_FIELD")

    def test_document_type_is_allowlisted(self):
        payload = dict(VALID, documentType="pdf")
        _, error = validate_case_payload(payload)
        self.assertEqual(error, "INVALID_DOCUMENT_TYPE")

    def test_masks_source_identifiers(self):
        self.assertEqual(mask_vehicle_number("ABC-1234"), "***-1234")
        self.assertEqual(mask_policy_number("AB123456789"), "AB******789")

    def test_case_import_rows_only_include_allowlisted_metadata(self):
        rows = build_case_import_rows([{
            "案件ID": "C001",
            "客戶姓名": "王小明",
            "服務項目": "信用卡授權書",
            "保單號碼": "SECRET-POLICY",
            "狀態": "已聯絡",
            "備註": "medical details",
            "建立時間": "2026/09/26 10:00",
            "保險公司": "全球人壽、遠雄人壽",
        }])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["documentType"], "cardAuth")
        self.assertEqual(rows[0]["insurers"], ["全球人壽", "遠雄人壽"])
        self.assertEqual(set(rows[0]), {
            "sourceKey", "documentType", "customerDisplayName",
            "insurers", "createdAt", "status",
        })
        self.assertNotIn("SECRET-POLICY", str(rows[0]))
        self.assertNotIn("medical details", str(rows[0]))


if __name__ == "__main__":
    unittest.main()
