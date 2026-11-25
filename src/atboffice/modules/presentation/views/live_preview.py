"""Live preview of transitions and animations on the editing canvas (not a slide show).

The overlay sits exactly over the slide in the canvas viewport and plays frames rendered
by the slide-show renderer, then disappears. Esc or a click stops it.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QElapsedTimer, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

FRAME_MS = 33


class LivePreviewOverlay(QLabel):
    finished = Signal()

    def __init__(self, view: Any) -> None:
        super().__init__(view.viewport())
        self.view = view
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._render: Any = None
        self.duration = 0

    # ---------------------------------------------------------------- geometry
    def slide_rect(self, pres: Any) -> QRect:
        poly = self.view.mapFromScene(QRectF(0, 0, float(pres.w), float(pres.h)))
        return poly.boundingRect()

    # ---------------------------------------------------------------- playback
    def _start(self, rect: QRect, duration: int, render: Any) -> None:
        self.setGeometry(rect)
        self.duration = max(1, int(duration))
        self._render = render
        self.render_at(0)
        self.show()
        self.raise_()
        self.setFocus()
        self._clock.start()
        self._timer.start()

    def render_at(self, ms: int) -> QImage:
        """Render (and show) the frame ``ms`` milliseconds into the preview."""
        img = self._render(max(0, min(ms, self.duration)), self.width(), self.height())
        self.setPixmap(QPixmap.fromImage(img))
        return img

    def _tick(self) -> None:
        elapsed = self._clock.elapsed()
        if elapsed >= self.duration:
            self.stop()
            return
        self.render_at(elapsed)

    def is_playing(self) -> bool:
        return self._timer.isActive()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()
        self.finished.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.stop()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.stop()

    # ---------------------------------------------------------------- transitions
    def play_transition(self, pres: Any, slide: Any, previous: Any | None) -> int:
        """Preview ``slide``'s transition from ``previous`` (or black). Returns ms."""
        from atboffice.modules.presentation.slideshow.transitions import (
            get_transition_duration,
            render_slide_to_image,
            render_transition_frame,
        )

        rect = self.slide_rect(pres)
        w, h = max(1, rect.width()), max(1, rect.height())
        img_to = render_slide_to_image(slide, pres, w, h)
        if previous is not None:
            img_from = render_slide_to_image(previous, pres, w, h)
        else:
            img_from = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
            img_from.fill(Qt.GlobalColor.black)
        trans = getattr(slide, "transition", None)
        duration = get_transition_duration(trans) if trans else 0
        if not trans or trans.type in (None, "", "none") or duration <= 0:
            duration = 400  # "No Transition" still shows the slide briefly

        def render(ms: int, width: int, height: int) -> QImage:
            frame = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            painter = QPainter(frame)
            render_transition_frame(
                painter,
                img_from.scaled(width, height),
                img_to.scaled(width, height),
                trans,
                ms / duration,
                width,
                height,
            )
            painter.end()
            return frame

        self._start(rect, duration, render)
        return duration

    # ---------------------------------------------------------------- animations
    def play_animations(self, pres: Any, slide: Any, anim_id: str = "") -> int:
        """Play the slide's builds in order (only ``anim_id``'s step when given)."""
        from atboffice.modules.presentation.slideshow.animations import (
            apply_step_state,
            compile_steps,
            compute_frame,
        )
        from atboffice.modules.presentation.slideshow.transitions import render_slide_to_image

        sw, sh = float(pres.w), float(pres.h)
        steps = compile_steps(slide, sw, sh)
        if anim_id:
            index = next(
                (i for i, st in enumerate(steps) if any(it.anim.id == anim_id for it in st.items)),
                None,
            )
            if index is None:
                return 0
            first, chosen = index, [steps[index]]
        else:
            first, chosen = 0, steps
        if not chosen:
            return 0
        bounds = {s.id: QRectF(s.x, s.y, s.w, s.h) for s in slide.shapes}
        starts, total = [], 0
        for st in chosen:
            starts.append(total)
            total += max(1, st.total_duration)
        rect = self.slide_rect(pres)

        def render(ms: int, width: int, height: int) -> QImage:
            idx = max(i for i, s0 in enumerate(starts) if s0 <= ms)
            local = ms - starts[idx]
            states = apply_step_state(steps, first + idx, bounds, sw, sh)
            for it in chosen[idx].items:
                if local < it.start:
                    continue
                t = 1.0 if it.dur <= 0 else min(1.0, (local - it.start) / it.dur)
                states[it.shape_id] = compute_frame(
                    it.anim, t, bounds.get(it.shape_id, QRectF(0, 0, 100, 100)), sw, sh
                )
            return render_slide_to_image(slide, pres, width, height, states)

        self._start(rect, total, render)
        return total


def preview_overlay(view: QWidget) -> LivePreviewOverlay:
    """The canvas view's (single) preview overlay."""
    overlay = getattr(view, "_live_preview", None)
    if overlay is None:
        overlay = LivePreviewOverlay(view)
        view._live_preview = overlay
    return overlay
