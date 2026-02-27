"""S3 bucket configuration screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    SelectionList,
    Static,
    Switch,
)

from ..step_rail import StepRail


class S3Screen(Screen):
    """Optional: configure S3 buckets."""

    def __init__(self, state: dict) -> None:
        super().__init__()
        self._state = state
        self._editing_index: int | None = None
        self._connections: list[dict] = []
        self._editing_conn_index: int | None = None

    def _draft(self) -> dict:
        d = self._state.setdefault("_wizard_draft", {})
        return d.setdefault("s3", {})

    def compose(self) -> ComposeResult:
        draft = self._draft()
        with Horizontal(classes="screen-layout"):
            with Vertical(classes="sidebar"):
                yield Static("Added Buckets", classes="title")
                yield ListView(id="item-list")
            with VerticalScroll(classes="form-container"):
                yield StepRail("s3")
                yield Static("S3 Bucket Details (Optional)", classes="title")

                yield Label("Bucket name (logical):", classes="section-label")
                yield Input(
                    placeholder="media",
                    id="bucket_name",
                    value=str(draft.get("bucket_name", "")),
                )

                yield Label("Bucket mode:", classes="section-label")
                yield Select(
                    [
                        ("Create managed bucket", "managed"),
                        ("Use existing bucket", "existing"),
                        ("Create managed bucket + one-time seed copy", "seed-copy"),
                    ],
                    id="bucket_mode",
                    value=str(draft.get("bucket_mode", "managed")),
                )

                yield Label(
                    "Existing bucket name:",
                    id="existing_bucket_name_label",
                    classes="section-label",
                )
                yield Input(
                    placeholder="my-existing-bucket",
                    id="existing_bucket_name",
                    value=str(draft.get("existing_bucket_name", "")),
                )

                yield Label(
                    "Seed source bucket name:",
                    id="seed_source_bucket_name_label",
                    classes="section-label",
                )
                yield Input(
                    placeholder="legacy-media-bucket",
                    id="seed_source_bucket_name",
                    value=str(draft.get("seed_source_bucket_name", "")),
                )

                yield Label(
                    "Run seed copy only in non-prod envs?",
                    id="seed_non_prod_only_label",
                    classes="section-label",
                )
                yield Switch(
                    id="seed_non_prod_only",
                    value=bool(draft.get("seed_non_prod_only", True)),
                )

                yield Label("Enable CloudFront?", classes="section-label")
                yield Switch(id="bucket_cf", value=bool(draft.get("bucket_cf", False)))

                yield Label("Enable CORS?", classes="section-label")
                yield Switch(
                    id="bucket_cors",
                    value=bool(draft.get("bucket_cors", False)),
                )

                yield Label("Public read?", classes="section-label")
                yield Switch(
                    id="bucket_public",
                    value=bool(draft.get("bucket_public", False)),
                )

                yield Static("Service Connections", classes="title")
                yield ListView(id="conn-list")

                yield Label("Services:", classes="section-label")
                yield Static(
                    "No services yet. Add services first, then return here.",
                    id="conn-services-empty",
                )
                yield SelectionList[str](id="conn_services")

                yield Label("Bucket env var name:", classes="section-label")
                yield Input(
                    placeholder="S3_BUCKET_MEDIA",
                    id="conn_env_key",
                    value=str(draft.get("conn_env_key", "")),
                )

                yield Label(
                    "CloudFront URL env var name:",
                    id="conn_cf_label",
                    classes="section-label",
                )
                yield Input(
                    placeholder="MEDIA_CDN_URL",
                    id="conn_cloudfront_env_key",
                    value=str(draft.get("conn_cloudfront_env_key", "")),
                )

                yield Label("Read-only?", classes="section-label")
                yield Switch(
                    id="conn_read_only",
                    value=bool(draft.get("conn_read_only", False)),
                )

                yield Static("Connection actions", classes="section-label")
                with Vertical(classes="button-row"):
                    yield Button("+ Add Connection", id="conn_add", variant="success")
                    yield Button("Update", id="conn_save", variant="success")
                    yield Button("Remove", id="conn_remove", variant="error")

                yield Static("────────────────────────", classes="section-divider")
                yield Static("Bucket actions", classes="section-label")
                with Vertical(classes="button-row"):
                    yield Button("+ Add", id="add", variant="success")
                    yield Button("Update", id="save", variant="success")
                    yield Button("Remove", id="remove", variant="error")

    def on_mount(self) -> None:
        draft = self._draft()
        self._connections = self._normalize_connections(draft.get("connections", []))
        self._editing_conn_index = draft.get("editing_conn_index")
        self._refresh_sidebar()
        self._refresh_conn_list()
        self._update_mode()
        self._refresh_conn_service_options()
        self._toggle_mode_fields()
        self._toggle_cf_fields()
        self._update_conn_mode()

    def _capture_draft(self) -> None:
        self._draft().update(
            {
                "bucket_name": self.query_one("#bucket_name", Input).value,
                "bucket_mode": self._bucket_mode(),
                "existing_bucket_name": self.query_one(
                    "#existing_bucket_name", Input
                ).value,
                "seed_source_bucket_name": self.query_one(
                    "#seed_source_bucket_name", Input
                ).value,
                "seed_non_prod_only": self.query_one(
                    "#seed_non_prod_only", Switch
                ).value,
                "bucket_cf": self.query_one("#bucket_cf", Switch).value,
                "bucket_cors": self.query_one("#bucket_cors", Switch).value,
                "bucket_public": self.query_one("#bucket_public", Switch).value,
                "connections": [dict(conn) for conn in self._connections],
                "editing_bucket_index": self._editing_index,
                "editing_conn_index": self._editing_conn_index,
                "conn_services": self._read_selected_conn_services(),
                "conn_env_key": self.query_one("#conn_env_key", Input).value,
                "conn_cloudfront_env_key": self.query_one(
                    "#conn_cloudfront_env_key", Input
                ).value,
                "conn_read_only": self.query_one("#conn_read_only", Switch).value,
            }
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        self._capture_draft()
        if event.input.id == "bucket_name":
            self._maybe_autofill_env_key(event.value)

    def _maybe_autofill_env_key(self, bucket_name: str) -> None:
        """Auto-fill conn_env_key with a default when bucket name changes."""
        env_key_input = self.query_one("#conn_env_key", Input)
        default = f"S3_BUCKET_{bucket_name.upper().replace('-', '_')}"
        current = env_key_input.value
        if not current or current.startswith("S3_BUCKET_"):
            env_key_input.value = default

    def on_switch_changed(self, event: Switch.Changed) -> None:
        self._capture_draft()
        if event.switch.id == "bucket_cf":
            self._toggle_cf_fields()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._capture_draft()
        if event.select.id == "bucket_mode":
            self._toggle_mode_fields()
            self._toggle_cf_fields()

    def _bucket_mode(self) -> str:
        mode = self.query_one("#bucket_mode", Select).value
        blank = getattr(Select, "BLANK", object())
        null = getattr(Select, "NULL", object())
        if mode in {blank, null, None}:
            return "managed"
        return str(mode)

    @staticmethod
    def _is_select_empty(value: object) -> bool:
        blank = getattr(Select, "BLANK", object())
        null = getattr(Select, "NULL", object())
        return value in {blank, null, None, "", False}

    def _toggle_mode_fields(self) -> None:
        mode = self._bucket_mode()
        is_existing = mode == "existing"
        is_seed_copy = mode == "seed-copy"
        self.query_one("#existing_bucket_name_label", Label).display = is_existing
        self.query_one("#existing_bucket_name", Input).display = is_existing
        self.query_one("#seed_source_bucket_name_label", Label).display = is_seed_copy
        self.query_one("#seed_source_bucket_name", Input).display = is_seed_copy
        self.query_one("#seed_non_prod_only_label", Label).display = is_seed_copy
        self.query_one("#seed_non_prod_only", Switch).display = is_seed_copy

        cloudfront_switch = self.query_one("#bucket_cf", Switch)
        if is_existing and cloudfront_switch.value:
            cloudfront_switch.value = False

    def _toggle_cf_fields(self) -> None:
        """Show/hide CloudFront URL input based on bucket_cf switch value."""
        if self._bucket_mode() == "existing":
            self.query_one("#conn_cf_label", Label).display = False
            self.query_one("#conn_cloudfront_env_key", Input).display = False
            return
        cf_enabled = self.query_one("#bucket_cf", Switch).value
        self.query_one("#conn_cf_label", Label).display = cf_enabled
        self.query_one("#conn_cloudfront_env_key", Input).display = cf_enabled

    def _refresh_conn_service_options(self) -> None:
        """Populate the service multi-select from state services."""
        draft = self._draft()
        selected = set(str(v) for v in draft.get("conn_services", []))
        self._set_conn_service_options(selected)

    def _set_conn_service_options(self, selected_services: set[str]) -> None:
        service_names = self._service_names()
        empty = self.query_one("#conn-services-empty", Static)
        selection = self.query_one("#conn_services", SelectionList)
        selection.clear_options()
        if service_names:
            selection.add_options(
                [(name, name, name in selected_services) for name in service_names]
            )
            selection.display = True
            empty.display = False
        else:
            selection.display = False
            empty.display = True

    def _service_names(self) -> list[str]:
        names: list[str] = []
        for svc in self._state.get("services", []):
            name = str(svc.get("name", "")).strip()
            if not name or name in names:
                continue
            names.append(name)
        return names

    def _read_selected_conn_services(self) -> list[str]:
        selection = self.query_one("#conn_services", SelectionList)
        return [str(v) for v in selection.selected]

    def _refresh_sidebar(self) -> None:
        """Rebuild the sidebar list from current state."""
        lv = self.query_one("#item-list", ListView)
        lv.clear()
        for bucket in self._state.get("s3_buckets", []):
            lv.append(ListItem(Static(bucket["name"])))

    def _refresh_conn_list(self) -> None:
        """Rebuild the connection list from self._connections."""
        lv = self.query_one("#conn-list", ListView)
        lv.clear()
        for conn in self._connections:
            access = "R" if conn.get("read_only") else "R/W"
            services = [str(service) for service in conn.get("services", [])]
            label = f"{', '.join(services)} → {conn['env_key']} [{access}]"
            lv.append(ListItem(Static(label)))

    def _normalize_connections(self, connections: list[dict] | object) -> list[dict]:
        """Normalize legacy single-service rows into grouped services rows."""
        normalized: list[dict] = []
        grouped: dict[tuple[str, str | None, bool], set[str]] = {}

        if not isinstance(connections, list):
            return normalized

        for raw in connections:
            if not isinstance(raw, dict):
                continue

            env_key = str(raw.get("env_key", "")).strip()
            if not env_key:
                continue

            cloudfront_env_key_raw = raw.get("cloudfront_env_key")
            cloudfront_env_key = (
                str(cloudfront_env_key_raw).strip() if cloudfront_env_key_raw else None
            )
            read_only = bool(raw.get("read_only", False))

            services_raw = raw.get("services")
            if isinstance(services_raw, list):
                services = [str(service).strip() for service in services_raw]
            else:
                service = str(raw.get("service", "")).strip()
                services = [service] if service else []

            for service in services:
                if not service:
                    continue
                key = (env_key, cloudfront_env_key, read_only)
                grouped.setdefault(key, set()).add(service)

        for (env_key, cloudfront_env_key, read_only), services in grouped.items():
            normalized.append(
                {
                    "services": sorted(services),
                    "env_key": env_key,
                    "cloudfront_env_key": cloudfront_env_key,
                    "read_only": read_only,
                }
            )

        return normalized

    def _update_mode(self) -> None:
        """Toggle button visibility based on add vs edit mode."""
        editing = self._editing_index is not None
        self.query_one("#add", Button).display = not editing
        self.query_one("#save", Button).display = editing
        self.query_one("#remove", Button).display = editing

    def _update_conn_mode(self) -> None:
        """Toggle connection button visibility based on add vs edit mode."""
        editing = self._editing_conn_index is not None
        self.query_one("#conn_add", Button).display = not editing
        self.query_one("#conn_save", Button).display = editing
        self.query_one("#conn_remove", Button).display = editing

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Route selection by list view id."""
        if event.list_view.id == "item-list":
            self._load_bucket(event.list_view.index)
        elif event.list_view.id == "conn-list":
            self._load_connection(event.list_view.index)

    def _load_bucket(self, idx: int | None) -> None:
        """Load a bucket into the form for editing."""
        buckets = self._state.get("s3_buckets", [])
        if idx is not None and idx < len(buckets):
            self._editing_index = idx
            bucket = buckets[idx]
            self.query_one("#bucket_name", Input).value = str(
                bucket.get("name", "") or ""
            )
            bucket_mode = str(bucket.get("mode", "managed") or "managed")
            self.query_one("#bucket_mode", Select).value = bucket_mode
            self.query_one("#existing_bucket_name", Input).value = str(
                bucket.get("existing_bucket_name") or ""
            )
            self.query_one("#seed_source_bucket_name", Input).value = str(
                bucket.get("seed_source_bucket_name") or ""
            )
            self.query_one("#seed_non_prod_only", Switch).value = bucket.get(
                "seed_non_prod_only", True
            )
            self.query_one("#bucket_cf", Switch).value = bucket.get("cloudfront", False)
            self.query_one("#bucket_cors", Switch).value = bucket.get("cors", False)
            self.query_one("#bucket_public", Switch).value = bucket.get(
                "public_read", False
            )
            self._connections = self._normalize_connections(
                bucket.get("connections", [])
            )
            self._editing_conn_index = None
            self._refresh_conn_list()
            self._clear_conn_form()
            self._update_mode()
            self._toggle_mode_fields()
            self._toggle_cf_fields()

    def _load_connection(self, idx: int | None) -> None:
        """Load a connection into the connection form for editing."""
        if idx is not None and idx < len(self._connections):
            self._editing_conn_index = idx
            conn = self._connections[idx]
            selected = {
                str(service)
                for service in conn.get("services", [])
                if str(service).strip()
            }
            self._set_conn_service_options(selected)
            self.query_one("#conn_env_key", Input).value = conn.get("env_key", "")
            self.query_one("#conn_cloudfront_env_key", Input).value = (
                conn.get("cloudfront_env_key") or ""
            )
            self.query_one("#conn_read_only", Switch).value = conn.get(
                "read_only", False
            )
            self._update_conn_mode()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id.startswith("step_nav_"):
            target = event.button.id.replace("step_nav_", "", 1)
            self.app.go_to_step(target)
            return
        if event.button.id == "back":
            self._flush_active_connection_edit()
            self._state["_wizard_last_screen"] = "rds"
            self.app.pop_screen()
        elif event.button.id == "add":
            self._flush_active_connection_edit()
            self._add_bucket()
        elif event.button.id == "save":
            self._flush_active_connection_edit()
            self._save_bucket()
        elif event.button.id == "remove":
            self._remove_bucket()
        elif event.button.id == "conn_add":
            self._add_connection()
        elif event.button.id == "conn_save":
            self._save_connection()
        elif event.button.id == "conn_remove":
            self._remove_connection()
        elif event.button.id == "next":
            self._persist_for_navigation()
            self.app.advance_to("secrets")

    def before_step_navigation(self, _target: str) -> bool:
        self._persist_for_navigation()
        return True

    def _persist_for_navigation(self) -> None:
        self._flush_active_connection_edit()
        self._capture_draft()
        name = self.query_one("#bucket_name", Input).value.strip()
        if name and self._editing_index is not None:
            self._save_bucket()
            return
        if name and self._editing_index is None:
            existing_index = next(
                (
                    i
                    for i, bucket in enumerate(self._state.get("s3_buckets", []))
                    if str(bucket.get("name", "")).strip() == name
                ),
                None,
            )
            if existing_index is not None:
                self._editing_index = int(existing_index)
                self._save_bucket()
                return
            self._add_bucket()

    def _flush_active_connection_edit(self) -> None:
        """Persist an in-progress connection edit before bucket-level actions."""
        if self._editing_conn_index is not None:
            self._save_connection()

    def _read_form(self) -> dict | None:
        """Read and validate the bucket form fields."""
        name = self.query_one("#bucket_name", Input).value.strip()
        if not name:
            self.notify("Bucket name is required", severity="error")
            return None

        mode = self._bucket_mode()
        existing_bucket_name = self.query_one(
            "#existing_bucket_name", Input
        ).value.strip()
        seed_source_bucket_name = self.query_one(
            "#seed_source_bucket_name", Input
        ).value.strip()
        seed_non_prod_only = self.query_one("#seed_non_prod_only", Switch).value

        if mode == "existing" and not existing_bucket_name:
            self.notify(
                "Existing bucket name is required in existing mode", severity="error"
            )
            return None

        if mode == "seed-copy" and not seed_source_bucket_name:
            self.notify(
                "Seed source bucket name is required in seed-copy mode",
                severity="error",
            )
            return None

        return {
            "name": name,
            "mode": mode,
            "existing_bucket_name": existing_bucket_name or None,
            "seed_source_bucket_name": seed_source_bucket_name or None,
            "seed_non_prod_only": seed_non_prod_only,
            "cloudfront": self.query_one("#bucket_cf", Switch).value,
            "cors": self.query_one("#bucket_cors", Switch).value,
            "public_read": self.query_one("#bucket_public", Switch).value,
            "connections": [dict(conn) for conn in self._connections],
        }

    def _read_conn_form(self) -> dict | None:
        """Read and validate the connection form fields."""
        services = self._read_selected_conn_services()
        if not services:
            self.notify("Select at least one service", severity="error")
            return None

        env_key = self.query_one("#conn_env_key", Input).value.strip()
        if not env_key:
            self.notify("Env var name is required", severity="error")
            return None

        cf_enabled = self.query_one("#bucket_cf", Switch).value
        cloudfront_env_key: str | None = None
        if cf_enabled:
            cf_val = self.query_one("#conn_cloudfront_env_key", Input).value.strip()
            cloudfront_env_key = cf_val if cf_val else None

        read_only = self.query_one("#conn_read_only", Switch).value

        return {
            "services": services,
            "env_key": env_key,
            "cloudfront_env_key": cloudfront_env_key,
            "read_only": read_only,
        }

    def _add_connection(self) -> None:
        conn = self._read_conn_form()
        if conn is None:
            return

        existing_services = {
            str(service)
            for existing in self._connections
            for service in existing.get("services", [])
            if str(service).strip()
        }
        duplicate_services = [
            svc for svc in conn["services"] if svc in existing_services
        ]
        if duplicate_services:
            dup_list = ", ".join(duplicate_services)
            self.notify(
                f"Service connection already exists for: {dup_list}",
                severity="error",
            )
            return

        self._connections.append(
            {
                "services": sorted([str(service) for service in conn["services"]]),
                "env_key": conn["env_key"],
                "cloudfront_env_key": conn.get("cloudfront_env_key"),
                "read_only": conn["read_only"],
            }
        )
        self._refresh_conn_list()
        self._clear_conn_form()
        self.notify(f"Added connection for {len(conn['services'])} service(s)")

    def _save_connection(self) -> None:
        if self._editing_conn_index is None:
            return
        conn = self._read_conn_form()
        if conn is None:
            return

        selected_services = sorted([str(service) for service in conn["services"]])
        other_services = {
            str(service)
            for i, existing in enumerate(self._connections)
            if i != self._editing_conn_index
            for service in existing.get("services", [])
            if str(service).strip()
        }
        duplicate_services = [
            service for service in selected_services if service in other_services
        ]
        if duplicate_services:
            dup_list = ", ".join(duplicate_services)
            self.notify(
                f"Service connection already exists for: {dup_list}",
                severity="error",
            )
            return

        updated_connections = [
            existing
            for i, existing in enumerate(self._connections)
            if i != self._editing_conn_index
        ]
        updated_connections.append(
            {
                "services": selected_services,
                "env_key": conn["env_key"],
                "cloudfront_env_key": conn.get("cloudfront_env_key"),
                "read_only": conn["read_only"],
            }
        )

        self._connections = updated_connections
        self._editing_conn_index = None
        self._refresh_conn_list()
        self._clear_conn_form()
        self.notify(f"Updated connection for {len(selected_services)} service(s)")

    def _remove_connection(self) -> None:
        if self._editing_conn_index is None:
            return
        services = self._connections[self._editing_conn_index].get("services", [])
        del self._connections[self._editing_conn_index]
        self._refresh_conn_list()
        self._clear_conn_form()
        self.notify(f"Removed connection for {len(services)} service(s)")

    def _clear_conn_form(self) -> None:
        """Reset connection form to add mode."""
        self._editing_conn_index = None
        self._set_conn_service_options(set())
        self.query_one("#conn_env_key", Input).value = ""
        self.query_one("#conn_cloudfront_env_key", Input).value = ""
        self.query_one("#conn_read_only", Switch).value = False
        self._update_conn_mode()

    def _add_bucket(self) -> None:
        bucket = self._read_form()
        if bucket is None:
            return
        self._state.setdefault("s3_buckets", []).append(bucket)
        self._clear_form()
        self._refresh_sidebar()
        self.notify(f"Added bucket '{bucket['name']}'")

    def _save_bucket(self) -> None:
        if self._editing_index is None:
            return
        bucket = self._read_form()
        if bucket is None:
            return
        self._state["s3_buckets"][self._editing_index] = bucket
        self._clear_form()
        self._refresh_sidebar()
        self.notify(f"Updated bucket '{bucket['name']}'")

    def _remove_bucket(self) -> None:
        if self._editing_index is None:
            return
        name = self._state["s3_buckets"][self._editing_index]["name"]
        del self._state["s3_buckets"][self._editing_index]
        self._clear_form()
        self._refresh_sidebar()
        self.notify(f"Removed bucket '{name}'")

    def _clear_form(self) -> None:
        """Reset form to add mode."""
        self._editing_index = None
        self._connections = []
        self._editing_conn_index = None
        self.query_one("#bucket_name", Input).value = ""
        self.query_one("#bucket_mode", Select).value = "managed"
        self.query_one("#existing_bucket_name", Input).value = ""
        self.query_one("#seed_source_bucket_name", Input).value = ""
        self.query_one("#seed_non_prod_only", Switch).value = True
        self.query_one("#bucket_cf", Switch).value = False
        self.query_one("#bucket_cors", Switch).value = False
        self.query_one("#bucket_public", Switch).value = False
        self._refresh_conn_list()
        self._clear_conn_form()
        self._update_mode()
        self._toggle_mode_fields()
