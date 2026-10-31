"""Dialogs package for Quire writer."""

from atboffice.modules.writer.dialogs.borders_shading import BordersShadingDialog
from atboffice.modules.writer.dialogs.bullets_numbering import BulletsNumberingDialog
from atboffice.modules.writer.dialogs.columns_dialog import ColumnsDialog
from atboffice.modules.writer.dialogs.customize_list_dialog import CustomizeListDialog
from atboffice.modules.writer.dialogs.font_dialog import FontDialog
from atboffice.modules.writer.dialogs.insert_table import InsertTableDialog
from atboffice.modules.writer.dialogs.mailmerge_wizard import (
    AddressListDialog,
    InsertMergeFieldDialog,
    MailMergeRecipientsDialog,
    MailMergeWizardDialog,
)
from atboffice.modules.writer.dialogs.page_setup import PageSetupDialog
from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog
from atboffice.modules.writer.dialogs.table_properties import TablePropertiesDialog
from atboffice.modules.writer.dialogs.tabs_dialog import TabsDialog

__all__ = [
    "AddressListDialog",
    "BordersShadingDialog",
    "BulletsNumberingDialog",
    "ColumnsDialog",
    "CustomizeListDialog",
    "FontDialog",
    "InsertMergeFieldDialog",
    "InsertTableDialog",
    "MailMergeRecipientsDialog",
    "MailMergeWizardDialog",
    "PageSetupDialog",
    "ParagraphDialog",
    "TablePropertiesDialog",
    "TabsDialog",
]
