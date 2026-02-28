"""Secrets configuration screen."""

from __future__ import annotations

import threading

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Input,
    Label,
    ListItem,
    ListView,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)

from ..step_rail import StepRail


class SecretsScreen(Screen):
    """Configure additional secrets (env vars injected into containers)."""

    def __init__(self, state: dict) -> None:
        super().__init__()
        self._state = state
        self._editing_index: int | None = None
        self._expose_to: list[str] = []
        self._existing_secret_records: list[dict[str, str]] = []
        self._filtered_existing_secret_records: list[dict[str, str]] = []
        self._selected_existing_secret_id: str | None = None
        self._fetching_existing_secrets = False

    def _draft(self) -> dict:
        d = self._state.setdefault("_wizard_draft", {})
        return d.setdefault("secrets", {})

    def _service_names(self) -> list[str]:
        names: list[str] = []
        for svc in self._state.get("services", []):
            name = str(svc.get("name", "")).strip()
            if not name or name in names:
                continue
            names.append(name)
        return names

    def _capture_form_scroll(self) -> tuple[float, float]:
        container = self.query_one(".form-container", VerticalScroll)
        scroll_x = float(getattr(container, "scroll_x", 0.0))
        scroll_y = float(getattr(container, "scroll_y", 0.0))
        return scroll_x, scroll_y

    def _restore_form_scroll(self, scroll: tuple[float, float]) -> None:
        container = self.query_one(".form-container", VerticalScroll)
        scroll_x, scroll_y = scroll
        self.call_after_refresh(
            lambda: container.scroll_to(
                x=scroll_x, y=scroll_y, animate=False, force=True
            )
        )

    def compose(self) -> ComposeResult:
        draft = self._draft()
        with Horizontal(classes="screen-layout"):
            with Vertical(classes="sidebar"):
                yield Static("Added Secrets", classes="title")
                yield ListView(id="item-list")
            with VerticalScroll(classes="form-container"):
                yield StepRail("secrets")
                yield Static("Secret Details (Optional)", classes="title")

                yield Label("Secret name (env var):", classes="section-label")
                yield Input(
                    placeholder="DJANGO_SECRET_KEY",
                    id="sec_name",
                    value=str(draft.get("sec_name", "")),
                )

                yield Label("Source:", classes="section-label")
                with RadioSet(id="sec_source"):
                    yield RadioButton(
                        "Generate (random value)",
                        value=draft.get("sec_source", "generate") == "generate",
                        id="src_gen",
                    )
                    yield RadioButton(
                        "Environment variable",
                        value=draft.get("sec_source", "generate") == "env",
                        id="src_env",
                    )
                    yield RadioButton(
                        "RDS managed value",
                        value=draft.get("sec_source", "generate") == "rds",
                        id="src_rds",
                    )
                    yield RadioButton(
                        "Existing AWS secret",
                        value=draft.get("sec_source", "generate") == "existing",
                        id="src_existing",
                    )

                yield Label(
                    "Existing secret name:",
                    id="sec_existing_label",
                    classes="section-label",
                )
                yield Input(
                    placeholder="my/secret/name",
                    id="sec_existing_name",
                    value=str(draft.get("sec_existing_name", "")),
                )
                yield Label(
                    "Filter existing secrets:",
                    id="sec_existing_filter_label",
                    classes="section-label",
                )
                yield Input(
                    placeholder="type to filter by name",
                    id="sec_existing_filter",
                    value=str(draft.get("sec_existing_filter", "")),
                )
                yield Button(
                    "Fetch Existing Secrets",
                    id="fetch_existing_secrets",
                    variant="default",
                )
                yield ListView(id="sec_existing_list")

                yield Label("Length (for generated):", classes="section-label")
                yield Input(
                    placeholder="50",
                    id="sec_length",
                    value=str(draft.get("sec_length", "50")),
                )

                yield Label("Expose to services:", classes="section-label")
                yield Static(
                    "No services yet. Add services first, then return here.",
                    id="sec-expose-empty",
                )
                yield SelectionList[str](id="sec-expose-services")

                with Vertical(classes="button-row"):
                    yield Button("+ Add", id="add", variant="success")
                    yield Button("Update", id="save", variant="success")
                    yield Button("Remove", id="remove", variant="error")

    def on_mount(self) -> None:
        self._restore_from_draft()
        self._refresh_expose_services()
        self._refresh_sidebar()
        self._update_mode()
        self._sync_source_fields()

    def _restore_from_draft(self) -> None:
        draft = self._draft()
        if isinstance(draft.get("sec_expose_to"), list):
            self._expose_to = [str(v) for v in draft.get("sec_expose_to", [])]
        selected_id = draft.get("sec_existing_selected_id")
        if selected_id:
            self._selected_existing_secret_id = str(selected_id)

    def _capture_draft(self) -> None:
        self._expose_to = self._read_expose_checkboxes()
        radio_set = self.query_one("#sec_source", RadioSet)
        pressed = radio_set.pressed_button
        source = "generate"
        if pressed and pressed.id == "src_env":
            source = "env"
        elif pressed and pressed.id == "src_rds":
            source = "rds"
        elif pressed and pressed.id == "src_existing":
            source = "existing"

        self._draft().update(
            {
                "sec_name": self.query_one("#sec_name", Input).value,
                "sec_source": source,
                "sec_existing_name": self.query_one("#sec_existing_name", Input).value,
                "sec_existing_filter": self.query_one(
                    "#sec_existing_filter", Input
                ).value,
                "sec_existing_selected_id": self._selected_existing_secret_id,
                "sec_length": self.query_one("#sec_length", Input).value,
                "sec_expose_to": list(self._expose_to),
            }
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "sec_existing_filter":
            self._apply_existing_secret_filter()
        self._capture_draft()

    def on_radio_set_changed(self, _event: RadioSet.Changed) -> None:
        self._sync_source_fields()
        self._capture_draft()

    def _sync_source_fields(self) -> None:
        source = self._selected_source()
        is_generated = source == "generate"
        is_existing = source == "existing"
        is_rds = source == "rds"

        self.query_one("#sec_length", Input).disabled = not is_generated
        self.query_one("#sec_existing_label", Label).display = is_existing or is_rds
        self.query_one("#sec_existing_name", Input).display = is_existing or is_rds
        self.query_one("#sec_existing_filter_label", Label).display = is_existing
        self.query_one("#sec_existing_filter", Input).display = is_existing
        self.query_one("#fetch_existing_secrets", Button).display = is_existing
        self.query_one("#sec_existing_list", ListView).display = is_existing
        self.query_one("#sec_existing_name", Input).disabled = is_rds
        if (
            is_rds
            and self._editing_index is not None
            and self._editing_index < len(self._state.get("secrets", []))
        ):
            current = self._state.get("secrets", [])[self._editing_index]
            self.query_one("#sec_existing_name", Input).value = str(
                current.get("existing_secret_display_name")
                or current.get("existing_secret_name")
                or ""
            )

    def _selected_source(self) -> str:
        radio_set = self.query_one("#sec_source", RadioSet)
        pressed = radio_set.pressed_button
        if pressed and pressed.id == "src_env":
            return "env"
        if pressed and pressed.id == "src_rds":
            return "rds"
        if pressed and pressed.id == "src_existing":
            return "existing"
        return "generate"

    def _set_selected_source(self, source: str) -> None:
        if source == "env":
            self.query_one("#src_env", RadioButton).value = True
            return
        if source == "rds":
            self.query_one("#src_rds", RadioButton).value = True
            return
        if source == "existing":
            self.query_one("#src_existing", RadioButton).value = True
            return
        self.query_one("#src_gen", RadioButton).value = True

    def _refresh_sidebar(self) -> None:
        """Rebuild the sidebar list from current state."""
        lv = self.query_one("#item-list", ListView)
        lv.clear()
        for secret in self._state.get("secrets", []):
            lv.append(ListItem(Static(secret["name"])))

    def _update_mode(self) -> None:
        """Toggle button visibility based on add vs edit mode."""
        editing = self._editing_index is not None
        self.query_one("#add", Button).display = not editing
        self.query_one("#save", Button).display = editing
        self.query_one("#remove", Button).display = editing

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection in secret sidebars/lists."""
        if event.list_view.id == "sec_existing_list":
            idx = event.list_view.index
            if idx is None or idx >= len(self._filtered_existing_secret_records):
                return
            rec = self._filtered_existing_secret_records[idx]
            self._selected_existing_secret_id = rec["secret_id"]
            self.query_one("#sec_existing_name", Input).value = rec["name"]
            self._capture_draft()
            return

        idx = event.list_view.index
        secrets = self._state.get("secrets", [])
        if event.list_view.id == "item-list" and idx is not None and idx < len(secrets):
            self._editing_index = idx
            secret = secrets[idx]
            self.query_one("#sec_name", Input).value = secret.get("name", "")
            self.query_one("#sec_length", Input).value = str(secret.get("length", 50))
            self._expose_to = [str(s) for s in secret.get("expose_to", [])]
            self._refresh_expose_services()
            if secret.get("source") == "env":
                self._set_selected_source("env")
                self._selected_existing_secret_id = None
            elif secret.get("source") == "rds":
                self._set_selected_source("rds")
                self.query_one("#sec_existing_name", Input).value = str(
                    secret.get("existing_secret_display_name")
                    or secret.get("existing_secret_name")
                    or ""
                )
                self._selected_existing_secret_id = None
            elif secret.get("source") == "existing":
                self._set_selected_source("existing")
                self.query_one("#sec_existing_name", Input).value = str(
                    secret.get("existing_secret_display_name")
                    or secret.get("existing_secret_name")
                    or ""
                )
                self._selected_existing_secret_id = (
                    str(secret.get("existing_secret_name") or "") or None
                )
            else:
                self._set_selected_source("generate")
                self._selected_existing_secret_id = None
            self._sync_source_fields()
            self._update_mode()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id.startswith("step_nav_"):
            target = event.button.id.replace("step_nav_", "", 1)
            self.app.go_to_step(target)
            return
        if event.button.id == "back":
            self._state["_wizard_last_screen"] = "s3"
            self.app.pop_screen()
        elif event.button.id == "add":
            self._add_secret()
        elif event.button.id == "save":
            self._save_secret()
        elif event.button.id == "remove":
            self._remove_secret()
        elif event.button.id == "next":
            self._persist_for_navigation()
            self.app.advance_to("review")
        elif event.button.id == "fetch_existing_secrets":
            self._start_fetch_existing_secrets()

    def _start_fetch_existing_secrets(self) -> None:
        if self._fetching_existing_secrets:
            return
        self._fetching_existing_secrets = True
        self.query_one("#fetch_existing_secrets", Button).disabled = True
        threading.Thread(
            target=self._fetch_existing_secrets_worker, daemon=True
        ).start()

    def _fetch_existing_secrets_worker(self) -> None:
        region = str(self._state.get("aws_region", "us-east-1"))
        try:
            sm = boto3.client("secretsmanager", region_name=region)
            paginator = sm.get_paginator("list_secrets")
            records: list[dict[str, str]] = []
            for page in paginator.paginate():
                for sec in page.get("SecretList", []):
                    name = str(sec.get("Name") or "").strip()
                    arn = str(sec.get("ARN") or "").strip()
                    if not name:
                        continue
                    records.append(
                        {
                            "name": name,
                            "secret_id": arn or name,
                        }
                    )
            records.sort(key=lambda item: item["name"])
            self.app.call_from_thread(
                self._complete_fetch_existing_secrets,
                records,
                None,
            )
        except (ClientError, BotoCoreError, RuntimeError) as exc:
            self.app.call_from_thread(
                self._complete_fetch_existing_secrets,
                [],
                str(exc),
            )

    def _complete_fetch_existing_secrets(
        self,
        records: list[dict[str, str]],
        err: str | None,
    ) -> None:
        scroll = self._capture_form_scroll()
        self._fetching_existing_secrets = False
        self.query_one("#fetch_existing_secrets", Button).disabled = False
        if err:
            self.notify(f"Failed to load existing secrets: {err}", severity="error")
            self._restore_form_scroll(scroll)
            return

        self._existing_secret_records = records
        self._apply_existing_secret_filter()
        self.notify("Fetched existing secrets", severity="information")
        self._restore_form_scroll(scroll)

    def _secret_name_for_id(self, secret_id: str) -> str | None:
        for rec in self._existing_secret_records:
            if rec["secret_id"] == secret_id:
                return rec["name"]
        return None

    def _apply_existing_secret_filter(self) -> None:
        filter_text = (
            self.query_one("#sec_existing_filter", Input).value.strip().lower()
        )
        lv = self.query_one("#sec_existing_list", ListView)

        self._filtered_existing_secret_records = [
            rec
            for rec in self._existing_secret_records
            if not filter_text or filter_text in rec["name"].lower()
        ]
        lv.clear()
        for rec in self._filtered_existing_secret_records:
            prefix = (
                "● " if rec["secret_id"] == self._selected_existing_secret_id else "  "
            )
            lv.append(ListItem(Static(f"{prefix}{rec['name']}")))

    def _resolve_existing_secret_id(self, existing_secret_name: str) -> str:
        typed = existing_secret_name.strip()
        if not typed:
            return ""
        for rec in self._existing_secret_records:
            if rec["name"] == typed:
                return rec["secret_id"]
        return self._selected_existing_secret_id or typed

    def before_step_navigation(self, _target: str) -> bool:
        self._persist_for_navigation()
        return True

    def _persist_for_navigation(self) -> None:
        self._capture_draft()
        name = self.query_one("#sec_name", Input).value.strip()
        if self._editing_index is not None:
            self._save_secret()
        elif name:
            existing_index = next(
                (
                    i
                    for i, secret in enumerate(self._state.get("secrets", []))
                    if str(secret.get("name", "")).strip() == name
                ),
                None,
            )
            if existing_index is not None:
                self._editing_index = int(existing_index)
                self._save_secret()
                return
            self._add_secret()

    def _read_form(self) -> dict | None:
        """Read and validate the form fields."""
        name = self.query_one("#sec_name", Input).value.strip()
        if not name:
            self.notify("Secret name is required", severity="error")
            return None

        source = self._selected_source()

        length = int(self.query_one("#sec_length", Input).value.strip() or "50")
        self._expose_to = self._read_expose_checkboxes()

        existing_secret_name = self.query_one("#sec_existing_name", Input).value.strip()
        if source in {"existing", "rds"} and not existing_secret_name:
            self.notify(
                "Existing secret name is required for source=existing/rds",
                severity="error",
            )
            return None

        if source == "rds":
            existing_secret_id = existing_secret_name
            # Keep the canonical JSON key for managed RDS secrets when editing,
            # even if the UI field shows a display label like "RDS dbname".
            if self._editing_index is not None and self._editing_index < len(
                self._state.get("secrets", [])
            ):
                current = self._state.get("secrets", [])[self._editing_index]
                canonical = str(current.get("existing_secret_name") or "").strip()
                if canonical:
                    existing_secret_id = canonical
            display_name = existing_secret_name or existing_secret_id
        else:
            existing_secret_id = self._resolve_existing_secret_id(existing_secret_name)
            display_name = existing_secret_name or None

        return {
            "name": name,
            "source": source,
            "existing_secret_name": existing_secret_id or None,
            "existing_secret_display_name": display_name,
            "length": length,
            "generate_once": True,
            "expose_to": list(self._expose_to),
        }

    def _read_expose_checkboxes(self) -> list[str]:
        selection = self.query_one("#sec-expose-services", SelectionList)
        return [str(v) for v in selection.selected]

    def _refresh_expose_services(self) -> None:
        service_names = self._service_names()
        selected = set(self._expose_to)
        empty = self.query_one("#sec-expose-empty", Static)
        selection = self.query_one("#sec-expose-services", SelectionList)
        selection.clear_options()
        if service_names:
            selection.add_options(
                [(name, name, name in selected) for name in service_names]
            )
            selection.display = True
            empty.display = False
        else:
            selection.display = False
            empty.display = True

    def _add_secret(self) -> None:
        secret = self._read_form()
        if secret is None:
            return
        self._state.setdefault("secrets", []).append(secret)
        self._clear_form()
        self._refresh_sidebar()
        self.notify(f"Added secret '{secret['name']}'")

    def _save_secret(self) -> None:
        if self._editing_index is None:
            return
        secret = self._read_form()
        if secret is None:
            return
        self._state["secrets"][self._editing_index] = secret
        self._clear_form()
        self._refresh_sidebar()
        self.notify(f"Updated secret '{secret['name']}'")

    def _remove_secret(self) -> None:
        if self._editing_index is None:
            return
        name = self._state["secrets"][self._editing_index]["name"]
        del self._state["secrets"][self._editing_index]
        self._clear_form()
        self._refresh_sidebar()
        self.notify(f"Removed secret '{name}'")

    def _clear_form(self) -> None:
        """Reset form to add mode."""
        self._editing_index = None
        self.query_one("#sec_name", Input).value = ""
        self.query_one("#sec_length", Input).value = "50"
        self._set_selected_source("generate")
        self.query_one("#sec_existing_name", Input).value = ""
        self.query_one("#sec_existing_filter", Input).value = ""
        self._existing_secret_records = []
        self._filtered_existing_secret_records = []
        self._selected_existing_secret_id = None
        self.query_one("#sec_existing_list", ListView).clear()
        self._expose_to = []
        self._refresh_expose_services()
        self._sync_source_fields()
        self._update_mode()
