"""Slide Show > Rehearse Timings: a timer HUD over the show that records each slide's time.

When the show ends the user is asked whether to keep the new timings; kept timings go
to ``slide.transition.after`` (seconds), like PowerPoint 2003.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QToolButton, QWidget


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("Rehearsal", text)


def fmt(ms: int) -> str:
    s = max(0, int(ms)) // 1000
    return f"{s // 3600:d}:{s // 60 % 60:02d}:{s % 60:02d}"


class RehearsalHud(QFrame):
    """The Rehearsal toolbar: Next, Pause, slide time, Repeat, total time."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("RehearsalHud")
        self.setStyleSheet(
            "#RehearsalHud { background: #F0F0F0; border: 1px solid #7F7F7F; }"
            "QLabel { font: 11pt 'Arial'; padding: 0 6px; }"
        )
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 2, 4, 2)
        self.btn_next = QToolButton(self)
        self.btn_pause = QToolButton(self)
        self.btn_pause.setCheckable(True)
        self.lbl_slide = QLabel("0:00:00", self)
        self.btn_repeat = QToolButton(self)
        self.lbl_total = QLabel("0:00:00", self)
        for w in (self.btn_next, self.btn_pause, self.lbl_slide, self.btn_repeat, self.lbl_total):
            h.addWidget(w)
        self.retranslate_ui()
        self.adjustSize()
        self.move(8, 8)

    def retranslate_ui(self) -> None:
        self.btn_next.setText(safe_tr("下一项"))
        self.btn_pause.setText(safe_tr("暂停"))
        self.btn_repeat.setText(safe_tr("重复"))
        self.btn_next.setToolTip(safe_tr("下一项"))
        self.btn_pause.setToolTip(safe_tr("暂停计时"))
        self.btn_repeat.setToolTip(safe_tr("重新开始当前幻灯片的计时"))


class RehearsalRecorder(QObject):
    """Times every slide shown in ``show_view`` (a SlideShowView)."""

    timings_saved = Signal(dict)  # {slide_index: seconds}

    def __init__(
        self,
        show_view: Any,
        presentation: Any,
        ask_keep: Callable[[int], bool] | None = None,
    ) -> None:
        super().__init__(show_view)
        self.show_view = show_view
        self.presentation = presentation
        self.ask_keep = ask_keep or self._ask_keep
        self.timings: dict[int, int] = {}  # slide index -> ms
        self.current = getattr(show_view, "current_slide_index", 0)
        self._slide_clock = QElapsedTimer()
        self._slide_ms = 0  # accumulated before the last pause
        self._total_ms = 0
        self._paused = False
        self._slide_clock.start()
        self.hud = RehearsalHud(show_view)
        self.hud.btn_next.clicked.connect(lambda _c=False: show_view.next_slide())
        self.hud.btn_pause.toggled.connect(self.set_paused)
        self.hud.btn_repeat.clicked.connect(lambda _c=False: self.repeat())
        self.hud.show()
        self.hud.raise_()
        self._tick = QTimer(self)
        self._tick.setInterval(500)
        self._tick.timeout.connect(self.refresh)
        self._tick.start()
        show_view.slideChanged.connect(self.on_slide_changed)
        show_view.showEnded.connect(self.finish)

    # ---------------------------------------------------------------- timing
    def slide_elapsed(self) -> int:
        live = 0 if self._paused else self._slide_clock.elapsed()
        return self._slide_ms + live

    def total_elapsed(self) -> int:
        return self._total_ms + self.slide_elapsed()

    def refresh(self) -> None:
        self.hud.lbl_slide.setText(fmt(self.slide_elapsed()))
        self.hud.lbl_total.setText(fmt(self.total_elapsed()))

    def set_paused(self, paused: bool) -> None:
        if paused == self._paused:
            return
        if paused:
            self._slide_ms += self._slide_clock.elapsed()
        else:
            self._slide_clock.restart()
        self._paused = paused
        self.refresh()

    def repeat(self) -> None:
        """Restart timing of the current slide."""
        self._slide_ms = 0
        self._slide_clock.restart()
        self.refresh()

    def record_current(self) -> None:
        ms = self.slide_elapsed()
        self.timings[self.current] = self.timings.get(self.current, 0) + ms
        self._total_ms += ms
        self._slide_ms = 0
        self._slide_clock.restart()

    def on_slide_changed(self, index: int) -> None:
        if index == self.current:
            return
        self.record_current()
        self.current = index
        self.refresh()

    # ---------------------------------------------------------------- end
    def _ask_keep(self, total_ms: int) -> bool:
        res = QMessageBox.question(
            self.show_view if self.show_view.isVisible() else None,
            safe_tr("排练计时"),
            safe_tr("幻灯片放映共需 {0}。是否保留新的幻灯片排练时间？").format(fmt(total_ms)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return res == QMessageBox.StandardButton.Yes

    def finish(self) -> dict[int, float]:
        """Stop timing; apply timings to the slides when the user keeps them."""
        if not self._tick.isActive():
            return {}
        self._tick.stop()
        self.record_current()
        self.hud.hide()
        if not self.timings or not self.ask_keep(self._total_ms):
            return {}
        from atboffice.modules.presentation.models.slide import Transition

        saved: dict[int, float] = {}
        for idx, ms in self.timings.items():
            if 0 <= idx < len(self.presentation.slides):
                slide = self.presentation.slides[idx]
                if slide.transition is None:
                    slide.transition = Transition()
                slide.transition.after = round(ms / 1000.0, 1)
                saved[idx] = slide.transition.after
        self.timings_saved.emit(saved)
        return saved


def attach_rehearsal(show_view: Any, presentation: Any, **kwargs: Any) -> RehearsalRecorder:
    recorder = RehearsalRecorder(show_view, presentation, **kwargs)
    show_view._rehearsal = recorder
    show_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return recorder
