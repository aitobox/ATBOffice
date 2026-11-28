"""Office 2003 classic Ledger Constrained Solver (规划求解) dialogs."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import get_i18n_manager, safe_tr
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.calc.solver import (
    ConstraintOp,
    SolverConstraint,
    SolverGoal,
    SolverMethod,
    SolverOptions,
    SolverParams,
    SolverResult,
    apply_solver_solution,
    generate_answer_report,
    generate_limits_report,
    generate_sensitivity_report,
    load_solver_model,
    save_solver_model,
    solve_model,
)
from atboffice.ui.styles.luna_2003 import theme_tokens, ui_font

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

logger = logging.getLogger(__name__)

_UNARY_CONSTRAINT_OPS: frozenset[ConstraintOp] = frozenset(("int", "bin", "dif"))

_METHOD_ITEMS: tuple[tuple[SolverMethod, str], ...] = (
    ("simplex_lp", "单纯形 LP"),
    ("grg_nonlinear", "GRG 非线性"),
    ("evolutionary", "演化"),
)

_CONSTRAINT_OP_ITEMS: tuple[tuple[ConstraintOp, str], ...] = (
    ("<=", "<="),
    ("=", "="),
    (">=", ">="),
    ("int", "整数 (int)"),
    ("bin", "二进制 (bin)"),
    ("dif", "全部不同 (dif)"),
)


def _format_number(value: float) -> str:
    """Format a floating-point solver metric concisely for UI labels."""
    if abs(value - round(value)) < 1e-12 and abs(value) < 1e15:
        return str(int(round(value)))
    return f"{value:.6g}"


def _format_constraint_display(constraint: SolverConstraint) -> str:
    """Render a constraint into human-readable localized text."""
    if constraint.op == "int":
        return f"{constraint.lhs_ref} = {safe_tr('整数 (int)')}"
    if constraint.op == "bin":
        return f"{constraint.lhs_ref} = {safe_tr('二进制 (bin)')}"
    if constraint.op == "dif":
        return f"{constraint.lhs_ref} = {safe_tr('全部不同 (dif)')}"
    return f"{constraint.lhs_ref} {constraint.op} {constraint.rhs}"


def _apply_dialog_chrome(dialog: QDialog) -> None:
    """Apply consistent Luna 2003 font and window flags without hardcoding colors."""
    dialog.setFont(ui_font())
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)


class _LocaleAwareDialog(QDialog):
    """Base dialog that automatically updates localized text on locale changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._locale_connected = False
        _apply_dialog_chrome(self)
        self._connect_locale_signal()

    def _connect_locale_signal(self) -> None:
        if not self._locale_connected:
            get_i18n_manager().locale_changed.connect(self._on_locale_changed)
            self._locale_connected = True

    def _disconnect_locale_signal(self) -> None:
        if self._locale_connected:
            try:
                get_i18n_manager().locale_changed.disconnect(self._on_locale_changed)
            except (RuntimeError, TypeError):
                pass
            self._locale_connected = False

    def _on_locale_changed(self, _locale: str) -> None:
        retranslate = getattr(self, "retranslate_ui", None)
        if callable(retranslate):
            retranslate()

    def done(self, result: int) -> None:
        self._disconnect_locale_signal()
        super().done(result)

    def closeEvent(self, event: Any) -> None:
        self._disconnect_locale_signal()
        super().closeEvent(event)


class _SolverWorker(QThread):
    """Background worker thread running ``solve_model`` off the Qt UI thread."""

    progress_updated = Signal(int, float)
    solve_finished = Signal(object)
    solve_failed = Signal(str)

    def __init__(
        self,
        workbook: WorkbookModel,
        params: SolverParams,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.params = params
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        """Signal the solver loop to abort cleanly."""
        self._cancel_event.set()
        self.requestInterruption()

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set() or self.isInterruptionRequested()

    def _on_progress(self, iteration: int, objective: float) -> None:
        self.progress_updated.emit(int(iteration), float(objective))

    def run(self) -> None:
        try:
            result = solve_model(
                self.workbook,
                self.params,
                cancel_check=self._is_cancelled,
                progress_cb=self._on_progress,
            )
            self.solve_finished.emit(result)
        except Exception as exc:
            logger.exception("Solver worker failed unexpectedly")
            self.solve_failed.emit(str(exc))


class AddConstraintDialog(_LocaleAwareDialog):
    """Dialog for adding or editing a single solver constraint."""

    constraint_added = Signal(object)

    def __init__(
        self,
        constraint: SolverConstraint | None = None,
        edit_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SolverAddConstraintDialog")
        self._edit_mode = edit_mode
        self._initial_constraint = constraint

        self._init_ui()
        if constraint is not None:
            self.lhs_edit.setText(constraint.lhs_ref)
            op_idx = self.op_combo.findData(constraint.op)
            if op_idx >= 0:
                self.op_combo.setCurrentIndex(op_idx)
            self.rhs_edit.setText(constraint.rhs)
        self._on_op_changed()
        self.retranslate_ui()

    def _init_ui(self) -> None:
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self.lhs_label = QLabel(self)
        self.lhs_edit = QLineEdit(self)
        self.lhs_edit.setObjectName("SolverConstraintLhsEdit")
        self.lhs_label.setBuddy(self.lhs_edit)

        self.op_label = QLabel(self)
        self.op_combo = QComboBox(self)
        self.op_combo.setObjectName("SolverConstraintOpCombo")
        for op_key, _label in _CONSTRAINT_OP_ITEMS:
            self.op_combo.addItem("", op_key)
        self.op_combo.currentIndexChanged.connect(self._on_op_changed)

        self.rhs_label = QLabel(self)
        self.rhs_edit = QLineEdit(self)
        self.rhs_edit.setObjectName("SolverConstraintRhsEdit")
        self.rhs_label.setBuddy(self.rhs_edit)

        grid.addWidget(self.lhs_label, 0, 0)
        grid.addWidget(self.op_label, 0, 1)
        grid.addWidget(self.rhs_label, 0, 2)
        grid.addWidget(self.lhs_edit, 1, 0)
        grid.addWidget(self.op_combo, 1, 1)
        grid.addWidget(self.rhs_edit, 1, 2)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.ok_btn = QPushButton(self)
        self.ok_btn.setObjectName("SolverConstraintOkBtn")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(self.ok_btn)

        self.add_btn = QPushButton(self)
        self.add_btn.setObjectName("SolverConstraintAddMoreBtn")
        self.add_btn.clicked.connect(self._on_add_more)
        self.add_btn.setVisible(not self._edit_mode)
        btn_row.addWidget(self.add_btn)

        self.cancel_btn = QPushButton(self)
        self.cancel_btn.setObjectName("SolverConstraintCancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    def _current_op(self) -> ConstraintOp:
        data = self.op_combo.currentData()
        return data if isinstance(data, str) else "<="  # type: ignore[return-value]

    def _on_op_changed(self) -> None:
        op = self._current_op()
        is_unary = op in _UNARY_CONSTRAINT_OPS
        self.rhs_edit.setEnabled(not is_unary)
        if is_unary:
            self.rhs_edit.clear()

    def _build_validated_constraint(self) -> SolverConstraint | None:
        title = safe_tr("更改约束") if self._edit_mode else safe_tr("添加约束")
        lhs = self.lhs_edit.text().strip()
        if not lhs:
            QMessageBox.warning(self, title, safe_tr("请输入约束单元格引用。"))
            self.lhs_edit.setFocus()
            return None

        op = self._current_op()
        rhs = ""
        if op not in _UNARY_CONSTRAINT_OPS:
            rhs = self.rhs_edit.text().strip()
            if not rhs:
                QMessageBox.warning(self, title, safe_tr("请输入约束值。"))
                self.rhs_edit.setFocus()
                return None

        return SolverConstraint(lhs_ref=lhs, op=op, rhs=rhs)

    def _on_ok(self) -> None:
        constraint = self._build_validated_constraint()
        if constraint is None:
            return
        self._result_constraint = constraint
        self.accept()

    def _on_add_more(self) -> None:
        constraint = self._build_validated_constraint()
        if constraint is None:
            return
        self.constraint_added.emit(constraint)
        self.lhs_edit.clear()
        self.rhs_edit.clear()
        self.lhs_edit.setFocus()

    def get_constraint(self) -> SolverConstraint:
        """Return the constructed ``SolverConstraint``."""
        if hasattr(self, "_result_constraint"):
            return self._result_constraint
        op = self._current_op()
        rhs = "" if op in _UNARY_CONSTRAINT_OPS else self.rhs_edit.text().strip()
        return SolverConstraint(lhs_ref=self.lhs_edit.text().strip(), op=op, rhs=rhs)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("更改约束") if self._edit_mode else safe_tr("添加约束"))
        self.lhs_label.setText(safe_tr("单元格引用(&C):"))
        self.op_label.setText(safe_tr("运算符:"))
        self.rhs_label.setText(safe_tr("约束值(&R):"))
        for idx, (_op_key, raw_label) in enumerate(_CONSTRAINT_OP_ITEMS):
            label = raw_label if raw_label in ("<=", "=", ">=") else safe_tr(raw_label)
            self.op_combo.setItemText(idx, label)
        self.ok_btn.setText(safe_tr("确定"))
        self.add_btn.setText(safe_tr("添加"))
        self.cancel_btn.setText(safe_tr("取消"))


class SolverOptionsDialog(_LocaleAwareDialog):
    """Dialog for configuring solver iteration, precision, and EA parameters."""

    def __init__(
        self,
        options: SolverOptions | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SolverOptionsDialog")
        self._options = replace(options) if options is not None else SolverOptions()

        self._init_ui()
        self._populate_from_options(self._options)
        self.retranslate_ui()

    def _init_ui(self) -> None:
        self.setFixedWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.max_time_label = QLabel(self)
        self.max_time_spin = QDoubleSpinBox(self)
        self.max_time_spin.setObjectName("SolverMaxTimeSpin")
        self.max_time_spin.setRange(1.0, 36000.0)
        self.max_time_spin.setDecimals(1)
        self.max_time_spin.setSingleStep(5.0)
        self.max_time_label.setBuddy(self.max_time_spin)

        self.max_iter_label = QLabel(self)
        self.max_iter_spin = QSpinBox(self)
        self.max_iter_spin.setObjectName("SolverMaxIterSpin")
        self.max_iter_spin.setRange(1, 100000)
        self.max_iter_spin.setSingleStep(50)
        self.max_iter_label.setBuddy(self.max_iter_spin)

        self.precision_label = QLabel(self)
        self.precision_edit = QLineEdit(self)
        self.precision_edit.setObjectName("SolverPrecisionEdit")
        self.precision_label.setBuddy(self.precision_edit)

        self.int_opt_label = QLabel(self)
        self.int_opt_spin = QDoubleSpinBox(self)
        self.int_opt_spin.setObjectName("SolverIntOptSpin")
        self.int_opt_spin.setRange(0.0, 1.0)
        self.int_opt_spin.setDecimals(4)
        self.int_opt_spin.setSingleStep(0.01)
        self.int_opt_label.setBuddy(self.int_opt_spin)

        self.pop_size_label = QLabel(self)
        self.pop_size_spin = QSpinBox(self)
        self.pop_size_spin.setObjectName("SolverPopSizeSpin")
        self.pop_size_spin.setRange(5, 1000)
        self.pop_size_spin.setSingleStep(10)
        self.pop_size_label.setBuddy(self.pop_size_spin)

        self.seed_label = QLabel(self)
        self.seed_spin = QSpinBox(self)
        self.seed_spin.setObjectName("SolverSeedSpin")
        self.seed_spin.setRange(0, 2147483647)
        self.seed_label.setBuddy(self.seed_spin)

        rows = (
            (self.max_time_label, self.max_time_spin),
            (self.max_iter_label, self.max_iter_spin),
            (self.precision_label, self.precision_edit),
            (self.int_opt_label, self.int_opt_spin),
            (self.pop_size_label, self.pop_size_spin),
            (self.seed_label, self.seed_spin),
        )
        for idx, (lbl, widget) in enumerate(rows):
            grid.addWidget(lbl, idx, 0)
            grid.addWidget(widget, idx, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self.defaults_btn = QPushButton(self)
        self.defaults_btn.setObjectName("SolverOptionsDefaultsBtn")
        self.defaults_btn.clicked.connect(self._on_restore_defaults)
        btn_row.addWidget(self.defaults_btn)
        btn_row.addStretch(1)

        self.ok_btn = QPushButton(self)
        self.ok_btn.setObjectName("SolverOptionsOkBtn")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton(self)
        self.cancel_btn.setObjectName("SolverOptionsCancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    def _populate_from_options(self, options: SolverOptions) -> None:
        self.max_time_spin.setValue(float(options.max_time_sec))
        self.max_iter_spin.setValue(int(options.max_iterations))
        self.precision_edit.setText(str(options.precision))
        self.int_opt_spin.setValue(float(options.integer_optimality))
        self.pop_size_spin.setValue(int(options.population_size))
        self.seed_spin.setValue(int(options.random_seed))

    def _on_restore_defaults(self) -> None:
        self._populate_from_options(SolverOptions())

    def _on_ok(self) -> None:
        try:
            precision = float(self.precision_edit.text().strip())
        except (ValueError, TypeError):
            precision = -1.0
        if precision <= 0.0:
            QMessageBox.warning(
                self,
                safe_tr("规划求解选项"),
                safe_tr("约束精度必须是大于 0 的数字。"),
            )
            self.precision_edit.setFocus()
            return

        self._options = SolverOptions(
            max_iterations=self.max_iter_spin.value(),
            max_time_sec=self.max_time_spin.value(),
            precision=precision,
            integer_optimality=self.int_opt_spin.value(),
            population_size=self.pop_size_spin.value(),
            random_seed=self.seed_spin.value(),
        )
        self.accept()

    def get_options(self) -> SolverOptions:
        """Return the configured ``SolverOptions``."""
        return replace(self._options)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("规划求解选项"))
        self.max_time_label.setText(safe_tr("最长时间(秒)(&T):"))
        self.max_iter_label.setText(safe_tr("最大迭代次数(&I):"))
        self.precision_label.setText(safe_tr("约束精度(&P):"))
        self.int_opt_label.setText(safe_tr("整数最优性容差(&O):"))
        self.pop_size_label.setText(safe_tr("种群大小(&S):"))
        self.seed_label.setText(safe_tr("随机种子(&R):"))
        self.defaults_btn.setText(safe_tr("恢复默认值(&D)"))
        self.ok_btn.setText(safe_tr("确定"))
        self.cancel_btn.setText(safe_tr("取消"))


class SolverResultsDialog(_LocaleAwareDialog):
    """Dialog displaying solver outcome and letting user keep/restore & report."""

    def __init__(
        self,
        solver_result: SolverResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SolverResultsDialog")
        self.solver_result = solver_result

        self._init_ui()
        self.retranslate_ui()

    def _init_ui(self) -> None:
        self.setMinimumWidth(420)
        tok = theme_tokens()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("SolverResultsStatusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setFont(ui_font(bold=True))
        layout.addWidget(self.status_label)

        self.summary_group = QGroupBox(self)
        summary_layout = QVBoxLayout(self.summary_group)
        summary_layout.setContentsMargins(10, 10, 10, 10)
        self.summary_label = QLabel(self.summary_group)
        self.summary_label.setObjectName("SolverResultsSummaryLabel")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary_label.setStyleSheet(
            f"background-color: {tok.menu_face}; border: 1px solid {tok.tb_border}; padding: 6px;"
        )
        summary_layout.addWidget(self.summary_label)
        layout.addWidget(self.summary_group)

        self.choice_group = QGroupBox(self)
        choice_layout = QVBoxLayout(self.choice_group)
        choice_layout.setContentsMargins(10, 10, 10, 10)
        choice_layout.setSpacing(6)

        self.keep_radio = QRadioButton(self.choice_group)
        self.keep_radio.setObjectName("SolverResultsKeepRadio")
        self.restore_radio = QRadioButton(self.choice_group)
        self.restore_radio.setObjectName("SolverResultsRestoreRadio")

        has_solution = bool(self.solver_result.solution_values)
        self.keep_radio.setEnabled(has_solution)
        if has_solution and self.solver_result.success:
            self.keep_radio.setChecked(True)
        else:
            self.restore_radio.setChecked(True)

        choice_layout.addWidget(self.keep_radio)
        choice_layout.addWidget(self.restore_radio)
        layout.addWidget(self.choice_group)

        self.reports_group = QGroupBox(self)
        reports_layout = QVBoxLayout(self.reports_group)
        reports_layout.setContentsMargins(10, 10, 10, 10)
        reports_layout.setSpacing(6)

        self.report_chk = QCheckBox(self.reports_group)
        self.report_chk.setObjectName("SolverResultsReportCheck")
        self.report_checkbox = self.report_chk
        self.sensitivity_report_chk = QCheckBox(self.reports_group)
        self.sensitivity_report_chk.setObjectName("SolverResultsSensitivityCheck")
        self.limits_report_chk = QCheckBox(self.reports_group)
        self.limits_report_chk.setObjectName("SolverResultsLimitsCheck")

        reports_layout.addWidget(self.report_chk)
        reports_layout.addWidget(self.sensitivity_report_chk)
        reports_layout.addWidget(self.limits_report_chk)
        layout.addWidget(self.reports_group)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.ok_btn = QPushButton(self)
        self.ok_btn.setObjectName("SolverResultsOkBtn")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton(self)
        self.cancel_btn.setObjectName("SolverResultsCancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    @property
    def keep_solution(self) -> bool:
        """Return True if accepted with Keep Solver Solution selected."""
        return self.result() == QDialog.DialogCode.Accepted and self.keep_radio.isChecked()

    @property
    def generate_report(self) -> bool:
        """Return True if accepted with Answer Report requested."""
        return self.result() == QDialog.DialogCode.Accepted and self.report_chk.isChecked()

    @property
    def generate_sensitivity(self) -> bool:
        """Return True if accepted with Sensitivity Report requested."""
        return (
            self.result() == QDialog.DialogCode.Accepted and self.sensitivity_report_chk.isChecked()
        )

    @property
    def generate_limits(self) -> bool:
        """Return True if accepted with Limits Report requested."""
        return self.result() == QDialog.DialogCode.Accepted and self.limits_report_chk.isChecked()

    @property
    def selected_reports(self) -> list[str]:
        """Return ordered report kinds selected on accept."""
        if self.result() != QDialog.DialogCode.Accepted:
            return []
        out: list[str] = []
        if self.report_chk.isChecked():
            out.append("answer")
        if self.sensitivity_report_chk.isChecked():
            out.append("sensitivity")
        if self.limits_report_chk.isChecked():
            out.append("limits")
        return out

    def _update_summary_text(self) -> None:
        res = self.solver_result
        self.status_label.setText(res.message or safe_tr("规划求解完成。"))
        self.summary_label.setText(
            safe_tr(
                "目标单元格: {0} | 初值: {1} -> 终值: {2} | 迭代: {3} | 耗时: {4}s",
                res.objective_ref,
                _format_number(res.initial_objective),
                _format_number(res.final_objective),
                res.iterations,
                f"{res.elapsed_sec:.3f}",
            )
        )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("规划求解结果"))
        self.summary_group.setTitle(safe_tr("结果摘要"))
        self.choice_group.setTitle(safe_tr("求解结果处理"))
        self.keep_radio.setText(safe_tr("保留规划求解的解(&K)"))
        self.restore_radio.setText(safe_tr("恢复原值(&R)"))
        self.reports_group.setTitle(safe_tr("报告"))
        self.report_chk.setText(safe_tr("生成运算结果报告(&A)"))
        self.sensitivity_report_chk.setText(safe_tr("生成灵敏度报告(&S)"))
        self.limits_report_chk.setText(safe_tr("生成极限值报告(&L)"))
        self.ok_btn.setText(safe_tr("确定"))
        self.cancel_btn.setText(safe_tr("取消"))
        self._update_summary_text()


class SolverParametersDialog(_LocaleAwareDialog):
    """Office 2003 classic Solver Parameters (规划求解参数) dialog."""

    def __init__(
        self,
        workbook: WorkbookModel | None,
        current_sheet: SheetDataModel | None,
        initial_r: int = 0,
        initial_c: int = 0,
        apply_callback: Callable[[SolverParams, SolverResult, bool], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SolverParametersDialog")
        self.workbook = workbook
        self.current_sheet = current_sheet
        self.initial_r = initial_r
        self.initial_c = initial_c
        self.apply_callback = apply_callback

        self.created_report_sheet: str | None = None
        self.created_report_sheets: list[str] = []
        self.last_result: SolverResult | None = None
        self._constraints: list[SolverConstraint] = []
        self._options = SolverOptions()
        self._worker: _SolverWorker | None = None
        self._solving = False
        self._active_params: SolverParams | None = None

        self._init_ui()
        self._load_initial_model()
        self.retranslate_ui()
        self._update_action_states()

    def _init_ui(self) -> None:
        self.setMinimumWidth(520)
        tok = theme_tokens()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Objective row
        obj_layout = QGridLayout()
        obj_layout.setHorizontalSpacing(8)
        obj_layout.setVerticalSpacing(6)

        self.objective_label = QLabel(self)
        self.objective_edit = QLineEdit(self)
        self.objective_edit.setObjectName("SolverObjectiveEdit")
        self.objective_label.setBuddy(self.objective_edit)
        obj_layout.addWidget(self.objective_label, 0, 0)
        obj_layout.addWidget(self.objective_edit, 0, 1)

        # Goal row (Max / Min / Value Of)
        self.goal_label = QLabel(self)
        goal_row = QHBoxLayout()
        goal_row.setSpacing(10)

        self.goal_btn_group = QButtonGroup(self)
        self.radio_max = QRadioButton(self)
        self.radio_max.setObjectName("SolverGoalMaxRadio")
        self.radio_min = QRadioButton(self)
        self.radio_min.setObjectName("SolverGoalMinRadio")
        self.radio_value_of = QRadioButton(self)
        self.radio_value_of.setObjectName("SolverGoalValueRadio")
        self.goal_btn_group.addButton(self.radio_max)
        self.goal_btn_group.addButton(self.radio_min)
        self.goal_btn_group.addButton(self.radio_value_of)
        self.radio_max.setChecked(True)

        self.target_value_edit = QLineEdit(self)
        self.target_value_edit.setObjectName("SolverTargetValueEdit")
        self.target_value_edit.setFixedWidth(96)
        self.target_value_edit.setEnabled(False)
        self.radio_value_of.toggled.connect(self._on_goal_toggled)

        goal_row.addWidget(self.radio_max)
        goal_row.addWidget(self.radio_min)
        goal_row.addWidget(self.radio_value_of)
        goal_row.addWidget(self.target_value_edit)
        goal_row.addStretch(1)

        obj_layout.addWidget(self.goal_label, 1, 0)
        obj_layout.addLayout(goal_row, 1, 1)

        # Changing variable cells row
        self.variables_label = QLabel(self)
        self.variables_edit = QLineEdit(self)
        self.variables_edit.setObjectName("SolverVariablesEdit")
        self.variables_label.setBuddy(self.variables_edit)
        obj_layout.addWidget(self.variables_label, 2, 0)
        obj_layout.addWidget(self.variables_edit, 2, 1)

        obj_layout.setColumnStretch(1, 1)
        main_layout.addLayout(obj_layout)

        # Constraints list + side action buttons
        self.constraints_label = QLabel(self)
        main_layout.addWidget(self.constraints_label)

        constraints_row = QHBoxLayout()
        constraints_row.setSpacing(10)

        self.constraints_list = QListWidget(self)
        self.constraints_list.setObjectName("SolverConstraintsList")
        self.constraints_list.setMinimumHeight(140)
        self.constraints_list.setStyleSheet(
            f"QListWidget {{ background-color: {tok.menu_face}; "
            f"border: 1px solid {tok.tb_border}; }}"
        )
        self.constraints_list.currentRowChanged.connect(self._update_action_states)
        self.constraints_list.itemDoubleClicked.connect(self._on_edit_constraint)
        constraints_row.addWidget(self.constraints_list, 1)

        c_btn_col = QVBoxLayout()
        c_btn_col.setSpacing(6)

        self.add_constraint_btn = QPushButton(self)
        self.add_constraint_btn.setObjectName("SolverAddConstraintBtn")
        self.add_constraint_btn.clicked.connect(self._on_add_constraint)
        c_btn_col.addWidget(self.add_constraint_btn)

        self.edit_constraint_btn = QPushButton(self)
        self.edit_constraint_btn.setObjectName("SolverEditConstraintBtn")
        self.edit_constraint_btn.clicked.connect(self._on_edit_constraint)
        c_btn_col.addWidget(self.edit_constraint_btn)

        self.delete_constraint_btn = QPushButton(self)
        self.delete_constraint_btn.setObjectName("SolverDeleteConstraintBtn")
        self.delete_constraint_btn.clicked.connect(self._on_delete_constraint)
        c_btn_col.addWidget(self.delete_constraint_btn)

        self.reset_all_btn = QPushButton(self)
        self.reset_all_btn.setObjectName("SolverResetAllBtn")
        self.reset_all_btn.clicked.connect(self._on_reset_all)
        c_btn_col.addWidget(self.reset_all_btn)

        c_btn_col.addStretch(1)
        constraints_row.addLayout(c_btn_col)
        main_layout.addLayout(constraints_row)

        # Non-negative checkbox
        self.non_negative_chk = QCheckBox(self)
        self.non_negative_chk.setObjectName("SolverNonNegativeCheck")
        self.non_negative_chk.setChecked(True)
        main_layout.addWidget(self.non_negative_chk)

        # Solving method row + Options button
        method_row = QHBoxLayout()
        method_row.setSpacing(8)

        self.method_label = QLabel(self)
        self.method_combo = QComboBox(self)
        self.method_combo.setObjectName("SolverMethodCombo")
        self.method_label.setBuddy(self.method_combo)
        for method_key, _raw_label in _METHOD_ITEMS:
            self.method_combo.addItem("", method_key)

        self.options_btn = QPushButton(self)
        self.options_btn.setObjectName("SolverOptionsBtn")
        self.options_btn.clicked.connect(self._on_options)

        method_row.addWidget(self.method_label)
        method_row.addWidget(self.method_combo, 1)
        method_row.addWidget(self.options_btn)
        main_layout.addLayout(method_row)

        # Background solve progress area
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("SolverProgressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("SolverStatusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"background-color: {tok.status_bg}; border: 1px solid {tok.status_sep}; padding: 4px;"
        )
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)

        # Bottom dialog buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.save_model_btn = QPushButton(self)
        self.save_model_btn.setObjectName("SolverSaveModelBtn")
        self.save_model_btn.clicked.connect(self._on_save_model)
        bottom_row.addWidget(self.save_model_btn)

        bottom_row.addStretch(1)

        self.cancel_btn = QPushButton(self)
        self.cancel_btn.setObjectName("SolverCancelSolveBtn")
        self.cancel_btn.clicked.connect(self._on_cancel_solve)
        self.cancel_btn.setVisible(False)
        bottom_row.addWidget(self.cancel_btn)

        self.solve_btn = QPushButton(self)
        self.solve_btn.setObjectName("SolverSolveBtn")
        self.solve_btn.setDefault(True)
        self.solve_btn.clicked.connect(self._on_solve)
        bottom_row.addWidget(self.solve_btn)

        self.close_btn = QPushButton(self)
        self.close_btn.setObjectName("SolverCloseBtn")
        self.close_btn.clicked.connect(self.reject)
        bottom_row.addWidget(self.close_btn)

        main_layout.addLayout(bottom_row)

    def _default_objective_ref(self) -> str:
        return cell_name(self.initial_r, self.initial_c, ra=True, ca=True)

    def _load_initial_model(self) -> None:
        loaded = load_solver_model(self.current_sheet) if self.current_sheet is not None else None
        if loaded is not None:
            self.apply_params(loaded)
        else:
            self.objective_edit.setText(self._default_objective_ref())

    def apply_params(self, params: SolverParams) -> None:
        """Populate all dialog widgets from an existing ``SolverParams`` object."""
        self.objective_edit.setText(params.objective_ref or self._default_objective_ref())
        if params.goal == "min":
            self.radio_min.setChecked(True)
        elif params.goal == "value_of":
            self.radio_value_of.setChecked(True)
            self.target_value_edit.setText(str(params.target_value))
        else:
            self.radio_max.setChecked(True)

        self.variables_edit.setText(params.variable_refs)
        self._constraints = [replace(c) for c in params.constraints]
        self._refresh_constraints_list()

        self.non_negative_chk.setChecked(bool(params.make_unconstrained_non_negative))
        method_idx = self.method_combo.findData(params.method)
        if method_idx >= 0:
            self.method_combo.setCurrentIndex(method_idx)
        self._options = replace(params.options)
        self._on_goal_toggled()
        self._update_action_states()

    def _refresh_constraints_list(self, select_row: int = -1) -> None:
        current = select_row if select_row >= 0 else self.constraints_list.currentRow()
        self.constraints_list.clear()
        for constraint in self._constraints:
            item = QListWidgetItem(_format_constraint_display(constraint))
            self.constraints_list.addItem(item)
        if 0 <= current < self.constraints_list.count():
            self.constraints_list.setCurrentRow(current)

    def _on_goal_toggled(self) -> None:
        is_val = self.radio_value_of.isChecked()
        self.target_value_edit.setEnabled(is_val and not self._is_solving())
        if is_val and not self.target_value_edit.text().strip():
            self.target_value_edit.setText("0")

    def _current_goal(self) -> SolverGoal:
        if self.radio_min.isChecked():
            return "min"
        if self.radio_value_of.isChecked():
            return "value_of"
        return "max"

    def _current_method(self) -> SolverMethod:
        data = self.method_combo.currentData()
        return data if isinstance(data, str) else "simplex_lp"  # type: ignore[return-value]

    def _default_sheet_name(self) -> str:
        if self.current_sheet is not None and getattr(self.current_sheet, "name", ""):
            return str(self.current_sheet.name)
        if self.workbook is not None and getattr(self.workbook, "sheets", None):
            return str(self.workbook.sheets[0].name)
        return "Sheet1"

    def build_params(self) -> SolverParams:
        """Assemble a ``SolverParams`` dataclass from current widget values."""
        target_value = 0.0
        if self.radio_value_of.isChecked():
            raw_val = self.target_value_edit.text().strip()
            target_value = float(raw_val) if raw_val else 0.0

        return SolverParams(
            objective_ref=self.objective_edit.text().strip(),
            goal=self._current_goal(),
            target_value=target_value,
            variable_refs=self.variables_edit.text().strip(),
            constraints=[replace(c) for c in self._constraints],
            make_unconstrained_non_negative=self.non_negative_chk.isChecked(),
            method=self._current_method(),
            default_sheet=self._default_sheet_name(),
            options=replace(self._options),
        )

    def _validate_inputs(self) -> SolverParams | None:
        title = safe_tr("规划求解参数")
        if self.workbook is None:
            QMessageBox.warning(self, title, safe_tr("未找到活动工作簿。"))
            return None

        if not self.objective_edit.text().strip():
            QMessageBox.warning(self, title, safe_tr("请输入目标单元格引用。"))
            self.objective_edit.setFocus()
            return None

        if self.radio_value_of.isChecked():
            raw_target = self.target_value_edit.text().strip()
            try:
                float(raw_target)
            except (ValueError, TypeError):
                QMessageBox.warning(self, title, safe_tr("请输入有效的数字目标值。"))
                self.target_value_edit.setFocus()
                return None

        if not self.variables_edit.text().strip():
            QMessageBox.warning(self, title, safe_tr("请输入可变单元格引用。"))
            self.variables_edit.setFocus()
            return None

        return self.build_params()

    def _is_solving(self) -> bool:
        return self._solving or (self._worker is not None and self._worker.isRunning())

    def _update_action_states(self) -> None:
        solving = self._is_solving()
        has_sel = 0 <= self.constraints_list.currentRow() < len(self._constraints)

        for widget in (
            self.objective_edit,
            self.radio_max,
            self.radio_min,
            self.radio_value_of,
            self.variables_edit,
            self.constraints_list,
            self.add_constraint_btn,
            self.reset_all_btn,
            self.non_negative_chk,
            self.method_combo,
            self.options_btn,
            self.save_model_btn,
            self.solve_btn,
        ):
            widget.setEnabled(not solving)

        self.target_value_edit.setEnabled(not solving and self.radio_value_of.isChecked())
        self.edit_constraint_btn.setEnabled(not solving and has_sel)
        self.delete_constraint_btn.setEnabled(not solving and has_sel)
        self.cancel_btn.setVisible(solving)
        self.cancel_btn.setEnabled(solving)
        self.progress_bar.setVisible(solving)

    def _set_status_message(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def _on_add_constraint(self) -> None:
        dlg = AddConstraintDialog(parent=self)
        dlg.constraint_added.connect(self._append_constraint)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._append_constraint(dlg.get_constraint())

    def _append_constraint(self, constraint: SolverConstraint) -> None:
        self._constraints.append(constraint)
        self._refresh_constraints_list(select_row=len(self._constraints) - 1)
        self._update_action_states()

    def _on_edit_constraint(self, *_args: Any) -> None:
        row = self.constraints_list.currentRow()
        if not (0 <= row < len(self._constraints)):
            return
        dlg = AddConstraintDialog(constraint=self._constraints[row], edit_mode=True, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._constraints[row] = dlg.get_constraint()
            self._refresh_constraints_list(select_row=row)
            self._update_action_states()

    def _on_delete_constraint(self) -> None:
        row = self.constraints_list.currentRow()
        if not (0 <= row < len(self._constraints)):
            return
        self._constraints.pop(row)
        next_row = min(row, len(self._constraints) - 1)
        self._refresh_constraints_list(select_row=next_row)
        self._update_action_states()

    def _on_reset_all(self) -> None:
        reply = QMessageBox.question(
            self,
            safe_tr("规划求解参数"),
            safe_tr("确定要重置所有目标、变量和约束设置吗？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.objective_edit.clear()
        self.radio_max.setChecked(True)
        self.target_value_edit.clear()
        self.variables_edit.clear()
        self._constraints.clear()
        self._refresh_constraints_list()
        self.non_negative_chk.setChecked(True)
        self.method_combo.setCurrentIndex(0)
        self._options = SolverOptions()
        self._set_status_message("")
        self._update_action_states()

    def _on_options(self) -> None:
        dlg = SolverOptionsDialog(options=self._options, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._options = dlg.get_options()

    def _on_save_model(self) -> None:
        if self.current_sheet is None:
            QMessageBox.warning(
                self,
                safe_tr("规划求解参数"),
                safe_tr("当前工作表无效，无法保存模型。"),
            )
            return
        if self.radio_value_of.isChecked():
            try:
                float(self.target_value_edit.text().strip() or "0")
            except (ValueError, TypeError):
                QMessageBox.warning(
                    self,
                    safe_tr("规划求解参数"),
                    safe_tr("请输入有效的数字目标值。"),
                )
                self.target_value_edit.setFocus()
                return
        params = self.build_params()
        save_solver_model(self.current_sheet, params)
        self._set_status_message(safe_tr("模型已保存到当前工作表。"))

    def _on_solve(self) -> None:
        if self._is_solving():
            return
        params = self._validate_inputs()
        if params is None or self.workbook is None:
            return

        self._active_params = params
        self.created_report_sheet = None
        self.created_report_sheets = []
        self.progress_bar.setRange(0, 0)
        self._set_status_message(safe_tr("正在求解，请稍候或点击停止..."))

        worker = _SolverWorker(self.workbook, params, parent=self)
        worker.progress_updated.connect(self._on_solve_progress)
        worker.solve_finished.connect(self._on_solve_finished)
        worker.solve_failed.connect(self._on_solve_failed)
        worker.finished.connect(self._on_worker_thread_finished)
        self._solving = True
        self._worker = worker
        worker.start()
        self._update_action_states()

    def _on_cancel_solve(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_cancel()
            self.cancel_btn.setEnabled(False)

    def _on_solve_progress(self, iteration: int, objective: float) -> None:
        if self._is_solving():
            self._set_status_message(
                safe_tr("迭代 {0}，目标值: {1}", iteration, _format_number(objective))
            )

    def _on_worker_thread_finished(self) -> None:
        worker = self._worker
        if worker is not None and not worker.isRunning():
            self._worker = None
            self._solving = False
            worker.deleteLater()
        self._update_action_states()

    def _join_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(3000)

    def _on_solve_failed(self, error_msg: str) -> None:
        self._join_worker()
        worker = self._worker
        self._worker = None
        self._solving = False
        if worker is not None:
            worker.deleteLater()
        self._update_action_states()
        msg = safe_tr("规划求解失败: {0}", error_msg)
        self._set_status_message(msg)
        QMessageBox.warning(self, safe_tr("规划求解参数"), msg)

    def _on_solve_finished(self, result: SolverResult) -> None:
        self._join_worker()
        worker = self._worker
        self._worker = None
        self._solving = False
        if worker is not None:
            worker.deleteLater()
        self.last_result = result
        self._update_action_states()

        if result.status == "cancelled":
            self._set_status_message(result.message or safe_tr("规划求解已取消。"))
            return

        if self.workbook is None or self._active_params is None:
            return

        params = self._active_params
        if result.solution_values:
            apply_solver_solution(self.workbook, result.solution_values)

        results_dlg = SolverResultsDialog(result, parent=self)
        if results_dlg.exec() == QDialog.DialogCode.Accepted:
            keep = results_dlg.keep_radio.isChecked()
            want_answer = results_dlg.report_chk.isChecked()
            want_sensitivity = results_dlg.sensitivity_report_chk.isChecked()
            want_limits = results_dlg.limits_report_chk.isChecked()
        else:
            keep = False
            want_answer = False
            want_sensitivity = False
            want_limits = False

        created_sheets: list[str] = []
        if want_answer:
            created_sheets.append(generate_answer_report(self.workbook, params, result))
        if want_sensitivity:
            created_sheets.append(generate_sensitivity_report(self.workbook, params, result))
        if want_limits:
            created_sheets.append(generate_limits_report(self.workbook, params, result))
        self.created_report_sheets = created_sheets
        self.created_report_sheet = created_sheets[0] if created_sheets else None

        if keep:
            if self.current_sheet is not None:
                save_solver_model(self.current_sheet, params)
            if self.apply_callback is not None:
                if result.initial_values:
                    apply_solver_solution(self.workbook, result.initial_values)
                self.apply_callback(params, result, True)
            elif result.solution_values:
                apply_solver_solution(self.workbook, result.solution_values)
            self._set_status_message(result.message or safe_tr("规划求解完成。"))
            self.accept()
            return

        if result.initial_values:
            apply_solver_solution(self.workbook, result.initial_values)
        if self.apply_callback is not None:
            self.apply_callback(params, result, False)
        self._set_status_message(result.message or safe_tr("规划求解完成。"))

    def shutdown_worker(self) -> None:
        """Cancel and wait for any active solver background thread."""
        self._solving = False
        worker = self._worker
        if worker is not None:
            if worker.isRunning():
                worker.request_cancel()
                worker.wait(3000)
            self._worker = None

    def reject(self) -> None:
        self.shutdown_worker()
        super().reject()

    def closeEvent(self, event: Any) -> None:
        self.shutdown_worker()
        super().closeEvent(event)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("规划求解参数"))
        self.objective_label.setText(safe_tr("设置目标(&T):"))
        self.goal_label.setText(safe_tr("到:"))
        self.radio_max.setText(safe_tr("最大值(&M)"))
        self.radio_min.setText(safe_tr("最小值(&N)"))
        self.radio_value_of.setText(safe_tr("值为(&V):"))
        self.variables_label.setText(safe_tr("通过更改可变单元格(&B):"))
        self.constraints_label.setText(safe_tr("遵守约束(&U):"))
        self.add_constraint_btn.setText(safe_tr("添加(&A)..."))
        self.edit_constraint_btn.setText(safe_tr("更改(&C)..."))
        self.delete_constraint_btn.setText(safe_tr("删除(&D)"))
        self.reset_all_btn.setText(safe_tr("全部重置(&R)"))
        self.non_negative_chk.setText(safe_tr("使无约束变量为非负数(&K)"))
        self.method_label.setText(safe_tr("选择求解方法(&E):"))
        for idx, (_method_key, raw_label) in enumerate(_METHOD_ITEMS):
            self.method_combo.setItemText(idx, safe_tr(raw_label))
        self.options_btn.setText(safe_tr("选项(&O)..."))
        self.save_model_btn.setText(safe_tr("保存模型(&S)"))
        self.solve_btn.setText(safe_tr("求解(&S)"))
        self.cancel_btn.setText(safe_tr("停止"))
        self.close_btn.setText(safe_tr("关闭"))
        self._refresh_constraints_list()


__all__ = [
    "AddConstraintDialog",
    "SolverOptionsDialog",
    "SolverParametersDialog",
    "SolverResultsDialog",
]
