"""RDS configuration screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Label, SelectionList, Static, Switch

from ..step_rail import StepRail
from ..steps import STEP_ORDER


class RdsScreen(Screen):
    """Optional: configure an RDS PostgreSQL instance."""

    _RDS_MANAGED_SECRET_NAMES = (
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_DB",
        "DATABASE_USER",
        "DATABASE_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    )
    _RDS_SECRET_KEY_BY_ENV = {
        "DATABASE_HOST": "host",
        "DATABASE_PORT": "port",
        "DATABASE_DB": "dbname",
        "DATABASE_USER": "username",
        "DATABASE_PASSWORD": "password",
        "POSTGRES_HOST": "host",
        "POSTGRES_PORT": "port",
        "POSTGRES_DB": "dbname",
        "POSTGRES_USER": "username",
        "POSTGRES_PASSWORD": "password",
    }

    def __init__(self, state: dict) -> None:
        super().__init__()
        self._state = state

    def _draft(self) -> dict:
        d = self._state.setdefault("_wizard_draft", {})
        return d.setdefault("rds", {})

    def _service_names(self) -> list[str]:
        names: list[str] = []
        for svc in self._state.get("services", []):
            name = str(svc.get("name", "")).strip()
            if not name or name in names:
                continue
            names.append(name)
        return names

    def compose(self) -> ComposeResult:
        draft = self._draft()
        rds = self._state.get("rds") or {}
        with VerticalScroll(classes="form-container"):
            yield StepRail("rds")
            yield Static("RDS Database (Optional)", classes="title")

            yield Label("Enable RDS PostgreSQL?", classes="section-label")
            yield Switch(
                id="enable_rds",
                value=bool(draft.get("enable_rds", bool(self._state.get("rds")))),
            )

            yield Label("Database name:", classes="section-label")
            yield Input(
                placeholder="myapp",
                id="db_name",
                value=str(draft.get("db_name", rds.get("database_name", ""))),
            )

            yield Label("Instance type:", classes="section-label")
            yield Input(
                placeholder="db.t4g.micro",
                id="db_instance",
                value=str(
                    draft.get("db_instance", rds.get("instance_type", "db.t4g.micro"))
                ),
            )

            yield Label("Storage (GB):", classes="section-label")
            yield Input(
                placeholder="20",
                id="db_storage",
                value=str(
                    draft.get(
                        "db_storage",
                        rds.get("allocated_storage_gb", 20),
                    )
                ),
            )

            yield Label("Grant database access to services:", classes="section-label")
            yield Static(
                "No services yet. Add services first, then return here.",
                id="rds-expose-empty",
            )
            yield SelectionList[str](id="db_expose")

    def on_mount(self) -> None:
        self._refresh_expose_services()

    def _refresh_expose_services(self) -> None:
        draft = self._draft()
        rds = self._state.get("rds") or {}
        draft_expose = draft.get("db_expose_list")
        if draft_expose is not None:
            current_expose = set(draft_expose)
        else:
            current_expose = set(rds.get("expose_to", []))

        service_names = self._service_names()
        empty = self.query_one("#rds-expose-empty", Static)
        selection = self.query_one("#db_expose", SelectionList)
        selection.clear_options()
        if service_names:
            selection.add_options(
                [(name, name, name in current_expose) for name in service_names]
            )
            selection.display = True
            empty.display = False
        else:
            selection.display = False
            empty.display = True

    def _read_expose_checkboxes(self) -> list[str]:
        selection = self.query_one("#db_expose", SelectionList)
        return [str(v) for v in selection.selected]

    def _capture_draft(self) -> None:
        self._draft().update(
            {
                "enable_rds": self.query_one("#enable_rds", Switch).value,
                "db_name": self.query_one("#db_name", Input).value,
                "db_instance": self.query_one("#db_instance", Input).value,
                "db_storage": self.query_one("#db_storage", Input).value,
                "db_expose_list": self._read_expose_checkboxes(),
            }
        )

    def on_input_changed(self, _event: Input.Changed) -> None:
        self._capture_draft()

    def on_switch_changed(self, _event: Switch.Changed) -> None:
        self._capture_draft()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id.startswith("step_nav_"):
            target = event.button.id.replace("step_nav_", "", 1)
            self.app.go_to_step(target)
            return
        if event.button.id == "back":
            self._state["_wizard_last_screen"] = "alb"
            self.app.pop_screen()
        elif event.button.id == "next":
            if self._apply_to_state():
                self.app.advance_to("s3")

    def _apply_to_state(self) -> bool:
        self._capture_draft()
        enabled = self.query_one("#enable_rds", Switch).value
        if enabled:
            db_name = self.query_one("#db_name", Input).value.strip()
            if not db_name:
                self.notify("Database name is required", severity="error")
                return False

            expose_to = self._read_expose_checkboxes()
            self._state["rds"] = {
                "database_name": db_name,
                "instance_type": self.query_one("#db_instance", Input).value.strip()
                or "db.t4g.micro",
                "allocated_storage_gb": int(
                    self.query_one("#db_storage", Input).value.strip() or "20"
                ),
                "expose_to": expose_to,
            }
            self._ensure_rds_managed_secrets(expose_to)
        else:
            self._state["rds"] = None
            self._remove_rds_managed_secrets()
        return True

    def _ensure_rds_managed_secrets(self, default_expose_to: list[str]) -> None:
        secrets = self._state.setdefault("secrets", [])
        existing_by_name = {
            str(sec.get("name")): sec
            for sec in secrets
            if isinstance(sec, dict) and sec.get("name")
        }

        for secret_name in self._RDS_MANAGED_SECRET_NAMES:
            existing = existing_by_name.get(secret_name)
            if existing is not None:
                if str(existing.get("source")) == "rds":
                    if not existing.get("existing_secret_name"):
                        existing["existing_secret_name"] = self._RDS_SECRET_KEY_BY_ENV[
                            secret_name
                        ]
                        existing["existing_secret_display_name"] = (
                            f"RDS {self._RDS_SECRET_KEY_BY_ENV[secret_name]}"
                        )
                    existing["expose_to"] = list(default_expose_to)
                continue
            secrets.append(
                {
                    "name": secret_name,
                    "source": "rds",
                    "existing_secret_name": self._RDS_SECRET_KEY_BY_ENV[secret_name],
                    "existing_secret_display_name": (
                        f"RDS {self._RDS_SECRET_KEY_BY_ENV[secret_name]}"
                    ),
                    "length": 50,
                    "generate_once": True,
                    "expose_to": list(default_expose_to),
                }
            )

    def _remove_rds_managed_secrets(self) -> None:
        self._state["secrets"] = [
            sec
            for sec in self._state.get("secrets", [])
            if not (
                isinstance(sec, dict)
                and str(sec.get("name")) in self._RDS_MANAGED_SECRET_NAMES
                and str(sec.get("source")) == "rds"
            )
        ]

    def before_step_navigation(self, target: str) -> bool:
        current_index = STEP_ORDER.index("rds")
        target_index = (
            STEP_ORDER.index(target) if target in STEP_ORDER else current_index
        )
        if target_index <= current_index:
            self._capture_draft()
            return True
        return self._apply_to_state()
