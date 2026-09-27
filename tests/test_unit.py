"""不访问网络的核心逻辑测试。"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from mcp_server import (
    filter_by_date,
    load_pushed_records,
    parse_notices,
    save_pushed_records,
)


class CoreLogicTests(unittest.TestCase):
    def test_parse_notices_resolves_relative_urls_and_deduplicates(self):
        html = """
        <ul>
          <li><h3><a href="../info/1.htm">通知一</a></h3><span>2026-09-27</span></li>
          <li><h3><a href="../info/1.htm">通知一</a></h3><span>2026-09-27</span></li>
          <li><h3><a href="/info/2.htm">通知二</a></h3><span>2026-09-26</span></li>
        </ul>
        """
        notices = parse_notices(html, "https://example.com/news/tzgg.htm")

        self.assertEqual(len(notices), 2)
        self.assertEqual(notices[0]["url"], "https://example.com/info/1.htm")

    def test_filter_by_date_excludes_future_dates(self):
        today = date.today()
        notices = [
            {"url": "today", "date": today.isoformat()},
            {"url": "yesterday", "date": (today - timedelta(days=1)).isoformat()},
            {"url": "future", "date": (today + timedelta(days=1)).isoformat()},
        ]

        result = filter_by_date(notices, 2)

        self.assertEqual([item["url"] for item in result], ["today", "yesterday"])

    def test_records_are_saved_atomically_and_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            record_file = str(Path(temp_dir) / "nested" / "records.json")
            records = {"https://example.com/1": "通知一"}

            save_pushed_records(records, record_file)

            self.assertEqual(load_pushed_records(record_file), records)
            self.assertFalse(Path(record_file + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
