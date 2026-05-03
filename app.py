import json
import os
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from db import get_db, init_db

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "video-manager-secret")

REFERENCE_API_BASE_URL = os.getenv("REFERENCE_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REFERENCE_API_KEY = os.getenv("REFERENCE_API_KEY", "").strip()
REFERENCE_TIMEOUT_SECONDS = 5
HEALTH_TIMEOUT_SECONDS = 2

UPLOAD_API_BASE_URL = os.getenv("UPLOAD_API_BASE_URL", REFERENCE_API_BASE_URL).rstrip("/")
UPLOAD_API_KEY = os.getenv("UPLOAD_API_KEY", REFERENCE_API_KEY).strip()
UPLOAD_TIMEOUT_SECONDS = 10
ITEMS_PER_PAGE = 50
PER_PAGE_OPTIONS = [25, 50, 100]


def parse_tags(raw_tags: str) -> list[str]:
    separators_normalized = raw_tags.replace("\n", ",")
    return [tag.strip() for tag in separators_normalized.split(",") if tag.strip()]


def parse_positive_int(raw_value: Any) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0


def parse_string(raw_value: Any) -> str:
    return str(raw_value or "").strip()


def optional_positive_int(raw_value: Any) -> int | None:
    value = parse_positive_int(raw_value)
    return value if value > 0 else None


def parse_metadata_json(raw_value: str) -> tuple[dict[str, Any], str | None]:
    cleaned = (raw_value or "").strip()
    if not cleaned:
        return {}, None

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}, "metadata ต้องเป็น JSON ที่ถูกต้อง"

    if not isinstance(parsed, dict):
        return {}, "metadata ต้องเป็น object JSON"

    return parsed, None


def json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def empty_form_data() -> dict[str, Any]:
    return {
        "device_id": 0,
        "device_platform_id": 0,
        "account_id": 0,
        "workflow_id": 0,
        "video_platform": "",
        "code_product": "",
        "link_product": "",
        "title": "",
        "description": "",
        "tags": "",
        "video_url": "",
        "cover_url": "",
        "local_video_path": "",
        "metadata_json": "{}",
        "status": "ready",
    }


def empty_upload_job_form_data() -> dict[str, Any]:
    return {
        "device_id": 0,
        "device_platform_id": 0,
        "account_id": 0,
        "workflow_id": 0,
        "code_product": "",
        "link_product": "",
        "title": "",
        "description": "",
        "tags": "",
        "video_url": "",
        "cover_url": "",
        "local_video_path": "",
        "metadata_json": "{}",
        "status": "draft",
    }


def form_to_payload(form: Any) -> dict[str, Any]:
    metadata_json = form.get("metadata_json", "{}").strip() or "{}"
    metadata, metadata_error = parse_metadata_json(metadata_json)

    return {
        "device_id": parse_positive_int(form.get("device_id", 0)),
        "device_platform_id": optional_positive_int(form.get("device_platform_id", 0)),
        "account_id": optional_positive_int(form.get("account_id", 0)),
        "workflow_id": parse_positive_int(form.get("workflow_id", 0)),
        "video_platform": form.get("video_platform", "").strip(),
        "code_product": form.get("code_product", "").strip(),
        "link_product": form.get("link_product", "").strip(),
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "tags": parse_tags(form.get("tags", "")),
        "video_url": form.get("video_url", "").strip(),
        "cover_url": form.get("cover_url", "").strip(),
        "local_video_path": form.get("local_video_path", "").strip(),
        "metadata": metadata,
        "metadata_json": metadata_json,
        "_metadata_error": metadata_error,
        "status": form.get("status", "ready").strip() or "ready",
    }


def upload_job_form_to_payload(form: Any) -> dict[str, Any]:
    metadata_json = form.get("metadata_json", "{}").strip() or "{}"
    metadata, metadata_error = parse_metadata_json(metadata_json)

    return {
        "device_id": parse_positive_int(form.get("device_id", 0)),
        "device_platform_id": optional_positive_int(form.get("device_platform_id", 0)),
        "account_id": optional_positive_int(form.get("account_id", 0)),
        "workflow_id": parse_positive_int(form.get("workflow_id", 0)),
        "code_product": form.get("code_product", "").strip(),
        "link_product": form.get("link_product", "").strip(),
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "tags": parse_tags(form.get("tags", "")),
        "video_url": form.get("video_url", "").strip(),
        "cover_url": form.get("cover_url", "").strip(),
        "local_video_path": form.get("local_video_path", "").strip(),
        "metadata": metadata,
        "metadata_json": metadata_json,
        "_metadata_error": metadata_error,
        "status": form.get("status", "draft").strip() or "draft",
    }


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_numbers = ["device_id", "workflow_id"]
    required_strings = ["title", "status"]

    for field in required_numbers:
        if payload[field] <= 0:
            errors.append(f"{field} ต้องมากกว่า 0")

    for field in required_strings:
        if not payload[field]:
            errors.append(f"{field} ห้ามว่าง")

    if payload.get("_metadata_error"):
        errors.append(payload["_metadata_error"])

    if not payload.get("video_url") and not payload.get("local_video_path"):
        errors.append("video_url or local_video_path is required")

    return errors


def validate_upload_job_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_numbers = ["device_id", "workflow_id"]
    required_strings = ["title", "status"]

    for field in required_numbers:
        if payload[field] <= 0:
            errors.append(f"{field} ต้องมากกว่า 0")

    for field in required_strings:
        if not payload[field]:
            errors.append(f"{field} ห้ามว่าง")

    if payload.get("_metadata_error"):
        errors.append(payload["_metadata_error"])

    if not payload.get("video_url") and not payload.get("local_video_path"):
        errors.append("video_url or local_video_path is required")

    return errors


VIDEO_SELECT_COLUMNS = """
    id,
    device_id,
    device_platform_id,
    account_id,
    workflow_id,
    video_platform,
    code_product,
    link_product,
    title,
    description,
    tags,
    video_url,
    cover_url,
    local_video_path,
    metadata,
    status,
    upload_job_id,
    upload_status,
    last_error,
    result,
    uploaded_at,
    created_at,
    updated_at
"""


def build_video_filters(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []

    search_query = parse_string(filters.get("q"))
    if search_query:
        clauses.append(
            """
            (
                title ILIKE %s
                OR code_product ILIKE %s
                OR video_platform ILIKE %s
                OR description ILIKE %s
                OR array_to_string(tags, ' ') ILIKE %s
            )
            """
        )
        pattern = f"%{search_query}%"
        values.extend([pattern, pattern, pattern, pattern, pattern])

    status = parse_string(filters.get("status"))
    if status and status != "all":
        clauses.append("lower(status) = lower(%s)")
        values.append(status)

    for field in ("device_id", "device_platform_id", "account_id", "workflow_id"):
        value = optional_positive_int(filters.get(field))
        if value:
            clauses.append(f"{field} = %s")
            values.append(value)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_clause, values


def list_videos(
    limit: int = ITEMS_PER_PAGE,
    offset: int = 0,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    where_clause, values = build_video_filters(filters or {})
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {VIDEO_SELECT_COLUMNS}
                FROM video_posts
                {where_clause}
                ORDER BY updated_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                [*values, max(1, limit), max(0, offset)],
            )
            return cursor.fetchall()


def count_videos(filters: dict[str, Any] | None = None) -> int:
    where_clause, values = build_video_filters(filters or {})
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)::int AS total
                FROM video_posts
                {where_clause}
                """,
                values,
            )
            row = cursor.fetchone() or {}
    return int(row.get("total") or 0)


def get_video(video_id: int) -> dict[str, Any] | None:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    device_id,
                    device_platform_id,
                    account_id,
                    workflow_id,
                    video_platform,
                    code_product,
                    link_product,
                    title,
                    description,
                    tags,
                    video_url,
                    cover_url,
                    local_video_path,
                    metadata,
                    status,
                    upload_job_id,
                    upload_status,
                    last_error,
                    result,
                    uploaded_at
                FROM video_posts
                WHERE id = %s
                """,
                (video_id,),
            )
            return cursor.fetchone()


def insert_video(payload: dict[str, Any]) -> int:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO video_posts (
                    device_id,
                    device_platform_id,
                    account_id,
                    workflow_id,
                    video_platform,
                    code_product,
                    link_product,
                    title,
                    description,
                    tags,
                    video_url,
                    cover_url,
                    local_video_path,
                    metadata,
                    status
                )
                VALUES (
                    %(device_id)s,
                    %(device_platform_id)s,
                    %(account_id)s,
                    %(workflow_id)s,
                    %(video_platform)s,
                    %(code_product)s,
                    %(link_product)s,
                    %(title)s,
                    %(description)s,
                    %(tags)s,
                    %(video_url)s,
                    %(cover_url)s,
                    %(local_video_path)s,
                    %(metadata_json)s::jsonb,
                    %(status)s
                )
                RETURNING id
                """,
                payload,
            )
            row = cursor.fetchone() or {}
        connection.commit()
        return int(row.get("id") or 0)


def update_video(video_id: int, payload: dict[str, Any]) -> bool:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE video_posts
                SET
                    device_id = %(device_id)s,
                    device_platform_id = %(device_platform_id)s,
                    account_id = %(account_id)s,
                    workflow_id = %(workflow_id)s,
                    video_platform = %(video_platform)s,
                    code_product = %(code_product)s,
                    link_product = %(link_product)s,
                    title = %(title)s,
                    description = %(description)s,
                    tags = %(tags)s,
                    video_url = %(video_url)s,
                    cover_url = %(cover_url)s,
                    local_video_path = %(local_video_path)s,
                    metadata = %(metadata_json)s::jsonb,
                    status = %(status)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                """,
                {**payload, "id": video_id},
            )
            updated = cursor.rowcount > 0
        connection.commit()
        return updated


def update_video_reference(video_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE video_posts
                SET
                    device_id = %(device_id)s,
                    device_platform_id = %(device_platform_id)s,
                    account_id = %(account_id)s,
                    workflow_id = %(workflow_id)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING
                    id,
                    device_id,
                    device_platform_id,
                    account_id,
                    workflow_id,
                    updated_at
                """,
                {**payload, "id": video_id},
            )
            row = cursor.fetchone()
        connection.commit()
        return row


def update_video_status(video_id: int, status: str) -> bool:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE video_posts
                SET
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, video_id),
            )
            updated = cursor.rowcount > 0
        connection.commit()
        return updated


def update_video_upload_state(
    video_id: int,
    *,
    upload_job_id: int | None,
    upload_status: str,
    last_error: str,
    result_payload: dict[str, Any],
) -> dict[str, Any] | None:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE video_posts
                SET
                    upload_job_id = %(upload_job_id)s,
                    upload_status = %(upload_status)s,
                    last_error = %(last_error)s,
                    result = %(result_json)s::jsonb,
                    uploaded_at = CASE
                        WHEN %(upload_job_id)s IS NOT NULL THEN NOW()
                        ELSE uploaded_at
                    END,
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING upload_job_id, upload_status, last_error, result, uploaded_at
                """,
                {
                    "id": video_id,
                    "upload_job_id": upload_job_id,
                    "upload_status": upload_status,
                    "last_error": last_error,
                    "result_json": json_text(result_payload),
                },
            )
            row = cursor.fetchone()
        connection.commit()
        return row


def delete_video(video_id: int) -> bool:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM video_posts WHERE id = %s", (video_id,))
            deleted = cursor.rowcount > 0
        connection.commit()
        return deleted


def record_video_event(
    video_id: int | None,
    event_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO video_post_events (video_id, event_type, message, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (video_id, event_type, message, json_text(payload or {})),
            )
        connection.commit()


def list_recent_video_events(video_ids: list[int], limit_per_video: int = 5) -> dict[int, list[dict[str, Any]]]:
    if not video_ids:
        return {}

    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, video_id, event_type, message, payload, created_at
                FROM (
                    SELECT
                        id,
                        video_id,
                        event_type,
                        message,
                        payload,
                        created_at,
                        ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY created_at DESC, id DESC) AS row_number
                    FROM video_post_events
                    WHERE video_id = ANY(%s)
                ) ranked_events
                WHERE row_number <= %s
                ORDER BY video_id, created_at DESC, id DESC
                """,
                (video_ids, max(1, limit_per_video)),
            )
            rows = cursor.fetchall()

    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(int(row["video_id"]), []).append(row)
    return grouped


def api_headers(api_key: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def request_api_json(
    *,
    base_url: str,
    api_key: str,
    path: str,
    method: str = "GET",
    json_body: dict[str, Any] | None = None,
    timeout_seconds: int = 5,
) -> dict[str, Any]:
    headers = api_headers(api_key)
    data = None

    if json_body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")

    request_obj = Request(f"{base_url}{path}", headers=headers, data=data, method=method)
    try:
        with urlopen(request_obj, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="ignore") if error.fp else str(error)
        raise RuntimeError(f"API returned HTTP {error.code}: {message}") from error
    except URLError as error:
        raise RuntimeError(f"API is unavailable: {error.reason}") from error

    if not payload.get("success", False):
        raise RuntimeError(payload.get("message", "API request failed"))

    return payload


def fetch_api_json(path: str) -> dict[str, Any]:
    try:
        return request_api_json(
            base_url=REFERENCE_API_BASE_URL,
            api_key=REFERENCE_API_KEY,
            path=path,
            timeout_seconds=REFERENCE_TIMEOUT_SECONDS,
        )
    except RuntimeError as error:
        raise RuntimeError(str(error).replace("API", "Reference API", 1)) from error


def upload_api_request(path: str, method: str = "GET", json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return request_api_json(
            base_url=UPLOAD_API_BASE_URL,
            api_key=UPLOAD_API_KEY,
            path=path,
            method=method,
            json_body=json_body,
            timeout_seconds=UPLOAD_TIMEOUT_SECONDS,
        )
    except RuntimeError as error:
        raise RuntimeError(str(error).replace("API", "Upload API", 1)) from error


def fetch_devices() -> list[dict[str, Any]]:
    return fetch_api_json("/api/devices").get("items", [])


def fetch_workflows() -> list[dict[str, Any]]:
    return fetch_api_json("/api/workflows").get("items", [])


def fetch_platforms(device_id: int) -> list[dict[str, Any]]:
    return fetch_api_json(f"/api/devices/{device_id}/platforms").get("items", [])


def fetch_accounts(platform_id: int) -> list[dict[str, Any]]:
    return fetch_api_json(f"/api/device-platforms/{platform_id}/accounts").get("items", [])


def default_upload_summary() -> dict[str, int]:
    return {
        "total_jobs": 0,
        "draft_count": 0,
        "running_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "template_count": 0,
    }


def default_database_summary() -> dict[str, int]:
    return {
        "total_videos": 0,
        "ready_count": 0,
        "draft_count": 0,
        "with_upload_job_count": 0,
        "without_upload_job_count": 0,
    }


def fetch_database_summary() -> dict[str, int]:
    with get_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*)::int AS total_videos,
                    COUNT(*) FILTER (WHERE lower(status) = 'ready')::int AS ready_count,
                    COUNT(*) FILTER (WHERE lower(status) = 'draft')::int AS draft_count,
                    COUNT(*) FILTER (WHERE upload_job_id IS NOT NULL)::int AS with_upload_job_count,
                    COUNT(*) FILTER (WHERE upload_job_id IS NULL)::int AS without_upload_job_count
                FROM video_posts
                """
            )
            row = cursor.fetchone() or {}
    return {**default_database_summary(), **row}


def compute_database_summary(videos: list[dict[str, Any]]) -> dict[str, int]:
    summary = default_database_summary()
    summary["total_videos"] = len(videos)
    summary["ready_count"] = sum(1 for video in videos if (video.get("status") or "").lower() == "ready")
    summary["draft_count"] = sum(1 for video in videos if (video.get("status") or "").lower() == "draft")
    summary["with_upload_job_count"] = sum(1 for video in videos if video.get("upload_job_id"))
    summary["without_upload_job_count"] = sum(1 for video in videos if not video.get("upload_job_id"))
    return summary


def normalize_page(raw_page: Any) -> int:
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def normalize_per_page(raw_per_page: Any) -> int:
    per_page = parse_positive_int(raw_per_page)
    return per_page if per_page in PER_PAGE_OPTIONS else ITEMS_PER_PAGE


def pagination_from_total(total_items: int, page: int, per_page: int = ITEMS_PER_PAGE) -> dict[str, Any]:
    total_pages = max((total_items + per_page - 1) // per_page, 1)
    current_page = min(max(page, 1), total_pages)
    start_index = (current_page - 1) * per_page
    end_index = start_index + per_page
    page_start = start_index + 1 if total_items else 0
    page_end = min(end_index, total_items)

    return {
        "current_page": current_page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "page_start": page_start,
        "page_end": page_end,
    }


def paginate_items(items: list[dict[str, Any]], page: int, per_page: int = ITEMS_PER_PAGE) -> dict[str, Any]:
    pagination = pagination_from_total(len(items), page, per_page)
    start_index = (pagination["current_page"] - 1) * per_page
    end_index = start_index + per_page
    return {**pagination, "items": items[start_index:end_index]}


def page_offset(page: int, per_page: int = ITEMS_PER_PAGE) -> int:
    return (max(page, 1) - 1) * max(1, per_page)


def filter_state_from_request() -> dict[str, Any]:
    return {
        "q": parse_string(request.args.get("q")),
        "status": parse_string(request.args.get("status")) or "all",
        "device_id": parse_positive_int(request.args.get("device_id")),
        "device_platform_id": parse_positive_int(request.args.get("device_platform_id")),
        "account_id": parse_positive_int(request.args.get("account_id")),
        "workflow_id": parse_positive_int(request.args.get("workflow_id")),
    }


def active_filter_params(filters: dict[str, Any], per_page: int) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key, value in filters.items():
        if value not in (None, "", 0, "all"):
            params[key] = value
    if per_page != ITEMS_PER_PAGE:
        params["per_page"] = per_page
    return params


def page_url_params(filters: dict[str, Any], per_page: int, page: int | None = None) -> dict[str, Any]:
    params = active_filter_params(filters, per_page)
    if page and page > 1:
        params["page"] = page
    return params


@app.context_processor
def template_helpers():
    def url_for_with_params(endpoint: str, base_params: dict[str, Any] | None = None, **values: Any) -> str:
        merged = dict(base_params or {})
        merged.update(values)
        return url_for(endpoint, **merged)

    return {"url_for_with_params": url_for_with_params}


def fetch_upload_summary() -> dict[str, Any]:
    item = upload_api_request("/api/uploads/summary").get("item", {})
    return {**default_upload_summary(), **item}


def fetch_upload_jobs(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    query_params = {
        key: value
        for key, value in (filters or {}).items()
        if value not in (None, "", 0)
    }
    path = "/api/uploads"
    if query_params:
        path = f"{path}?{urlencode(query_params)}"
    return upload_api_request(path).get("items", [])


def fetch_upload_jobs_page(
    limit: int,
    offset: int,
    filters: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query_params: dict[str, Any] = {"limit": limit, "offset": offset, "include_total": 1}
    for key in ("status", "device_id", "device_platform_id", "account_id", "workflow_id"):
        value = (filters or {}).get(key)
        if value not in (None, "", 0, "all"):
            query_params[key] = value
    response = upload_api_request(
        f"/api/uploads?{urlencode(query_params)}"
    )
    return response.get("items", []), response.get("page", {})


def fetch_upload_job_item(upload_job_id: int) -> dict[str, Any]:
    return upload_api_request(f"/api/uploads/{upload_job_id}").get("item", {})


def check_db_health() -> dict[str, Any]:
    try:
        with get_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 AS ok")
                cursor.fetchone()
        return {"ok": True, "label": "Database", "message": "เชื่อมต่อฐานข้อมูลได้"}
    except Exception as error:
        return {"ok": False, "label": "Database", "message": str(error)}


def check_api_health(label: str, base_url: str, api_key: str) -> dict[str, Any]:
    try:
        response = request_api_json(
            base_url=base_url,
            api_key=api_key,
            path="/api/health",
            timeout_seconds=HEALTH_TIMEOUT_SECONDS,
        )
        item = response.get("item", {})
        status = item.get("status", "ok")
        return {"ok": True, "label": label, "message": f"พร้อมใช้งาน ({status})"}
    except RuntimeError as error:
        return {"ok": False, "label": label, "message": str(error)}


def build_health_status() -> dict[str, Any]:
    services = [
        check_db_health(),
        check_api_health("Reference API", REFERENCE_API_BASE_URL, REFERENCE_API_KEY),
        check_api_health("Upload API", UPLOAD_API_BASE_URL, UPLOAD_API_KEY),
    ]
    ok_count = sum(1 for service in services if service["ok"])
    return {
        "ok": ok_count == len(services),
        "ok_count": ok_count,
        "total_count": len(services),
        "services": services,
    }


def mask_secret(value: str) -> str:
    cleaned = parse_string(value)
    if not cleaned:
        return ""
    if len(cleaned) <= 6:
        return "******"
    return f"{cleaned[:2]}...{cleaned[-2:]}"


def build_settings_context() -> dict[str, Any]:
    return {
        "database": {
            "host": os.getenv("DB_HOST", "192.168.1.211"),
            "port": os.getenv("DB_PORT", "5432"),
            "name": os.getenv("DB_NAME", "n8n"),
            "user": os.getenv("DB_USER", "n8n"),
            "password": mask_secret(os.getenv("DB_PASSWORD", "")),
        },
        "apis": {
            "reference_base_url": REFERENCE_API_BASE_URL,
            "reference_api_key": mask_secret(REFERENCE_API_KEY),
            "upload_base_url": UPLOAD_API_BASE_URL,
            "upload_api_key": mask_secret(UPLOAD_API_KEY),
        },
        "defaults": {
            "items_per_page": ITEMS_PER_PAGE,
            "per_page_options": PER_PAGE_OPTIONS,
        },
    }


def load_upload_job_overrides(videos: list[dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], dict[int, str]]:
    upload_items: dict[int, dict[str, Any]] = {}
    upload_errors: dict[int, str] = {}

    for video in videos:
        upload_job_id = video.get("upload_job_id")
        if not upload_job_id:
            continue

        try:
            upload_items[upload_job_id] = fetch_upload_job_item(upload_job_id)
        except RuntimeError as error:
            upload_errors[upload_job_id] = str(error)

    return upload_items, upload_errors


def merge_video_display_data(video: dict[str, Any], upload_item: dict[str, Any] | None) -> dict[str, Any]:
    if not upload_item:
        return {
            **video,
            "display_source": "database",
            "display_source_label": "Database",
        }

    merged = dict(video)
    for field in (
        "device_id",
        "device_platform_id",
        "account_id",
        "workflow_id",
        "code_product",
        "link_product",
        "title",
        "description",
        "tags",
        "video_url",
        "cover_url",
        "local_video_path",
        "metadata",
        "last_error",
        "result",
    ):
        if field in upload_item:
            merged[field] = upload_item[field]

    if "id" in upload_item:
        merged["upload_job_id"] = upload_item["id"]

    upload_status = upload_item.get("status") or upload_item.get("upload_status")
    if upload_status:
        merged["status"] = upload_status
        merged["upload_status"] = upload_status

    return {
        **merged,
        "display_source": "api",
        "display_source_label": "Upload API",
    }


def device_label(device: dict[str, Any]) -> str:
    serial = f" | {device['serial']}" if device.get("serial") else ""
    return f"{device.get('name', 'Device')} #{device.get('id')}{serial}"


def platform_label(platform: dict[str, Any]) -> str:
    package_name = f" | {platform['package_name']}" if platform.get("package_name") else ""
    return f"{platform.get('platform_name', platform.get('platform_key', 'Platform'))} #{platform.get('id')}{package_name}"


def account_label(account: dict[str, Any]) -> str:
    primary = account.get("display_name") or account.get("username") or account.get("login_id") or "Account"
    login_id = f" | {account['login_id']}" if account.get("login_id") else ""
    return f"{primary} #{account.get('id')}{login_id}"


def workflow_label(workflow: dict[str, Any]) -> str:
    suffix = " | active" if workflow.get("is_active") else " | inactive"
    return f"{workflow.get('name', 'Workflow')} #{workflow.get('id')}{suffix}"


def build_option(item_id: int, label: str, meta: str = "") -> dict[str, Any]:
    return {"id": item_id, "label": label, "meta": meta}


def ensure_selected_option(options: list[dict[str, Any]], selected_id: int, fallback_label: str) -> list[dict[str, Any]]:
    if selected_id and all(option["id"] != selected_id for option in options):
        return [build_option(selected_id, fallback_label, "Current saved value")] + options
    return options


def build_lookup(items: list[dict[str, Any]], label_key: str) -> dict[int, str]:
    return {item["id"]: item[label_key] for item in items}


def fallback_label(label: str, item_id: int | None) -> str:
    return f"{label} #{item_id}" if item_id else "-"


def format_display_datetime(value: Any) -> str:
    if not value:
        return "-"

    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M")

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return "-"
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return normalized
        return parsed.strftime("%d/%m/%Y %H:%M")

    return str(value)


def enrich_videos(
    videos: list[dict[str, Any]],
    device_lookup: dict[int, str],
    platform_lookup: dict[int, str],
    account_lookup: dict[int, str],
    workflow_lookup: dict[int, str],
    upload_job_items: dict[int, dict[str, Any]],
    upload_job_errors: dict[int, str],
    prefer_upload_api: bool = True,
) -> list[dict[str, Any]]:
    enriched = []
    event_lookup = list_recent_video_events([int(video["id"]) for video in videos if video.get("id")])
    for video in videos:
        if prefer_upload_api:
            video_display = merge_video_display_data(video, upload_job_items.get(video.get("upload_job_id")))
        else:
            video_display = {
                **video,
                "display_source": "database",
                "display_source_label": "Database",
            }
        enriched.append(
            {
                **video_display,
                "device_display": device_lookup.get(video_display["device_id"], fallback_label("Device", video_display.get("device_id"))),
                "platform_display": platform_lookup.get(
                    video_display["device_platform_id"], fallback_label("Platform", video_display.get("device_platform_id"))
                ),
                "account_display": account_lookup.get(
                    video_display["account_id"], fallback_label("Account", video_display.get("account_id"))
                ),
                "workflow_display": workflow_lookup.get(
                    video_display["workflow_id"], fallback_label("Workflow", video_display.get("workflow_id"))
                ),
                "video_platform_display": video_display.get("video_platform") or "-",
                "metadata_json_pretty": json.dumps(video_display.get("metadata") or {}, ensure_ascii=False, indent=2),
                "result_json_pretty": json.dumps(video_display.get("result") or {}, ensure_ascii=False, indent=2),
                "uploaded_at_display": format_display_datetime(video_display.get("uploaded_at")),
                "updated_at_display": format_display_datetime(video_display.get("updated_at")),
                "display_source_error": upload_job_errors.get(video.get("upload_job_id"), ""),
                "audit_events": [
                    {**event, "created_at_display": format_display_datetime(event.get("created_at"))}
                    for event in event_lookup.get(int(video["id"]), [])
                ],
            }
        )
    return enriched


def enrich_upload_jobs(
    upload_jobs: list[dict[str, Any]],
    device_lookup: dict[int, str],
    platform_lookup: dict[int, str],
    account_lookup: dict[int, str],
    workflow_lookup: dict[int, str],
) -> list[dict[str, Any]]:
    enriched = []
    for upload_job in upload_jobs:
        tags = upload_job.get("tags")
        if not isinstance(tags, list):
            tags = []

        metadata = upload_job.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        result = upload_job.get("result")
        if not isinstance(result, dict):
            result = {}

        upload_job_id = parse_positive_int(upload_job.get("id"))
        device_id = parse_positive_int(upload_job.get("device_id"))
        platform_id = parse_positive_int(upload_job.get("device_platform_id"))
        account_id = parse_positive_int(upload_job.get("account_id"))
        workflow_id = parse_positive_int(upload_job.get("workflow_id"))
        status = (upload_job.get("status") or upload_job.get("upload_status") or "draft").strip() or "draft"

        enriched.append(
            {
                **upload_job,
                "id": upload_job_id,
                "upload_job_id": upload_job_id,
                "device_id": device_id,
                "device_platform_id": platform_id,
                "account_id": account_id,
                "workflow_id": workflow_id,
                "status": status,
                "upload_status": status,
                "title": upload_job.get("title") or f"Upload Job #{upload_job_id}",
                "description": upload_job.get("description") or "",
                "tags": tags,
                "metadata": metadata,
                "result": result,
                "last_error": upload_job.get("last_error") or "",
                "code_product": upload_job.get("code_product") or "-",
                "link_product": upload_job.get("link_product") or "",
                "video_url": upload_job.get("video_url") or "",
                "cover_url": upload_job.get("cover_url") or "",
                "local_video_path": upload_job.get("local_video_path") or "",
                "device_display": device_lookup.get(device_id, f"Device #{device_id}" if device_id else "-"),
                "platform_display": platform_lookup.get(platform_id, f"Platform #{platform_id}" if platform_id else "-"),
                "account_display": account_lookup.get(account_id, f"Account #{account_id}" if account_id else "-"),
                "workflow_display": workflow_lookup.get(workflow_id, f"Workflow #{workflow_id}" if workflow_id else "-"),
                "video_platform_display": platform_lookup.get(platform_id, f"Platform #{platform_id}" if platform_id else "-"),
                "metadata_json_pretty": json.dumps(metadata, ensure_ascii=False, indent=2),
                "result_json_pretty": json.dumps(result, ensure_ascii=False, indent=2),
                "uploaded_at_display": format_display_datetime(upload_job.get("uploaded_at")),
                "updated_at_display": format_display_datetime(
                    upload_job.get("updated_at") or upload_job.get("created_at") or upload_job.get("uploaded_at")
                ),
                "display_source": "api",
                "display_source_label": "Upload API",
                "display_source_error": "",
            }
        )
    return enriched


def load_reference_bundle(
    videos: list[dict[str, Any]],
    form_data: dict[str, Any],
    *,
    prefer_upload_api: bool = True,
    include_upload_summary: bool = True,
) -> dict[str, Any]:
    device_options: list[dict[str, Any]] = []
    platform_options: list[dict[str, Any]] = []
    account_options: list[dict[str, Any]] = []
    workflow_options: list[dict[str, Any]] = []
    reference_error = ""
    upload_summary = default_upload_summary()
    upload_summary_error = ""
    upload_job_items: dict[int, dict[str, Any]] = {}
    upload_job_errors: dict[int, str] = {}

    try:
        devices = fetch_devices()
        workflows = fetch_workflows()

        device_ids = {video["device_id"] for video in videos if video.get("device_id")}
        if form_data.get("device_id"):
            device_ids.add(form_data["device_id"])

        platforms_by_device: dict[int, list[dict[str, Any]]] = {}
        all_platforms: list[dict[str, Any]] = []
        for device_id in sorted(device_ids):
            platforms = fetch_platforms(device_id)
            platforms_by_device[device_id] = platforms
            all_platforms.extend(platforms)

        platform_ids = {video["device_platform_id"] for video in videos if video.get("device_platform_id")}
        if form_data.get("device_platform_id"):
            platform_ids.add(form_data["device_platform_id"])

        accounts_by_platform: dict[int, list[dict[str, Any]]] = {}
        all_accounts: list[dict[str, Any]] = []
        for platform_id in sorted(platform_ids):
            accounts = fetch_accounts(platform_id)
            accounts_by_platform[platform_id] = accounts
            all_accounts.extend(accounts)

        device_options = [
            build_option(device["id"], device_label(device), device.get("last_status", ""))
            for device in devices
        ]
        workflow_options = [
            build_option(workflow["id"], workflow_label(workflow), workflow.get("description", ""))
            for workflow in workflows
        ]
        if not form_data.get("device_id") and device_options:
            form_data["device_id"] = device_options[0]["id"]
        if not form_data.get("workflow_id") and workflow_options:
            active_workflow = next(
                (workflow for workflow in workflows if workflow.get("is_active") and "upload" in (workflow.get("name") or "").lower()),
                None,
            ) or next(
                (workflow for workflow in workflows if workflow.get("is_active")),
                workflows[0] if workflows else None,
            )
            if active_workflow:
                form_data["workflow_id"] = active_workflow["id"]
        if form_data.get("device_id") and form_data["device_id"] not in platforms_by_device:
            platforms = fetch_platforms(form_data["device_id"])
            platforms_by_device[form_data["device_id"]] = platforms
            all_platforms.extend(platforms)
        platform_options = [
            build_option(platform["id"], platform_label(platform), platform.get("package_name", ""))
            for platform in platforms_by_device.get(form_data["device_id"], [])
        ]
        if not form_data.get("device_platform_id") and platform_options:
            form_data["device_platform_id"] = platform_options[0]["id"]
        if form_data.get("device_platform_id") and form_data["device_platform_id"] not in accounts_by_platform:
            accounts = fetch_accounts(form_data["device_platform_id"])
            accounts_by_platform[form_data["device_platform_id"]] = accounts
            all_accounts.extend(accounts)
        account_options = [
            build_option(
                account["id"],
                account_label(account),
                account.get("username", "") or account.get("login_id", ""),
            )
            for account in accounts_by_platform.get(form_data["device_platform_id"], [])
        ]
        if not form_data.get("account_id") and account_options:
            form_data["account_id"] = account_options[0]["id"]

        device_lookup = build_lookup(device_options, "label")
        platform_lookup = {platform["id"]: platform_label(platform) for platform in all_platforms}
        account_lookup = {account["id"]: account_label(account) for account in all_accounts}
        workflow_lookup = build_lookup(workflow_options, "label")
    except RuntimeError as error:
        reference_error = str(error)
        device_lookup = {}
        platform_lookup = {}
        account_lookup = {}
        workflow_lookup = {}

    if include_upload_summary:
        try:
            upload_summary = fetch_upload_summary()
        except RuntimeError as error:
            upload_summary_error = str(error)

    if prefer_upload_api and upload_summary_error:
        upload_job_errors = {
            video["upload_job_id"]: upload_summary_error
            for video in videos
            if video.get("upload_job_id")
        }
    elif prefer_upload_api:
        upload_job_items, upload_job_errors = load_upload_job_overrides(videos)

    device_options = ensure_selected_option(device_options, form_data["device_id"], f"Device #{form_data['device_id']}")
    platform_options = ensure_selected_option(
        platform_options,
        form_data["device_platform_id"],
        f"Platform #{form_data['device_platform_id']}",
    )
    account_options = ensure_selected_option(account_options, form_data["account_id"], f"Account #{form_data['account_id']}")
    workflow_options = ensure_selected_option(
        workflow_options,
        form_data["workflow_id"],
        f"Workflow #{form_data['workflow_id']}",
    )

    return {
        "videos": enrich_videos(
            videos,
            device_lookup,
            platform_lookup,
            account_lookup,
            workflow_lookup,
            upload_job_items,
            upload_job_errors,
            prefer_upload_api=prefer_upload_api,
        ),
        "device_options": device_options,
        "platform_options": platform_options,
        "account_options": account_options,
        "workflow_options": workflow_options,
        "device_lookup": device_lookup,
        "platform_lookup": platform_lookup,
        "account_lookup": account_lookup,
        "workflow_lookup": workflow_lookup,
        "reference_error": reference_error,
        "reference_api_base_url": REFERENCE_API_BASE_URL,
        "upload_api_base_url": UPLOAD_API_BASE_URL,
        "upload_summary": upload_summary,
        "upload_summary_error": upload_summary_error,
    }


def reference_response(items: list[dict[str, Any]]) -> Any:
    return jsonify({"success": True, "items": items})


def redirect_with_page(endpoint: str, page: int | None = None, **values: Any):
    normalized_page = normalize_page(page)
    if normalized_page > 1:
        values["page"] = normalized_page
    return redirect(url_for(endpoint, **values))


def redirect_back(endpoint: str, page: int | None = None, **values: Any):
    for key in ("q", "status", "device_id", "device_platform_id", "account_id", "workflow_id", "per_page"):
        value = request.args.get(key)
        if value not in (None, "", "0", "all"):
            values[key] = value
    return redirect_with_page(endpoint, page, **values)


def reference_payload_from_request() -> dict[str, Any]:
    source = request.get_json(silent=True) or request.form
    return {
        "device_id": parse_positive_int(source.get("device_id", 0)),
        "device_platform_id": optional_positive_int(source.get("device_platform_id", 0)),
        "account_id": optional_positive_int(source.get("account_id", 0)),
        "workflow_id": parse_positive_int(source.get("workflow_id", 0)),
    }


def validate_reference_payload(payload: dict[str, Any]) -> list[str]:
    errors = []
    for field in ("device_id", "workflow_id"):
        if payload[field] <= 0:
            errors.append(f"{field} ต้องมากกว่า 0")
    return errors


def build_upload_job_payload(video: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": video["device_id"],
        "device_platform_id": video["device_platform_id"],
        "account_id": video["account_id"],
        "workflow_id": video["workflow_id"],
        "code_product": video["code_product"],
        "link_product": video["link_product"],
        "title": video["title"],
        "description": video["description"],
        "tags": video["tags"] or [],
        "video_url": video["video_url"],
        "cover_url": video["cover_url"],
        "local_video_path": video["local_video_path"],
        "metadata": video.get("metadata") or {},
    }


def upload_job_to_form_data(upload_job: dict[str, Any]) -> dict[str, Any]:
    form_data = empty_upload_job_form_data()
    upload_status = (upload_job.get("status") or upload_job.get("upload_status") or "draft").strip() or "draft"
    form_data.update(
        {
            "device_id": parse_positive_int(upload_job.get("device_id")),
            "device_platform_id": parse_positive_int(upload_job.get("device_platform_id")),
            "account_id": parse_positive_int(upload_job.get("account_id")),
            "workflow_id": parse_positive_int(upload_job.get("workflow_id")),
            "code_product": upload_job.get("code_product") or "",
            "link_product": upload_job.get("link_product") or "",
            "title": upload_job.get("title") or "",
            "description": upload_job.get("description") or "",
            "tags": ", ".join(upload_job.get("tags") or []),
            "video_url": upload_job.get("video_url") or "",
            "cover_url": upload_job.get("cover_url") or "",
            "local_video_path": upload_job.get("local_video_path") or "",
            "metadata_json": json.dumps(upload_job.get("metadata") or {}, ensure_ascii=False, indent=2),
            "status": upload_status,
        }
    )
    return form_data


def update_upload_job(upload_job_id: int, payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        response = upload_api_request(
            f"/api/uploads/{upload_job_id}",
            method="PUT",
            json_body={
                "device_id": payload["device_id"],
                "device_platform_id": payload["device_platform_id"],
                "account_id": payload["account_id"],
                "workflow_id": payload["workflow_id"],
                "code_product": payload["code_product"],
                "link_product": payload["link_product"],
                "title": payload["title"],
                "description": payload["description"],
                "tags": payload["tags"],
                "video_url": payload["video_url"],
                "cover_url": payload["cover_url"],
                "local_video_path": payload["local_video_path"],
                "metadata": payload["metadata"],
                "status": payload["status"],
                "upload_status": payload["status"],
            },
        )
    except RuntimeError as error:
        return False, str(error), None

    item = response.get("item", {})
    return True, f"อัปเดต Upload Job เรียบร้อยแล้ว #{item.get('id', upload_job_id)}", item


def remove_upload_job(upload_job_id: int) -> tuple[bool, str]:
    try:
        upload_api_request(f"/api/uploads/{upload_job_id}", method="DELETE")
    except RuntimeError as error:
        return False, str(error)
    return True, f"ลบ Upload Job เรียบร้อยแล้ว #{upload_job_id}"


def run_upload_job_direct(upload_job_id: int) -> tuple[bool, str]:
    try:
        response = upload_api_request(
            f"/api/uploads/{upload_job_id}/run",
            method="POST",
            json_body={},
        )
    except RuntimeError as error:
        return False, str(error)

    item = response.get("item", {})
    return True, f"สั่งรัน Upload Job เรียบร้อยแล้ว #{item.get('id', upload_job_id)}"


def sync_video_to_upload_api(video_id: int) -> tuple[bool, str]:
    video = get_video(video_id)
    if not video:
        return False, "ไม่พบรายการที่ต้องการส่งข้อมูล"

    payload = build_upload_job_payload(video)
    try:
        if video.get("upload_job_id"):
            response = upload_api_request(
                f"/api/uploads/{video['upload_job_id']}",
                method="PUT",
                json_body=payload,
            )
        else:
            response = upload_api_request("/api/uploads", method="POST", json_body=payload)
    except RuntimeError as error:
        update_video_upload_state(
            video_id,
            upload_job_id=video.get("upload_job_id"),
            upload_status="sync_error",
            last_error=str(error),
            result_payload={},
        )
        return False, str(error)

    item = response.get("item", {})
    update_video_status(video_id, "draft")
    update_video_upload_state(
        video_id,
        upload_job_id=item.get("id") or video.get("upload_job_id"),
        upload_status=item.get("status", "draft"),
        last_error="",
        result_payload=item,
    )
    return True, f"ส่งข้อมูล Upload Job เรียบร้อยแล้ว #{item.get('id')}"


def queue_video_upload(video_id: int) -> tuple[bool, str]:
    synced, message = sync_video_to_upload_api(video_id)
    if not synced:
        return False, message

    return run_video_upload(video_id)


def run_video_upload(video_id: int) -> tuple[bool, str]:

    video = get_video(video_id)
    if not video or not video.get("upload_job_id"):
        return False, "ไม่พบ Upload Job สำหรับสั่งรัน"

    try:
        response = upload_api_request(
            f"/api/uploads/{video['upload_job_id']}/run",
            method="POST",
            json_body={},
        )
    except RuntimeError as error:
        update_video_upload_state(
            video_id,
            upload_job_id=video.get("upload_job_id"),
            upload_status="run_error",
            last_error=str(error),
            result_payload=video.get("result") or {},
        )
        return False, str(error)

    item = response.get("item", {})
    update_video_upload_state(
        video_id,
        upload_job_id=video["upload_job_id"],
        upload_status=item.get("status", "queued"),
        last_error="",
        result_payload=response,
    )
    return True, f"ส่งและเข้าคิว Upload Job #{video['upload_job_id']} เรียบร้อยแล้ว"


def serialize_upload_state(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None

    return {
        "upload_job_id": item.get("upload_job_id"),
        "upload_status": item.get("upload_status", "not_sent"),
        "last_error": item.get("last_error", ""),
        "result": item.get("result") or {},
        "result_pretty": json.dumps(item.get("result") or {}, ensure_ascii=False, indent=2),
        "uploaded_at_display": item["uploaded_at"].strftime("%d/%m/%Y %H:%M") if item.get("uploaded_at") else "-",
    }


def refresh_video_upload_status(video_id: int) -> tuple[bool, str, dict[str, Any] | None]:
    video = get_video(video_id)
    if not video:
        return False, "ไม่พบรายการที่ต้องการอัปเดตสถานะ", None

    upload_job_id = video.get("upload_job_id")
    if not upload_job_id:
        return False, "รายการนี้ยังไม่มี Upload Job", None

    try:
        response = upload_api_request(f"/api/uploads/{upload_job_id}")
    except RuntimeError as error:
        persisted = update_video_upload_state(
            video_id,
            upload_job_id=upload_job_id,
            upload_status=video.get("upload_status", "draft"),
            last_error=str(error),
            result_payload=video.get("result") or {},
        )
        return False, str(error), serialize_upload_state(persisted)

    item = response.get("item", {})
    persisted = update_video_upload_state(
        video_id,
        upload_job_id=item.get("id") or upload_job_id,
        upload_status=item.get("status", video.get("upload_status", "draft")),
        last_error=item.get("last_error", video.get("last_error", "")),
        result_payload=item["result"] if "result" in item else (video.get("result") or {}),
    )

    if not persisted:
        return False, "ไม่สามารถบันทึกสถานะล่าสุดได้", None

    return True, "อัปเดตสถานะ Upload Job ล่าสุดแล้ว", serialize_upload_state(persisted)


@app.route("/")
@app.route("/database")
def index():
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    per_page = normalize_per_page(request.args.get("per_page"))
    filters = filter_state_from_request()
    editing_id = request.args.get("edit", type=int)
    editing_video = get_video(editing_id) if editing_id else None

    form_data = empty_form_data()
    if editing_video:
        form_data.update(editing_video)
        form_data["tags"] = ", ".join(editing_video["tags"] or [])
        form_data["metadata_json"] = json.dumps(editing_video.get("metadata") or {}, ensure_ascii=False, indent=2)

    database_summary = fetch_database_summary()
    filtered_total = count_videos(filters)
    pagination = pagination_from_total(filtered_total, current_page, per_page)
    videos = list_videos(
        limit=pagination["per_page"],
        offset=page_offset(pagination["current_page"], pagination["per_page"]),
        filters=filters,
    )
    reference_bundle = load_reference_bundle(
        videos,
        form_data,
        prefer_upload_api=False,
        include_upload_summary=False,
    )

    return render_template(
        "index.html",
        page_mode="database",
        form_data=form_data,
        editing_video=editing_video,
        editing_upload=None,
        api_jobs_error="",
        database_summary=database_summary,
        filters=filters,
        per_page_options=PER_PAGE_OPTIONS,
        pagination_base_params=active_filter_params(filters, pagination["per_page"]),
        health_status=build_health_status(),
        **pagination,
        **reference_bundle,
    )


@app.get("/api")
def api_jobs_page():
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    per_page = normalize_per_page(request.args.get("per_page"))
    filters = filter_state_from_request()
    edit_upload_id = request.args.get("edit_upload", type=int)
    editing_upload = None
    form_data = empty_upload_job_form_data()
    editing_upload_error = ""

    if edit_upload_id:
        try:
            editing_upload = fetch_upload_job_item(edit_upload_id)
            form_data = upload_job_to_form_data(editing_upload)
        except RuntimeError as error:
            editing_upload_error = str(error)

    reference_bundle = load_reference_bundle([], form_data, prefer_upload_api=False)
    api_jobs_error = ""

    try:
        summary_total = parse_positive_int(reference_bundle["upload_summary"].get("total_jobs"))
        pagination = pagination_from_total(summary_total, current_page, per_page)
        upload_jobs, api_page = fetch_upload_jobs_page(
            pagination["per_page"],
            page_offset(pagination["current_page"], pagination["per_page"]),
            filters,
        )
        total_jobs = parse_positive_int(api_page.get("total"))
        if total_jobs and total_jobs != summary_total:
            pagination = pagination_from_total(total_jobs, current_page, per_page)
        elif not summary_total and upload_jobs:
            pagination = pagination_from_total(len(upload_jobs), current_page, per_page)
        all_videos = enrich_upload_jobs(
            upload_jobs,
            reference_bundle["device_lookup"],
            reference_bundle["platform_lookup"],
            reference_bundle["account_lookup"],
            reference_bundle["workflow_lookup"],
        )
        videos = all_videos
        if editing_upload:
            editing_upload = enrich_upload_jobs(
                [editing_upload],
                reference_bundle["device_lookup"],
                reference_bundle["platform_lookup"],
                reference_bundle["account_lookup"],
                reference_bundle["workflow_lookup"],
            )[0]
    except RuntimeError as error:
        api_jobs_error = str(error)
        videos = []
        pagination = paginate_items([], current_page)

    page_context = {**reference_bundle, "videos": videos}

    return render_template(
        "index.html",
        page_mode="api",
        form_data=form_data,
        editing_video=None,
        editing_upload=editing_upload,
        api_jobs_error=api_jobs_error or editing_upload_error,
        database_summary=default_database_summary(),
        filters=filters,
        per_page_options=PER_PAGE_OPTIONS,
        pagination_base_params=active_filter_params(filters, pagination["per_page"]),
        health_status=build_health_status(),
        **pagination,
        **page_context,
    )


@app.get("/reference/devices/<int:device_id>/platforms")
def reference_platforms(device_id: int):
    try:
        items = [
            build_option(platform["id"], platform_label(platform), platform.get("package_name", ""))
            for platform in fetch_platforms(device_id)
        ]
        return reference_response(items)
    except RuntimeError as error:
        return jsonify({"success": False, "message": str(error)}), 502


@app.get("/reference/device-platforms/<int:platform_id>/accounts")
def reference_accounts(platform_id: int):
    try:
        items = [
            build_option(
                account["id"],
                account_label(account),
                account.get("username", "") or account.get("login_id", ""),
            )
            for account in fetch_accounts(platform_id)
        ]
        return reference_response(items)
    except RuntimeError as error:
        return jsonify({"success": False, "message": str(error)}), 502


@app.post("/videos/<int:video_id>/reference")
def edit_video_reference(video_id: int):
    init_db()
    payload = reference_payload_from_request()
    errors = validate_reference_payload(payload)
    if errors:
        return jsonify({"success": False, "message": ", ".join(errors)}), 400

    updated = update_video_reference(video_id, payload)
    if not updated:
        return jsonify({"success": False, "message": "ไม่พบรายการที่ต้องการแก้ไข"}), 404

    return jsonify(
        {
            "success": True,
            "item": {
                "id": updated["id"],
                "device_id": updated["device_id"],
                "device_platform_id": updated["device_platform_id"],
                "account_id": updated["account_id"],
                "workflow_id": updated["workflow_id"],
                "updated_at_display": updated["updated_at"].strftime("%d/%m/%Y %H:%M"),
            },
            "message": "อัปเดตข้อมูลอ้างอิงเรียบร้อยแล้ว",
        }
    )


@app.post("/videos")
def create_video():
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    payload = form_to_payload(request.form)
    errors = validate_payload(payload)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect_back("index", current_page)

    video_id = insert_video(payload)
    record_video_event(video_id, "created", "สร้างรายการวิดีโอ", {"title": payload["title"]})
    flash("เพิ่มรายการวิดีโอเรียบร้อยแล้ว", "success")
    return redirect_back("index", current_page)


@app.post("/videos/<int:video_id>/update")
def edit_video(video_id: int):
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    payload = form_to_payload(request.form)
    errors = validate_payload(payload)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect_back("index", current_page, edit=video_id)

    if not update_video(video_id, payload):
        flash("ไม่พบรายการที่ต้องการแก้ไข", "error")
    else:
        record_video_event(video_id, "updated", "แก้ไขข้อมูลรายการ", {"title": payload["title"], "status": payload["status"]})
        flash("อัปเดตรายการเรียบร้อยแล้ว", "success")

    return redirect_back("index", current_page)


@app.post("/videos/<int:video_id>/send")
def send_video(video_id: int):
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    success, message = sync_video_to_upload_api(video_id)
    record_video_event(video_id, "send", message, {"success": success})
    flash(message, "success" if success else "error")
    return redirect_back("index", current_page)


@app.post("/videos/<int:video_id>/run")
def run_only_video(video_id: int):
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    success, message = run_video_upload(video_id)
    record_video_event(video_id, "run", message, {"success": success})
    flash(message, "success" if success else "error")
    return redirect_back("index", current_page)


@app.post("/videos/<int:video_id>/send-run")
def send_and_run_video(video_id: int):
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    success, message = queue_video_upload(video_id)
    record_video_event(video_id, "send_run", message, {"success": success})
    flash(message, "success" if success else "error")
    return redirect_back("index", current_page)


@app.post("/videos/<int:video_id>/refresh-upload-status")
def refresh_upload_status(video_id: int):
    init_db()
    success, message, item = refresh_video_upload_status(video_id)
    status_code = 200 if success else 400
    return jsonify({"success": success, "message": message, "item": item}), status_code


@app.post("/api/uploads/<int:upload_job_id>/update")
def edit_api_upload_job(upload_job_id: int):
    current_page = normalize_page(request.args.get("page", type=int))
    payload = upload_job_form_to_payload(request.form)
    errors = validate_upload_job_payload(payload)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect_back("api_jobs_page", current_page, edit_upload=upload_job_id)

    success, message, _item = update_upload_job(upload_job_id, payload)
    record_video_event(None, "api_upload_update", message, {"upload_job_id": upload_job_id, "success": success})
    flash(message, "success" if success else "error")
    if success:
        return redirect_back("api_jobs_page", current_page)
    return redirect_back("api_jobs_page", current_page, edit_upload=upload_job_id)


@app.post("/api/uploads/<int:upload_job_id>/delete")
def delete_api_upload_job(upload_job_id: int):
    current_page = normalize_page(request.args.get("page", type=int))
    success, message = remove_upload_job(upload_job_id)
    record_video_event(None, "api_upload_delete", message, {"upload_job_id": upload_job_id, "success": success})
    flash(message, "success" if success else "error")
    return redirect_back("api_jobs_page", current_page)


@app.post("/api/uploads/<int:upload_job_id>/run")
def run_api_upload_job(upload_job_id: int):
    current_page = normalize_page(request.args.get("page", type=int))
    success, message = run_upload_job_direct(upload_job_id)
    record_video_event(None, "api_upload_run", message, {"upload_job_id": upload_job_id, "success": success})
    flash(message, "success" if success else "error")
    return redirect_back("api_jobs_page", current_page)


@app.get("/upload-summary")
def upload_summary():
    try:
        item = fetch_upload_summary()
        return jsonify({"success": True, "item": item})
    except RuntimeError as error:
        return jsonify({"success": False, "message": str(error), "item": default_upload_summary()}), 502


@app.get("/health-status")
def health_status_api():
    item = build_health_status()
    return jsonify({"success": item["ok"], "item": item}), 200 if item["ok"] else 503


@app.get("/settings")
def settings_page():
    return render_template(
        "settings.html",
        settings=build_settings_context(),
        health_status=build_health_status(),
    )


@app.post("/videos/<int:video_id>/delete")
def remove_video(video_id: int):
    init_db()
    current_page = normalize_page(request.args.get("page", type=int))
    if delete_video(video_id):
        record_video_event(video_id, "deleted", "ลบรายการวิดีโอ", {"video_id": video_id})
        flash("ลบรายการเรียบร้อยแล้ว", "success")
    else:
        flash("ไม่พบรายการที่ต้องการลบ", "error")
    return redirect_back("index", current_page)


if __name__ == "__main__":
    init_db()
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=parse_positive_int(os.getenv("PORT", "5000")) or 5000,
    )
