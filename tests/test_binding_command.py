import unittest

from app import _extract_binding_code


class BindingCommandTests(unittest.TestCase):
    def test_accepts_documented_and_common_variants(self):
        cases = {
            "綁定 123456": "123456",
            "綁定123456": "123456",
            "綁定：123456": "123456",
            "綁定: 123456": "123456",
            "綁定　１２３４５６": "123456",
            "１２３４５６": "123456",
            "123456": "123456",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(_extract_binding_code(message), expected)

    def test_rejects_non_binding_messages(self):
        for message in ("綁定", "綁定 12345", "綁定 1234567", "指令", "abc123"):
            with self.subTest(message=message):
                self.assertIsNone(_extract_binding_code(message))


if __name__ == "__main__":
    unittest.main()
