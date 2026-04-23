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


def escape_command_value_for_editor(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def unescape_command_value_from_editor(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        if index + 1 >= len(value):
            result.append("\\")
            break

        next_char = value[index + 1]
        if next_char == "r":
            result.append("\r")
        elif next_char == "n":
            result.append("\n")
        elif next_char == '"':
            result.append('"')
        elif next_char == "\\":
            result.append("\\")
        else:
            result.append("\\")
            result.append(next_char)
        index += 2

    return "".join(result)


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


def get_user_command_configs_dir(username: str) -> Path:
    path = get_user_dir(username) / "configs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_legacy_user_command_config_path(username: str, config_name: str) -> Path:
    return get_user_dir(username) / f"{normalize_command_config_name(config_name)}.json"


def get_user_command_config_path(username: str, config_name: str) -> Path:
    return get_user_command_configs_dir(username) / f"{normalize_command_config_name(config_name)}.json"


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
class TcpFavorite:
    host: str
    port: int

    def to_dict(self) -> dict[str, object]:
        return {
            "HOST": self.host,
            "PORT": self.port,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TcpFavorite:
        host = str(payload.get("HOST", "")).strip()
        port = int(payload.get("PORT", 0) or 0)
        if not host:
            raise ValueError("TCP favorite host cannot be blank.")
        if port <= 0:
            raise ValueError("TCP favorite port must be greater than zero.")
        return cls(host=host, port=port)


@dataclass(slots=True)
class UserProfile:
    username: str
    theme: str = _DEFAULT_THEME_NAME
    log_folder: str = ""
    startup_command_config: str = ""
    command_configs: list[str] = field(default_factory=lambda: ["blank"])
    tcp_favorites: list[TcpFavorite] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "USERNAME": self.username,
            "THEME": self.theme,
            "LOG_FOLDER": self.log_folder,
            "STARTUP_COMMAND_CONFIG": self.startup_command_config,
            "COMMAND_CONFIGS": self.command_configs,
            "TCP_FAVORITES": [favorite.to_dict() for favorite in self.tcp_favorites],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> UserProfile:
        username = normalize_username(str(payload.get("USERNAME", "")))
        theme = str(payload.get("THEME", _DEFAULT_THEME_NAME)).strip() or _DEFAULT_THEME_NAME
        log_folder = str(payload.get("LOG_FOLDER", "")).strip()
        startup_command_config = str(payload.get("STARTUP_COMMAND_CONFIG", "")).strip()
        if startup_command_config:
            startup_command_config = normalize_command_config_name(startup_command_config)
        raw_command_configs = payload.get("COMMAND_CONFIGS")
        command_configs = [
            normalize_command_config_name(str(item))
            for item in raw_command_configs or []
            if str(item).strip()
        ]
        if raw_command_configs is None and not command_configs:
            command_configs = ["blank"]
        tcp_favorites: list[TcpFavorite] = []
        for item in payload.get("TCP_FAVORITES", []):
            if not isinstance(item, dict):
                continue
            try:
                tcp_favorites.append(TcpFavorite.from_dict(item))
            except (TypeError, ValueError):
                continue
        return cls(
            username=username,
            theme=theme,
            log_folder=log_folder,
            startup_command_config=startup_command_config,
            command_configs=command_configs,
            tcp_favorites=tcp_favorites,
        )


@dataclass(slots=True)
class CommandConfig:
    key: str
    name: str
    commands: dict[str, object]
    path: Path


def _dedupe_command_config_keys(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = normalize_command_config_name(item)
        if key in seen:
            continue
        result.append(key)
        seen.add(key)
    return result


def _dedupe_tcp_favorites(items: list[TcpFavorite]) -> list[TcpFavorite]:
    result: list[TcpFavorite] = []
    seen: set[tuple[str, int]] = set()
    for item in items:
        key = (item.host, item.port)
        if key in seen:
            continue
        result.append(item)
        seen.add(key)
    return result


def load_command_config_document(path: Path) -> dict[str, object]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Command config '{path.name}' must contain a JSON object.")
    return payload


def save_command_config_document(
    profile: UserProfile,
    config_name: str,
    payload: dict[str, object],
    *,
    previous_path: Path | None = None,
) -> Path:
    key = normalize_command_config_name(config_name)
    target_path = get_user_command_config_path(profile.username, key)

    previous_key = None
    if previous_path is not None:
        previous_key = normalize_command_config_name(previous_path.stem)
        if previous_key != key and target_path.exists():
            raise FileExistsError(f"Command config '{key}.json' already exists.")

    _write_json(target_path, payload)

    if previous_path is not None and previous_path != target_path and previous_path.exists():
        previous_path.unlink()

    config_keys = _dedupe_command_config_keys(profile.command_configs)
    if previous_key is not None and previous_key in config_keys:
        index = config_keys.index(previous_key)
        config_keys[index] = key
        config_keys = _dedupe_command_config_keys(config_keys)
        if profile.startup_command_config:
            startup_key = normalize_command_config_name(profile.startup_command_config)
            if startup_key == previous_key:
                profile.startup_command_config = key
    elif key not in config_keys:
        config_keys.append(key)

    profile.command_configs = config_keys
    save_user_profile(profile)
    return target_path


def delete_command_config_document(profile: UserProfile, path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)

    key = normalize_command_config_name(path.stem)
    path.unlink()
    profile.command_configs = [
        item
        for item in _dedupe_command_config_keys(profile.command_configs)
        if normalize_command_config_name(item) != key
    ]
    if profile.startup_command_config:
        startup_key = normalize_command_config_name(profile.startup_command_config)
        if startup_key == key:
            profile.startup_command_config = ""
    save_user_profile(profile)


def upsert_tcp_favorite(profile: UserProfile, host: str, port: int) -> bool:
    favorite = TcpFavorite(host=str(host).strip(), port=int(port))
    existing = _dedupe_tcp_favorites(profile.tcp_favorites)
    added = all(item.host != favorite.host or item.port != favorite.port for item in existing)
    profile.tcp_favorites = _dedupe_tcp_favorites([favorite, *existing])
    save_user_profile(profile)
    return added


def migrate_legacy_command_configs(username: str) -> None:
    normalized = normalize_username(username)
    user_dir = get_user_dir(normalized)
    configs_dir = get_user_command_configs_dir(normalized)
    profile_path = get_user_profile_path(normalized)

    for path in user_dir.glob("*.json"):
        if path == profile_path:
            continue
        target = configs_dir / path.name
        if target.exists():
            continue
        path.replace(target)


def list_user_command_config_files(username: str) -> list[Path]:
    normalized = normalize_username(username)
    migrate_legacy_command_configs(normalized)
    return sorted(get_user_command_configs_dir(normalized).glob("*.json"))


def save_user_profile(profile: UserProfile) -> None:
    normalized = normalize_username(profile.username)
    _write_json(
        get_user_profile_path(normalized),
        UserProfile(
            username=normalized,
            theme=profile.theme,
            log_folder=profile.log_folder,
            startup_command_config=(
                normalize_command_config_name(profile.startup_command_config)
                if profile.startup_command_config
                else ""
            ),
            command_configs=[normalize_command_config_name(item) for item in profile.command_configs],
            tcp_favorites=_dedupe_tcp_favorites(profile.tcp_favorites),
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
        startup_command_config="",
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
    migrate_legacy_command_configs(profile.username)
    configs: list[CommandConfig] = []
    for item in profile.command_configs:
        key = normalize_command_config_name(item)
        path = get_user_command_config_path(profile.username, key)
        if not path.exists():
            continue

        payload = load_command_config_document(path)
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
