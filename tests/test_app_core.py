import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DB_PASSWORD", "")

from app import (
    active_filter_params,
    build_video_filters,
    enrich_upload_jobs,
    mask_secret,
    normalize_per_page,
    pagination_from_total,
    update_upload_job,
    upload_job_to_form_data,
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

    def test_upload_job_form_data_prefers_upload_status_fallback(self):
        form_data = upload_job_to_form_data({"id": 7, "upload_status": "queued"})
        self.assertEqual(form_data["status"], "queued")

    def test_enrich_upload_jobs_prefers_upload_status_fallback(self):
        items = enrich_upload_jobs(
            [{"id": 7, "device_id": 1, "device_platform_id": 1, "account_id": 1, "workflow_id": 1, "upload_status": "success"}],
            {1: "Device"},
            {1: "Platform"},
            {1: "Account"},
            {1: "Workflow"},
        )
        self.assertEqual(items[0]["status"], "success")
        self.assertEqual(items[0]["upload_status"], "success")

    def test_update_upload_job_sends_status_alias(self):
        captured = {}

        def fake_upload_api_request(path, method="GET", json_body=None):
            captured["path"] = path
            captured["method"] = method
            captured["json_body"] = json_body
            return {"item": {"id": 7}}

        with patch("app.upload_api_request", side_effect=fake_upload_api_request):
            success, message, item = update_upload_job(
                7,
                {
                    "device_id": 1,
                    "device_platform_id": 1,
                    "account_id": 1,
                    "workflow_id": 1,
                    "code_product": "CODE-1",
                    "link_product": "",
                    "title": "title",
                    "description": "",
                    "tags": [],
                    "video_url": "",
                    "cover_url": "",
                    "local_video_path": "",
                    "metadata": {},
                    "status": "posted",
                },
            )

        self.assertTrue(success)
        self.assertIn("อัปเดต Upload Job", message)
        self.assertEqual(item["id"], 7)
        self.assertEqual(captured["path"], "/api/uploads/7")
        self.assertEqual(captured["method"], "PUT")
        self.assertEqual(captured["json_body"]["status"], "posted")
        self.assertEqual(captured["json_body"]["upload_status"], "posted")


if __name__ == "__main__":
    unittest.main()
