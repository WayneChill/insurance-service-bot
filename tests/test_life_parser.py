import io
import unittest

from openpyxl import Workbook

from excel_reader import parse_life_excel


def make_row(size=37):
    return [None] * size


class LifeParserTests(unittest.TestCase):
    def workbook(self):
        wb = Workbook()
        ws = wb.active
        for _ in range(7):
            ws.append([])

        main = make_row()
        main[0] = "POLICY0011150101"
        main[2] = "全球人壽"
        main[4] = "LIFE20"
        main[7] = "終身壽險"
        main[10] = "1150101"
        main[13] = 20
        main[15] = "年繳"
        main[16] = 100
        main[17] = 12000
        main[18] = "信用卡"
        main[19] = "測試客戶"
        main[21] = "測試客戶"
        main[23] = "A123456789"
        main[32] = "正常"
        ws.append(main)

        marker = make_row()
        marker[0] = "#rangeid=1"
        marker[2] = "對象"
        marker[11] = "附約"
        ws.append(marker)

        rider = make_row()
        rider[11] = "RIDER1"
        rider[14] = "醫療附約"
        rider[20] = 1
        rider[22] = 2
        rider[24] = 500000
        rider[25] = 3600
        ws.append(rider)

        excluded = make_row()
        excluded[0] = "TRAVEL0011150101"
        excluded[2] = "某人壽"
        excluded[7] = "個人旅行平安險"
        excluded[19] = "測試客戶"
        excluded[21] = "測試客戶"
        excluded[32] = "正常"
        ws.append(excluded)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def test_reads_terms_coverage_and_nested_riders(self):
        clients = parse_life_excel(self.workbook(), "測試客戶")
        self.assertEqual(len(clients), 1)
        policies = clients[0]["policies"]
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0]["term"], "20")
        self.assertEqual(policies[0]["coverage_amount"], "100")
        self.assertEqual(policies[0]["coverage_unit"], "萬")
        self.assertEqual(policies[0]["riders"][0]["code"], "RIDER1")
        self.assertEqual(policies[0]["riders"][0]["coverage_amount"], "500000")


if __name__ == "__main__":
    unittest.main()
