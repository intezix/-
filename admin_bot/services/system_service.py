from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Сервисы, которыми управляет System-панель.
# Ключ = имя docker compose service, значение = человеческое название.
MANAGED_SERVICES: dict[str, str] = {
    "payment_bot": "💳 Payment Bot",
    "main_bot":    "🤖 Main Bot",
    "support_bot": "🆘 Support Bot",
}

# Эмодзи состояния контейнера
STATE_ICON: dict[str, str] = {
    "running":    "✅",
    "exited":     "🔴",
    "paused":     "⏸",
    "restarting": "🔄",
    "dead":       "💀",
    "created":    "🆕",
}


class SystemService:
    """
    Обёртка над docker CLI: статус контейнеров, перезапуск, логи.

    Требует:
      project_name   — имя docker compose проекта (docker compose -p NAME)
      compose_dir    — путь к директории с docker-compose.yml (опционально,
                       нужен только для `docker compose restart`)
    """

    def __init__(self, *, project_name: str, compose_dir: str | None = None) -> None:
        self._project = project_name
        self._dir = compose_dir

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _run(self, *args: str, timeout: float = 30.0) -> tuple[int, str, str]:
        """Run a subprocess, return (returncode, stdout, stderr)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")
        except asyncio.TimeoutError:
            logger.warning("docker command timed out: %s", args)
            return 1, "", "Timeout"
        except FileNotFoundError:
            return 1, "", "docker не найден в PATH"
        except Exception as exc:
            logger.exception("system_service error: %s", exc)
            return 1, "", str(exc)

    def _container_name(self, service: str) -> str:
        return f"{self._project}-{service}-1"

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_status(self) -> list[dict]:
        """
        Возвращает список {service, label, container, running, state, icon}.
        Вызывает по одному `docker inspect` на каждый сервис.
        """
        results = []
        for svc, label in MANAGED_SERVICES.items():
            cname = self._container_name(svc)
            rc, out, _ = await self._run(
                "docker", "inspect", cname, "--format", "{{.State.Status}}"
            )
            if rc != 0 or not out.strip():
                state = "не найден"
                running = False
            else:
                state = out.strip().lower()
                running = state == "running"
            results.append({
                "service": svc,
                "label": label,
                "container": cname,
                "running": running,
                "state": state,
                "icon": STATE_ICON.get(state, "❓"),
            })
        return results

    async def restart(self, service: str) -> tuple[bool, str]:
        """
        Перезапустить сервис. Пробует:
          1) docker compose -p PROJECT --project-directory DIR restart SERVICE
          2) docker restart CONTAINER   (fallback если compose_dir не задан)
        Возвращает (success, output_text).
        """
        if service not in MANAGED_SERVICES:
            return False, "Неизвестный сервис"

        if self._dir:
            rc, out, err = await self._run(
                "docker", "compose",
                "-p", self._project,
                "--project-directory", self._dir,
                "restart", service,
                timeout=60.0,
            )
        else:
            # fallback: restart by container name
            cname = self._container_name(service)
            rc, out, err = await self._run("docker", "restart", cname, timeout=60.0)

        output = (out + err).strip() or "—"
        return rc == 0, output

    async def get_logs(self, service: str, lines: int = 50) -> str:
        """Последние N строк логов контейнера."""
        if service not in MANAGED_SERVICES:
            return "Неизвестный сервис"
        cname = self._container_name(service)
        # docker logs выводит в stderr по умолчанию
        rc, out, err = await self._run(
            "docker", "logs", "--tail", str(lines), "--timestamps", cname
        )
        combined = (out + err).strip()
        return combined or "(логи пусты)"

    def is_configured(self) -> bool:
        """True если project_name задан (не пустой)."""
        return bool(self._project)
