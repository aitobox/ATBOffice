"""Reusable cross-module UI dialogs for ATBOffice."""

from atboffice.ui.dialogs.about_dialog import AboutDialog
from atboffice.ui.dialogs.document_properties_dialog import (
    DocumentMetadata,
    DocumentPropertiesDialog,
)
from atboffice.ui.dialogs.find_replace_dialog import FindReplaceDialog
from atboffice.ui.dialogs.in_app_save_as_dialog import (
    InAppSaveAsDialog,
    SecurityOptionsDialog,
)
from atboffice.ui.dialogs.license_dialog import LicenseDialog
from atboffice.ui.dialogs.options_dialog import OptionsDialog
from atboffice.ui.dialogs.templates_dialog import TemplatesDialog
from atboffice.ui.dialogs.theme_dialog import (
    SuiteThemeDialog,
    ThemeDialog,
    ThemesDialog,
)
from atboffice.ui.dialogs.update_dialog import UpdateDialog

__all__ = [
    "AboutDialog",
    "DocumentMetadata",
    "DocumentPropertiesDialog",
    "FindReplaceDialog",
    "InAppSaveAsDialog",
    "LicenseDialog",
    "OptionsDialog",
    "SecurityOptionsDialog",
    "SuiteThemeDialog",
    "TemplatesDialog",
    "ThemeDialog",
    "ThemesDialog",
    "UpdateDialog",
]

