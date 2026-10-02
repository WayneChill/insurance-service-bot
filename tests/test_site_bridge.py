import unittest

from site_bridge import (
    bearer_authorized,
    build_case_import_rows,
    build_newcase_import_rows,
    build_payment_import_rows,
    collect_application_rows,
    mask_policy_number,
    mask_vehicle_number,
    validate_case_payload,
    validate_legacy_case_status_payload,
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

    def test_case_import_preserves_legacy_service_type(self):
        rows = build_case_import_rows([{
            "案件ID": "C002", "客戶姓名": "王小明", "服務項目": "契變",
            "狀態": "核對中", "建立時間": "2026/09/26 10:00", "保險公司": "",
        }])
        self.assertEqual(rows[0]["documentType"], "契變")

    def test_legacy_case_status_update_is_minimal_and_allowlisted(self):
        cleaned, error = validate_legacy_case_status_payload({
            "lineUserId": "U12345678901234567890",
            "sourceKey": "line-case:C001",
            "status": "已完成",
        })
        self.assertIsNone(error)
        self.assertEqual(cleaned["caseId"], "C001")

        _, error = validate_legacy_case_status_payload({
            "lineUserId": "U12345678901234567890",
            "sourceKey": "line-case:C001",
            "status": "自行輸入",
        })
        self.assertEqual(error, "INVALID_STATUS")

    def test_new_contract_and_payment_rows_preserve_stages_and_safe_details(self):
        new = build_newcase_import_rows([{"ID": "N003", "姓名": "測試", "階段": "照會中", "保險公司": "測試保險", "建立時間": "2026/10/03 09:30", "備註": "PRIVATE"}])[0]
        self.assertEqual(new["sourceKey"], "line-newcase:N003")
        self.assertEqual(new["documentType"], "newContract")
        self.assertEqual(new["status"], "照會中")
        self.assertEqual(new["createdAt"], "2026-10-03T09:30:00+08:00")
        pay = build_payment_import_rows([{"ID": "P001", "要保人": "測試", "公司": "測試保險", "保單號碼": "AB123456789", "保費": "12,000", "轉帳日": "1151002", "狀態": "已通知", "備註": "PRIVATE"}])[0]
        self.assertEqual(pay["details"]["premium"], "12,000")
        self.assertEqual(pay["details"]["paymentDate"], "1151002")
        self.assertNotIn("AB123456789", str(pay))
        self.assertFalse(pay["details"]["recordDateMissing"])
        self.assertEqual(pay["createdAt"], "2026-10-02T00:00:00+08:00")
        self.assertNotIn("PRIVATE", str([pay,new]))
        for source, status in [("line-newcase:N003", "發單中"), ("line-payment:P001", "已通知")]:
            result, error = validate_legacy_case_status_payload({"lineUserId": VALID["lineUserId"], "sourceKey": source, "status": status})
            self.assertIsNone(error)
            self.assertEqual(result["status"], status)
        _, error = validate_legacy_case_status_payload({"lineUserId": VALID["lineUserId"], "sourceKey": "line-newcase:N003", "status": "已通知"})
        self.assertEqual(error, "INVALID_STATUS")

    def test_collection_includes_completed_payments_to_reconcile_and_never_truncates_first_thousand(self):
        from unittest.mock import Mock
        db = Mock()
        db.get_all_cases.return_value = []
        db.get_newcase_list.return_value = [{"ID": f"N{i:03d}", "姓名": "Test", "階段": "核保中", "建立時間": "2026/10/03 10:00"} for i in range(1005)]
        db.get_payment_failures.return_value = [{"ID": "P001", "要保人": "Test", "狀態": "已完成"}]
        rows, skipped = collect_application_rows(db)
        self.assertEqual(len(rows), 1006)
        self.assertEqual(skipped, 0)
        db.get_payment_failures.assert_called_once_with(include_completed=True, strict=True)
        db.get_newcase_list.side_effect = RuntimeError("upstream failure")
        with self.assertRaises(RuntimeError):
            collect_application_rows(db)


if __name__ == "__main__":
    unittest.main()
