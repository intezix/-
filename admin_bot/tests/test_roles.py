from __future__ import annotations

import pytest

from admin_bot.services.role_service import RoleService


def test_can_view_raw_payments() -> None:
    assert RoleService.can_view_raw_payments("owner") is True
    assert RoleService.can_view_raw_payments("admin") is True
    assert RoleService.can_view_raw_payments("support") is False
    assert RoleService.can_view_raw_payments("viewer") is False


def test_permissions_helpers() -> None:
    assert RoleService.can_manage_roles("owner") is True
    assert RoleService.can_manage_roles("admin") is False

