"""Dialogs package for Quire writer."""

from atboffice.modules.writer.dialogs.borders_shading import BordersShadingDialog
from atboffice.modules.writer.dialogs.break_dialog import BreakDialog
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
from atboffice.modules.writer.dialogs.page_formatting_dialogs import (
    ChangeCaseDialog,
    DocumentThemeDialog,
    DropCapDialog,
    PageNumbersDialog,
    TextDirectionDialog,
    WatermarkDialog,
)
from atboffice.modules.writer.dialogs.page_setup import PageSetupDialog
from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog
from atboffice.modules.writer.dialogs.reference_dialogs import (
    BookmarkDialog,
    CaptionDialog,
    CrossRefDialog,
    DateTimeDialog,
    FieldDialog,
    FootnoteDialog,
    HyperlinkDialog,
    IndexTablesDialog,
    SymbolDialog,
)
from atboffice.modules.writer.dialogs.table_dialogs import (
    DeleteCellsDialog,
    InsertCellsDialog,
    SplitCellsDialog,
    TableAutoFormatDialog,
    TableFormulaDialog,
    TableSortDialog,
)
from atboffice.modules.writer.dialogs.table_properties import TablePropertiesDialog
from atboffice.modules.writer.dialogs.tabs_dialog import TabsDialog
from atboffice.modules.writer.dialogs.tools_dialogs import (
    AutoCorrectDialog,
    AutoSummarizeDialog,
    CustomizeDialog,
    EnvelopesLabelsDialog,
    HyphenationDialog,
    LetterWizardDialog,
    QuireOptionsDialog,
)
from atboffice.modules.writer.dialogs.word_count_dlg import (
    WordCountDialog,
    WordCountStats,
    calculate_document_statistics,
    count_text_statistics,
)

__all__ = [
    "AddressListDialog",
    "AutoCorrectDialog",
    "AutoSummarizeDialog",
    "BookmarkDialog",
    "BordersShadingDialog",
    "BreakDialog",
    "BulletsNumberingDialog",
    "CaptionDialog",
    "ChangeCaseDialog",
    "ColumnsDialog",
    "CrossRefDialog",
    "CustomizeDialog",
    "CustomizeListDialog",
    "DateTimeDialog",
    "DeleteCellsDialog",
    "DocumentThemeDialog",
    "DropCapDialog",
    "EnvelopesLabelsDialog",
    "FieldDialog",
    "FontDialog",
    "FootnoteDialog",
    "HyperlinkDialog",
    "HyphenationDialog",
    "IndexTablesDialog",
    "InsertCellsDialog",
    "InsertMergeFieldDialog",
    "InsertTableDialog",
    "LetterWizardDialog",
    "MailMergeRecipientsDialog",
    "MailMergeWizardDialog",
    "PageNumbersDialog",
    "PageSetupDialog",
    "ParagraphDialog",
    "QuireOptionsDialog",
    "SplitCellsDialog",
    "SymbolDialog",
    "TableAutoFormatDialog",
    "TableFormulaDialog",
    "TablePropertiesDialog",
    "TableSortDialog",
    "TabsDialog",
    "TextDirectionDialog",
    "WatermarkDialog",
    "WordCountDialog",
    "WordCountStats",
    "calculate_document_statistics",
    "count_text_statistics",
]
