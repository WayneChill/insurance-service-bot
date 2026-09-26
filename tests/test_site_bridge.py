import unittest

from site_bridge import (
    bearer_authorized,
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


if __name__ == "__main__":
    unittest.main()
