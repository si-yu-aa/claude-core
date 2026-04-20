"""Permission helpers for built-in tools."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Callable

from claude_core.tools.base import PermissionResult


PermissionSpec = str | dict


def workspace_root() -> Path:
    """Return the current workspace root used for tool path checks."""
    return Path.cwd().resolve()


def normalize_file_path(file_path: str, *, root: str | Path | None = None) -> str:
    """Normalize a file path and keep it inside the active workspace."""
    if not file_path:
        raise PermissionError("file_path is required")

    workspace = Path(root).resolve() if root is not None else workspace_root()
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    normalized = candidate.resolve(strict=False)

    try:
        normalized.relative_to(workspace)
    except ValueError as exc:
        raise PermissionError(f"path escapes workspace: {file_path}") from exc

    return str(normalized)


def _normalize_permission_spec(spec: PermissionSpec) -> dict:
    if isinstance(spec, str):
        return {"rule": spec}
    return dict(spec)


def _rule_matches(pattern: str, rule: str, path: str | None) -> bool:
    if pattern == rule:
        return True

    prefix = f"{rule}:"
    if not pattern.startswith(prefix) or path is None:
        return False

    path_pattern = pattern[len(prefix):]
    return fnmatchcase(path, path_pattern)


def _is_allowed(permission_context, rule: str, path: str | None) -> bool:
    return any(
        _rule_matches(candidate, rule, path)
        for candidate in getattr(permission_context, "always_allow_rules", []) or []
    )


def _is_denied(permission_context, rule: str, path: str | None) -> bool:
    return any(
        _rule_matches(candidate, rule, path)
        for candidate in getattr(permission_context, "deny_rules", []) or []
    )


def check_rule(
    context,
    spec: PermissionSpec,
    decision_classification: str,
) -> PermissionResult:
    """Evaluate a permission rule against the current context."""
    permission_context = getattr(getattr(context, "options", None), "permission_context", None)
    normalized = _normalize_permission_spec(spec)
    rule = normalized["rule"]
    path = normalized.get("path")
    updated_input = normalized.get("updated_input")

    if permission_context is None:
        return PermissionResult(
            behavior="ask",
            message=f"Permission required for {rule}",
            decision_classification=decision_classification,
        )

    if _is_allowed(permission_context, rule, path):
        return PermissionResult(
            behavior="allow",
            updated_input=updated_input,
            decision_classification=decision_classification,
        )

    if _is_denied(permission_context, rule, path):
        return PermissionResult(
            behavior="deny",
            message=f"Permission denied for {rule}",
            decision_classification=decision_classification,
        )

    return PermissionResult(
        behavior="ask",
        message=f"Permission required for {rule}",
        decision_classification=decision_classification,
    )


def build_permission_checker(
    rule_resolver: Callable[[dict], PermissionSpec],
    decision_classification: str,
):
    """Create a permission hook from tool input to permission rule metadata."""

    async def check_permissions(input_data: dict, context) -> PermissionResult:
        try:
            spec = rule_resolver(input_data)
        except PermissionError as exc:
            return PermissionResult(
                behavior="deny",
                message=str(exc),
                decision_classification=decision_classification,
            )

        return check_rule(
            context=context,
            spec=spec,
            decision_classification=decision_classification,
        )

    return check_permissions
