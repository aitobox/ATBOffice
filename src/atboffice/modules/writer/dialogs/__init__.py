"""Dialogs package for Quire writer."""

from atboffice.modules.writer.dialogs.bullets_numbering import BulletsNumberingDialog
from atboffice.modules.writer.dialogs.font_dialog import FontDialog
from atboffice.modules.writer.dialogs.mailmerge_wizard import (
    AddressListDialog,
    InsertMergeFieldDialog,
    MailMergeRecipientsDialog,
    MailMergeWizardDialog,
)
from atboffice.modules.writer.dialogs.page_setup import PageSetupDialog
from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog

__all__ = [
    "AddressListDialog",
    "BulletsNumberingDialog",
    "FontDialog",
    "InsertMergeFieldDialog",
    "MailMergeRecipientsDialog",
    "MailMergeWizardDialog",
    "PageSetupDialog",
    "ParagraphDialog",
]
