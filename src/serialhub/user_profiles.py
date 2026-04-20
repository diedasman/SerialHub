from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from serialhub.config import get_data_dir

_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*]+')
_APP_STATE_PATH = "app_state.json"
_USERS_DIRNAME = "users"
_DEFAULT_THEME_NAME = "app-dark"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")


def normalize_username(username: str) -> str:
    safe_name = _INVALID_PATH_CHARS.sub("_", username.strip()).strip(" .")
    if not safe_name:
        raise ValueError("Enter a username first.")
    return safe_name


def normalize_command_config_name(name: str) -> str:
    safe_name = _INVALID_PATH_CHARS.sub("_", name.strip()).strip(" .")
    if safe_name.lower().endswith(".json"):
        safe_name = safe_name[:-5]
    if not safe_name:
        raise ValueError("Command config names cannot be blank.")
    return safe_name


def get_users_dir() -> Path:
    path = get_data_dir() / _USERS_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_dir(username: str) -> Path:
    path = get_users_dir() / normalize_username(username)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_profile_path(username: str) -> Path:
    normalized = normalize_username(username)
    return get_user_dir(normalized) / f"{normalized}.json"


def get_user_command_config_path(username: str, config_name: str) -> Path:
    return get_user_dir(username) / f"{normalize_command_config_name(config_name)}.json"


def get_user_message_history_path(username: str) -> Path:
    return get_user_dir(username) / "message_history.txt"


def get_user_tcp_ip_history_path(username: str) -> Path:
    return get_user_dir(username) / "tcp_ip_history.txt"


def get_user_tcp_port_history_path(username: str) -> Path:
    return get_user_dir(username) / "tcp_port_history.txt"


def get_user_default_logs_dir(username: str) -> Path:
    path = get_user_dir(username) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_state_path() -> Path:
    return get_data_dir() / _APP_STATE_PATH


@dataclass(slots=True)
class UserProfile:
    username: str
    theme: str = _DEFAULT_THEME_NAME
    log_folder: str = ""
    command_configs: list[str] = field(default_factory=lambda: ["blank"])

    def to_dict(self) -> dict[str, object]:
        return {
            "USERNAME": self.username,
            "THEME": self.theme,
            "LOG_FOLDER": self.log_folder,
            "COMMAND_CONFIGS": self.command_configs,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> UserProfile:
        username = normalize_username(str(payload.get("USERNAME", "")))
        theme = str(payload.get("THEME", _DEFAULT_THEME_NAME)).strip() or _DEFAULT_THEME_NAME
        log_folder = str(payload.get("LOG_FOLDER", "")).strip()
        command_configs = [
            normalize_command_config_name(str(item))
            for item in payload.get("COMMAND_CONFIGS", [])
            if str(item).strip()
        ]
        if not command_configs:
            command_configs = ["blank"]
        return cls(
            username=username,
            theme=theme,
            log_folder=log_folder,
            command_configs=command_configs,
        )


@dataclass(slots=True)
class CommandConfig:
    key: str
    name: str
    commands: dict[str, object]
    path: Path


def save_user_profile(profile: UserProfile) -> None:
    normalized = normalize_username(profile.username)
    _write_json(
        get_user_profile_path(normalized),
        UserProfile(
            username=normalized,
            theme=profile.theme,
            log_folder=profile.log_folder,
            command_configs=[normalize_command_config_name(item) for item in profile.command_configs],
        ).to_dict(),
    )


def load_user_profile(username: str) -> UserProfile | None:
    path = get_user_profile_path(username)
    if not path.exists():
        return None
    return UserProfile.from_dict(_read_json(path))


def _blank_command_config_payload() -> dict[str, object]:
    return {
        "NAME": "BLANK",
        "COMMANDS": {},
    }


def _starter_command_config_payload() -> dict[str, object]:
    return {
        "NAME": "DEFAULTS",
        "COMMANDS": {},
    }


def create_user_profile(username: str) -> UserProfile:
    normalized = normalize_username(username)
    profile_path = get_user_profile_path(normalized)
    if profile_path.exists():
        raise FileExistsError(f"User '{normalized}' already exists.")

    profile = UserProfile(
        username=normalized,
        theme=_DEFAULT_THEME_NAME,
        log_folder="",
        command_configs=[f"{normalized}_cmds", "blank"],
    )
    save_user_profile(profile)

    _write_json(
        get_user_command_config_path(normalized, f"{normalized}_cmds"),
        _starter_command_config_payload(),
    )
    _write_json(
        get_user_command_config_path(normalized, "blank"),
        _blank_command_config_payload(),
    )
    return profile


def load_command_configs(profile: UserProfile) -> list[CommandConfig]:
    configs: list[CommandConfig] = []
    for item in profile.command_configs:
        key = normalize_command_config_name(item)
        path = get_user_command_config_path(profile.username, key)
        if not path.exists():
            continue

        payload = _read_json(path)
        name = str(payload.get("NAME", key)).strip() or key
        commands = payload.get("COMMANDS", {})
        if not isinstance(commands, dict):
            continue
        configs.append(CommandConfig(key=key, name=name, commands=commands, path=path))
    return configs


def get_remembered_username() -> str | None:
    path = get_app_state_path()
    if not path.exists():
        return None
    remembered = str(_read_json(path).get("REMEMBERED_USERNAME", "")).strip()
    return remembered or None


def set_remembered_username(username: str | None) -> None:
    remembered = normalize_username(username) if username else ""
    _write_json(get_app_state_path(), {"REMEMBERED_USERNAME": remembered})
