"""Tests for TemplateRegistry and TemplateInfo."""

import pytest

from atboffice.core.templates import TemplateInfo, TemplateRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure clean registry state before and after each test."""
    TemplateRegistry.reset_instance()
    yield
    TemplateRegistry.reset_instance()


def test_template_info_creation():
    """Verify TemplateInfo dataclass initialization with default and custom values."""
    tpl = TemplateInfo(
        id="sample_doc",
        name="Sample Document",
        app="quire",
        category="General",
        icon="📝",
        description="A sample document template",
    )
    assert tpl.id == "sample_doc"
    assert tpl.name == "Sample Document"
    assert tpl.app == "quire"
    assert tpl.category == "General"
    assert tpl.icon == "📝"
    assert tpl.description == "A sample document template"
    assert tpl.builder is None
    assert tpl.sample_path is None


def test_template_registry_singleton():
    """Verify singleton pattern behavior of TemplateRegistry."""
    reg1 = TemplateRegistry.get_instance()
    reg2 = TemplateRegistry.get_instance()
    assert reg1 is reg2

    TemplateRegistry.reset_instance()
    reg3 = TemplateRegistry.get_instance()
    assert reg3 is not reg1


def test_custom_template_registration_and_lookup():
    """Verify registering, retrieving, and unregistering templates."""
    reg = TemplateRegistry.get_instance()
    reg.clear()

    tpl = TemplateInfo(
        id="invoice_custom",
        name="Custom Invoice",
        app="ledger",
        category="Financial",
        icon="💰",
    )
    reg.register(tpl)

    # Lookup without app filter
    found = reg.get("invoice_custom")
    assert found is not None
    assert found.name == "Custom Invoice"

    # Lookup with matching app filter
    found_app = reg.get("invoice_custom", app="ledger")
    assert found_app is not None
    assert found_app.id == "invoice_custom"

    # Lookup with mismatched app filter
    assert reg.get("invoice_custom", app="quire") is None

    # Unregister
    assert reg.unregister("invoice_custom", app="ledger") is True
    assert reg.get("invoice_custom") is None
    assert reg.unregister("invoice_custom") is False


def test_template_filtering_by_app_and_category():
    """Verify listing templates filtered by app and category."""
    reg = TemplateRegistry.get_instance()
    reg.clear()

    reg.register(TemplateInfo(id="q1", name="Q1", app="quire", category="Letters"))
    reg.register(TemplateInfo(id="q2", name="Q2", app="quire", category="Reports"))
    reg.register(TemplateInfo(id="l1", name="L1", app="ledger", category="Financial"))
    reg.register(TemplateInfo(id="p1", name="P1", app="lectern", category="Business"))

    assert len(reg.list_templates()) == 4
    assert len(reg.list_templates(app="quire")) == 2
    assert len(reg.list_templates(app="ledger")) == 1
    assert len(reg.list_templates(app="lectern")) == 1

    assert len(reg.list_templates(category="Letters")) == 1
    assert len(reg.list_templates(app="quire", category="Reports")) == 1
    assert len(reg.list_templates(app="ledger", category="Reports")) == 0

    quire_cats = reg.list_categories(app="quire")
    assert "Letters" in quire_cats
    assert "Reports" in quire_cats
    assert "Financial" not in quire_cats


def test_builtin_templates_registration():
    """Verify all 22 built-in templates from .vibeoffice are registered."""
    reg = TemplateRegistry.get_instance()
    quire_templates = reg.list_templates(app="quire")
    ledger_templates = reg.list_templates(app="ledger")
    lectern_templates = reg.list_templates(app="lectern")

    assert len(quire_templates) == 10
    assert len(ledger_templates) == 8
    assert len(lectern_templates) == 4

    expected_quire_ids = {
        "letter", "memo", "fax", "resume", "report",
        "agenda", "minutes", "todo", "flyer", "recipe",
    }
    expected_ledger_ids = {
        "loan", "expense", "invoice", "timecard",
        "budget", "tasks", "shopping", "schedule",
    }
    expected_lectern_ids = {
        "status", "meeting", "lesson", "event",
    }

    assert {t.id for t in quire_templates} == expected_quire_ids
    assert {t.id for t in ledger_templates} == expected_ledger_ids
    assert {t.id for t in lectern_templates} == expected_lectern_ids

    # Every template should have a non-empty name, category, and default icon
    for tpl in quire_templates + ledger_templates + lectern_templates:
        assert bool(tpl.name)
        assert bool(tpl.category)
        assert bool(tpl.icon)
