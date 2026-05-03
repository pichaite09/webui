import os
import unittest

os.environ.setdefault("DB_PASSWORD", "")

from app import (
    active_filter_params,
    build_video_filters,
    mask_secret,
    normalize_per_page,
    pagination_from_total,
    validate_payload,
)


class AppCoreTest(unittest.TestCase):
    def test_validation_requires_core_fields_and_video_source(self):
        errors = validate_payload(
            {
                "device_id": 0,
                "workflow_id": 0,
                "title": "",
                "status": "",
                "video_url": "",
                "local_video_path": "",
                "_metadata_error": None,
            }
        )
        self.assertTrue(any("device_id" in error for error in errors))
        self.assertTrue(any("workflow_id" in error for error in errors))
        self.assertIn("video_url or local_video_path is required", errors)

    def test_validation_accepts_local_video_path(self):
        errors = validate_payload(
            {
                "device_id": 1,
                "workflow_id": 2,
                "title": "clip",
                "status": "ready",
                "video_url": "",
                "local_video_path": "D:\\videos\\clip.mp4",
                "_metadata_error": None,
            }
        )
        self.assertEqual(errors, [])

    def test_pagination_and_page_size(self):
        self.assertEqual(normalize_per_page("25"), 25)
        self.assertEqual(normalize_per_page("999"), 50)
        page = pagination_from_total(101, 5, 25)
        self.assertEqual(page["current_page"], 5)
        self.assertEqual(page["page_start"], 101)
        self.assertEqual(page["page_end"], 101)

    def test_filter_params_and_sql_where(self):
        filters = {"q": "abc", "status": "ready", "device_id": 1, "workflow_id": 0}
        params = active_filter_params(filters, 100)
        self.assertEqual(params["q"], "abc")
        self.assertEqual(params["per_page"], 100)
        where_clause, values = build_video_filters(filters)
        self.assertIn("WHERE", where_clause)
        self.assertIn("lower(status)", where_clause)
        self.assertIn(1, values)

    def test_mask_secret(self):
        self.assertEqual(mask_secret("abcdef123456"), "ab...56")
        self.assertEqual(mask_secret("abc"), "******")
        self.assertEqual(mask_secret(""), "")


if __name__ == "__main__":
    unittest.main()
