#!/usr/bin/env python3
from __future__ import annotations

import cgi
import json
import mimetypes
import os
import re
import shutil
import sys
import time
import urllib.parse
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GROUPS = {"female", "male", "brow"}
WORKWALL_SLOTS = {"main", "side_top", "side_middle", "side_bottom"}
UPLOADS_PREFIX = "/uploads"
CASE_IMAGE_PREFIX = f"{UPLOADS_PREFIX}/case-gallery/images"
WORKWALL_IMAGE_PREFIX = f"{UPLOADS_PREFIX}/workwall"
PERSISTENT_ROOT = Path(os.environ.get("SONG_PERSISTENT_ROOT", ROOT / "persistent-data")).resolve()
DATA_DIR = PERSISTENT_ROOT / "case-gallery"
IMAGE_DIR = DATA_DIR / "images"
MANIFEST_PATH = DATA_DIR / "cases.json"
REGISTRATION_PATH = DATA_DIR / "coupon-registrations.json"
WORKWALL_DIR = PERSISTENT_ROOT / "workwall"
WORKWALL_MANIFEST_PATH = WORKWALL_DIR / "manifest.json"
LEGACY_CASE_DIR = ROOT / "assets" / "case-gallery"
LEGACY_CASE_IMAGE_DIR = LEGACY_CASE_DIR / "images"
LEGACY_CASE_MANIFEST_PATH = LEGACY_CASE_DIR / "cases.json"
LEGACY_REGISTRATION_PATH = LEGACY_CASE_DIR / "coupon-registrations.json"
LEGACY_WORKWALL_DIR = ROOT / "assets" / "workwall"
LEGACY_WORKWALL_MANIFEST_PATH = LEGACY_WORKWALL_DIR / "manifest.json"


def normalize_case_src(src: str) -> str:
    src = str(src or "")
    if src.startswith("/assets/case-gallery/images/"):
        return src.replace("/assets/case-gallery/images", CASE_IMAGE_PREFIX, 1)
    return src


def normalize_workwall_src(src: str) -> str:
    src = str(src or "")
    if src.startswith("/assets/workwall/"):
        return src.replace("/assets/workwall", WORKWALL_IMAGE_PREFIX, 1)
    return src


def migrate_legacy_storage() -> None:
    for group in GROUPS:
        legacy_group_dir = LEGACY_CASE_IMAGE_DIR / group
        if legacy_group_dir.exists():
            shutil.copytree(legacy_group_dir, IMAGE_DIR / group, dirs_exist_ok=True)

    if LEGACY_WORKWALL_DIR.exists():
        for entry in LEGACY_WORKWALL_DIR.iterdir():
            if entry.is_file() and entry.name != "manifest.json":
                target = WORKWALL_DIR / entry.name
                if not target.exists():
                    shutil.copy2(entry, target)

    if not MANIFEST_PATH.exists():
        if LEGACY_CASE_MANIFEST_PATH.exists():
            payload = json.loads(LEGACY_CASE_MANIFEST_PATH.read_text(encoding="utf-8"))
            payload["items"] = [
                {**item, "src": normalize_case_src(item.get("src", ""))}
                for item in payload.get("items", [])
            ]
            MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            MANIFEST_PATH.write_text(
                json.dumps({"updatedAt": int(time.time() * 1000), "items": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    if not REGISTRATION_PATH.exists():
        if LEGACY_REGISTRATION_PATH.exists():
            REGISTRATION_PATH.write_text(LEGACY_REGISTRATION_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            REGISTRATION_PATH.write_text(
                json.dumps({"updatedAt": int(time.time() * 1000), "items": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    if not WORKWALL_MANIFEST_PATH.exists():
        if LEGACY_WORKWALL_MANIFEST_PATH.exists():
            payload = json.loads(LEGACY_WORKWALL_MANIFEST_PATH.read_text(encoding="utf-8"))
            payload["items"] = [
                {**item, "src": normalize_workwall_src(item.get("src", ""))}
                for item in payload.get("items", [])
            ]
            WORKWALL_MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            WORKWALL_MANIFEST_PATH.write_text(
                json.dumps({"updatedAt": int(time.time() * 1000), "items": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def src_to_path(src: str) -> Path | None:
    src = str(src or "")
    if src.startswith(f"{UPLOADS_PREFIX}/"):
        relative = src[len(UPLOADS_PREFIX) + 1 :]
        target = (PERSISTENT_ROOT / relative).resolve()
        if str(target).startswith(str(PERSISTENT_ROOT)):
            return target
        return None
    if src.startswith("/assets/"):
        target = (ROOT / src.lstrip("/")).resolve()
        if str(target).startswith(str(ROOT)):
            return target
    return None


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for group in GROUPS:
        (IMAGE_DIR / group).mkdir(parents=True, exist_ok=True)
    WORKWALL_DIR.mkdir(parents=True, exist_ok=True)
    migrate_legacy_storage()


def read_manifest() -> dict:
    ensure_storage()
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"updatedAt": int(time.time() * 1000), "items": []}


def write_manifest(payload: dict) -> None:
    ensure_storage()
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_registrations() -> dict:
    ensure_storage()
    try:
        return json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"updatedAt": int(time.time() * 1000), "items": []}


def write_registrations(payload: dict) -> None:
    ensure_storage()
    REGISTRATION_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_workwall_manifest() -> dict:
    ensure_storage()
    try:
        return json.loads(WORKWALL_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"updatedAt": int(time.time() * 1000), "items": []}


def write_workwall_manifest(payload: dict) -> None:
    ensure_storage()
    WORKWALL_MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "image").stem
    ext = Path(filename or ".jpg").suffix.lower() or ".jpg"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-") or "image"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        ext = ".jpg"
    return f"{safe_name}{ext}"


def build_cases_payload(manifest: dict) -> dict:
    groups = {group: [] for group in GROUPS}
    for item in sorted(manifest.get("items", []), key=lambda entry: entry.get("createdAt", 0)):
        group = item.get("group")
        if group in groups:
            groups[group].append(item)
    return {
      "updatedAt": manifest.get("updatedAt", int(time.time() * 1000)),
      "groups": groups,
      "total": sum(len(items) for items in groups.values()),
    }


def is_seed_item(item: dict) -> bool:
    return str(item.get("id", "")).startswith("seed-")


class GalleryHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
      self.send_header("Cache-Control", "no-store")
      super().end_headers()

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"", "/"}:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/generated-views/visitor-homepage.html")
            self.end_headers()
            return
        if parsed.path == "/dashboard":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/generated-views/coupon-registrations-dashboard.html")
            self.end_headers()
            return
        if parsed.path == "/healthz":
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/cases":
            manifest = read_manifest()
            self.send_json(build_cases_payload(manifest))
            return
        if parsed.path == "/api/coupon/registrations":
            self.send_json(read_registrations())
            return
        if parsed.path == "/api/workwall":
            self.send_json(read_workwall_manifest())
            return
        if parsed.path.startswith(f"{UPLOADS_PREFIX}/"):
            self.handle_uploaded_file(parsed.path)
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/cases/upload":
            self.handle_upload(parsed)
            return
        if parsed.path == "/api/cases/delete":
            self.handle_delete()
            return
        if parsed.path == "/api/cases/clear":
            self.handle_clear()
            return
        if parsed.path == "/api/coupon/register":
            self.handle_coupon_register()
            return
        if parsed.path == "/api/coupon/delete":
            self.handle_coupon_delete()
            return
        if parsed.path == "/api/coupon/update":
            self.handle_coupon_update()
            return
        if parsed.path == "/api/workwall/upload":
            self.handle_workwall_upload(parsed)
            return
        if parsed.path == "/api/workwall/delete":
            self.handle_workwall_delete()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")

    def parse_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def handle_uploaded_file(self, path: str) -> None:
        file_path = src_to_path(path)
        if not file_path or not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Uploaded file not found")
            return

        try:
            body = file_path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to read uploaded file")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_upload(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        group = params.get("group", [""])[0]
        if group not in GROUPS:
            self.send_json({"error": "Invalid group"}, HTTPStatus.BAD_REQUEST)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )

        file_fields = form["files"] if "files" in form else []
        if not isinstance(file_fields, list):
            file_fields = [file_fields]

        manifest = read_manifest()
        items = manifest.get("items", [])
        group_items = [item for item in items if item.get("group") == group]
        if group_items and all(is_seed_item(item) for item in group_items):
            items = [item for item in items if item.get("group") != group]
        created_items = []
        now = int(time.time() * 1000)

        for offset, field in enumerate(file_fields):
            if not getattr(field, "file", None):
                continue
            safe_name = sanitize_filename(getattr(field, "filename", "image.jpg"))
            item_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
            target_name = f"{item_id}-{safe_name}"
            target_path = IMAGE_DIR / group / target_name
            with target_path.open("wb") as target:
                shutil.copyfileobj(field.file, target)
            item = {
                "id": item_id,
                "group": group,
                "name": getattr(field, "filename", safe_name),
                "src": f"{CASE_IMAGE_PREFIX}/{group}/{target_name}",
                "createdAt": now + offset,
            }
            items.append(item)
            created_items.append(item)

        manifest["items"] = items
        manifest["updatedAt"] = int(time.time() * 1000)
        write_manifest(manifest)
        self.send_json({
            "ok": True,
            "items": created_items,
            "cases": build_cases_payload(manifest),
        })

    def handle_delete(self) -> None:
        payload = self.parse_json_body()
        item_id = payload.get("id")
        group = payload.get("group")
        if not item_id or group not in GROUPS:
            self.send_json({"error": "Missing id or group"}, HTTPStatus.BAD_REQUEST)
            return

        manifest = read_manifest()
        kept_items = []
        removed_item = None
        for item in manifest.get("items", []):
            if item.get("id") == item_id and item.get("group") == group and removed_item is None:
                removed_item = item
                continue
            kept_items.append(item)

        if removed_item:
            src_path = src_to_path(removed_item.get("src", ""))
            if src_path and src_path.exists():
                src_path.unlink()

        manifest["items"] = kept_items
        manifest["updatedAt"] = int(time.time() * 1000)
        write_manifest(manifest)
        self.send_json({"ok": True, "cases": build_cases_payload(manifest)})

    def handle_clear(self) -> None:
        payload = self.parse_json_body()
        group = payload.get("group")
        if group not in GROUPS:
            self.send_json({"error": "Invalid group"}, HTTPStatus.BAD_REQUEST)
            return

        manifest = read_manifest()
        kept_items = []
        for item in manifest.get("items", []):
            if item.get("group") == group:
                src_path = src_to_path(item.get("src", ""))
                if src_path and src_path.exists():
                    src_path.unlink()
            else:
                kept_items.append(item)

        manifest["items"] = kept_items
        manifest["updatedAt"] = int(time.time() * 1000)
        write_manifest(manifest)
        self.send_json({"ok": True, "cases": build_cases_payload(manifest)})

    def handle_coupon_register(self) -> None:
        payload = self.parse_json_body()
        name = str(payload.get("name", "")).strip()
        contact = str(payload.get("contact", "")).strip()
        secret = str(payload.get("secret", "")).strip()
        coupon_template = str(payload.get("template", "")).strip()

        if not name or not contact:
            self.send_json({"error": "Missing name or contact"}, HTTPStatus.BAD_REQUEST)
            return

        registrations = read_registrations()
        items = registrations.get("items", [])
        ticket_no = f"SONG-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        created_at = int(time.time() * 1000)
        item = {
            "id": uuid.uuid4().hex,
            "name": name,
            "contact": contact,
            "secret": secret,
            "template": coupon_template,
            "ticketNo": ticket_no,
            "createdAt": created_at,
            "status": "new",
        }
        items.append(item)
        registrations["items"] = items
        registrations["updatedAt"] = created_at
        write_registrations(registrations)
        self.send_json({
            "ok": True,
            "ticketNo": ticket_no,
            "createdAt": created_at,
        })

    def handle_coupon_delete(self) -> None:
        payload = self.parse_json_body()
        item_id = str(payload.get("id", "")).strip()
        if not item_id:
            self.send_json({"error": "Missing registration id"}, HTTPStatus.BAD_REQUEST)
            return

        registrations = read_registrations()
        items = registrations.get("items", [])
        kept_items = [item for item in items if str(item.get("id", "")) != item_id]

        if len(kept_items) == len(items):
            self.send_json({"error": "Registration not found"}, HTTPStatus.NOT_FOUND)
            return

        registrations["items"] = kept_items
        registrations["updatedAt"] = int(time.time() * 1000)
        write_registrations(registrations)
        self.send_json({
            "ok": True,
            "items": kept_items,
            "updatedAt": registrations["updatedAt"],
        })

    def handle_coupon_update(self) -> None:
        payload = self.parse_json_body()
        item_id = str(payload.get("id", "")).strip()
        status = str(payload.get("status", "")).strip()
        allowed_status = {"new", "contacted"}

        if not item_id:
            self.send_json({"error": "Missing registration id"}, HTTPStatus.BAD_REQUEST)
            return
        if status not in allowed_status:
            self.send_json({"error": "Invalid status"}, HTTPStatus.BAD_REQUEST)
            return

        registrations = read_registrations()
        items = registrations.get("items", [])
        updated = False
        for item in items:
            if str(item.get("id", "")) == item_id:
                item["status"] = status
                updated = True
                break

        if not updated:
            self.send_json({"error": "Registration not found"}, HTTPStatus.NOT_FOUND)
            return

        registrations["items"] = items
        registrations["updatedAt"] = int(time.time() * 1000)
        write_registrations(registrations)
        self.send_json({
            "ok": True,
            "items": items,
            "updatedAt": registrations["updatedAt"],
        })

    def handle_workwall_upload(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        slot = params.get("slot", [""])[0]
        if slot not in WORKWALL_SLOTS:
            self.send_json({"error": "Invalid slot"}, HTTPStatus.BAD_REQUEST)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )
        file_field = form["file"] if "file" in form else None
        if not getattr(file_field, "file", None):
            self.send_json({"error": "Missing file"}, HTTPStatus.BAD_REQUEST)
            return

        manifest = read_workwall_manifest()
        items = manifest.get("items", [])
        existing = next((item for item in items if item.get("slot") == slot), None)
        if existing:
            old_path = src_to_path(existing.get("src", ""))
            if old_path and old_path.exists():
                old_path.unlink()

        safe_name = sanitize_filename(getattr(file_field, "filename", "workwall.jpg"))
        item_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        target_name = f"{slot}-{item_id}-{safe_name}"
        target_path = WORKWALL_DIR / target_name
        with target_path.open("wb") as target:
            shutil.copyfileobj(file_field.file, target)

        new_item = {
            "id": item_id,
            "slot": slot,
            "name": getattr(file_field, "filename", safe_name),
            "src": f"{WORKWALL_IMAGE_PREFIX}/{target_name}",
            "updatedAt": int(time.time() * 1000),
        }

        items = [item for item in items if item.get("slot") != slot]
        items.append(new_item)
        manifest["items"] = items
        manifest["updatedAt"] = int(time.time() * 1000)
        write_workwall_manifest(manifest)
        self.send_json({"ok": True, "item": new_item, "items": items, "updatedAt": manifest["updatedAt"]})

    def handle_workwall_delete(self) -> None:
        payload = self.parse_json_body()
        slot = str(payload.get("slot", "")).strip()
        if slot not in WORKWALL_SLOTS:
            self.send_json({"error": "Invalid slot"}, HTTPStatus.BAD_REQUEST)
            return

        manifest = read_workwall_manifest()
        items = manifest.get("items", [])
        removed = next((item for item in items if item.get("slot") == slot), None)
        kept = [item for item in items if item.get("slot") != slot]

        if removed:
            file_path = src_to_path(removed.get("src", ""))
            if file_path and file_path.exists():
                file_path.unlink()

        manifest["items"] = kept
        manifest["updatedAt"] = int(time.time() * 1000)
        write_workwall_manifest(manifest)
        self.send_json({"ok": True, "items": kept, "updatedAt": manifest["updatedAt"]})


def main() -> None:
    ensure_storage()
    host = os.environ.get("SONG_GALLERY_HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("SONG_GALLERY_PORT", "8123")))
    server = ThreadingHTTPServer((host, port), GalleryHandler)
    print(f"Serving Song gallery on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
