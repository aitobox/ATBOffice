"""PPTX reader: animations, transitions, media timing, notes and comments."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from atboffice.modules.presentation.io.pptx_common import (
    REL_AUTHORS_MODERN,
    REL_COMMENT_AUTHORS,
    REL_COMMENTS,
    REL_COMMENTS_MODERN,
    REL_NOTES_SLIDE,
    _get_attr,
    _get_child,
    _get_children,
    _local_tag,
    _resolve_path,
    safe_float,
    safe_int,
)
from atboffice.modules.presentation.models.comment import (
    Comment,
    CommentAuthor,
    CommentReply,
)
from atboffice.modules.presentation.models.media_item import (
    PlaybackSettings,
)
from atboffice.modules.presentation.models.presentation import (
    LoadWarning,
    Presentation,
)
from atboffice.modules.presentation.models.shape import (
    Shape,
)
from atboffice.modules.presentation.models.slide import Animation, Slide, Transition
from atboffice.vfs import etree as ET


class PptxSlideExtrasMixin:
    """Reads animations, transitions, media timing, notes and comments."""

    def _parse_slide_media_timing(
        self,
        timing_elem: ET.Element | None,
    ) -> dict[str, PlaybackSettings]:
        """Extract media playback settings keyed by target shape ID."""
        if timing_elem is None:
            return {}
        settings_by_id: dict[str, PlaybackSettings] = {}
        for node in timing_elem.iter():
            ltag = _local_tag(node.tag)
            if ltag in ("cMediaNode", "video", "audio"):
                spid = None
                for child in node.iter():
                    if _local_tag(child.tag) == "spTgt":
                        spid = _get_attr(child, "spid")
                        break
                if not spid:
                    continue

                vol_str = _get_attr(node, "vol")
                volume = 0.8
                if vol_str is not None:
                    try:
                        volume = max(0.0, min(1.0, float(vol_str) / 100000.0))
                    except (ValueError, TypeError):
                        pass

                show_when_stopped = _get_attr(node, "showWhenStopped", "1")
                hide_while_not_playing = show_when_stopped == "0"

                loop = False
                c_tn = _get_child(node, "cTn")
                if c_tn is not None:
                    repeat_count = _get_attr(c_tn, "repeatCount", "")
                    if repeat_count in ("indefinite", "INF"):
                        loop = True

                settings_by_id[spid] = PlaybackSettings(
                    volume=volume,
                    hide_while_not_playing=hide_while_not_playing,
                    loop=loop,
                )
        return settings_by_id

    def _parse_slide_animations(
        self,
        timing_elem: ET.Element | None,
        shapes: list[Shape],
    ) -> list[Animation]:
        """Parse sequential and parallel animation effects from <p:timing>."""
        if timing_elem is None:
            return []

        # Find mainSeq cTn element
        main_seq = None
        for elem in timing_elem.iter():
            if _local_tag(elem.tag) == "cTn" and _get_attr(elem, "nodeType") == "mainSeq":
                main_seq = elem
                break

        target_root = main_seq if main_seq is not None else timing_elem

        id_map: dict[str, str] = {}
        for s in shapes:
            id_map[s.id] = s.id
            if s.name:
                id_map[s.name] = s.id

        ENTR_MAP = {
            1: "appear",
            2: "flyIn",
            3: "blinds",
            4: "box",
            5: "checkerboard",
            6: "circle",
            8: "diamond",
            9: "dissolve",
            10: "fade",
            12: "peekIn",
            13: "plus",
            14: "randomBars",
            16: "split",
            18: "strips",
            20: "wedge",
            21: "wheel",
            22: "wipe",
            23: "zoom",
            42: "ascend",
            47: "descend",
            49: "spinner",
            55: "expand",
        }
        EXIT_MAP = {
            "appear": "disappear",
            "flyIn": "flyOut",
            "ascend": "descend",
            "expand": "fade",
            "spinner": "zoom",
        }
        EMPH_MAP = {
            6: "growShrink",
            8: "spin",
            9: "transparency",
            32: "teeter",
            35: "blink",
        }
        DIR_MAP = {
            1: "b",
            2: "l",
            4: "r",
            8: "t",
            5: "rb",
            9: "rt",
            6: "lb",
            10: "lt",
        }

        animations: list[Animation] = []

        for ctn in target_root.iter():
            if _local_tag(ctn.tag) != "cTn":
                continue
            cls = _get_attr(ctn, "presetClass")
            if not cls or cls not in ("entr", "exit", "emph", "path"):
                continue

            spid = None
            para_idx = None
            for descendant in ctn.iter():
                dtag = _local_tag(descendant.tag)
                if dtag == "spTgt":
                    spid = _get_attr(descendant, "spid")
                    prg = _get_child(descendant, "pRg")
                    if prg is not None:
                        st = _get_attr(prg, "st")
                        if st is not None:
                            try:
                                para_idx = int(st)
                            except ValueError:
                                pass
                    break

            if not spid:
                continue

            sid = id_map.get(spid, spid)

            node_type = _get_attr(ctn, "nodeType")
            if node_type == "clickEffect":
                start = "click"
            elif node_type == "afterEffect":
                start = "after"
            elif node_type == "withEffect":
                start = "with"
            else:
                has_click = False
                has_after = False
                for cond in ctn.iter():
                    if _local_tag(cond.tag) == "cond":
                        delay_attr = _get_attr(cond, "delay", "")
                        evt_attr = _get_attr(cond, "evt", "")
                        if delay_attr == "indefinite" or evt_attr in ("onClick", "onNext"):
                            has_click = True
                        elif evt_attr == "onEnd":
                            has_after = True
                if has_click:
                    start = "click"
                elif has_after:
                    start = "after"
                else:
                    start = "with"

            dur_val = _get_attr(ctn, "dur")
            dur = 500
            if dur_val and dur_val != "indefinite":
                dur = safe_int(dur_val, 500)

            delay = 0
            for cond in ctn.iter():
                if _local_tag(cond.tag) == "cond":
                    d_val = _get_attr(cond, "delay")
                    if d_val and d_val != "indefinite":
                        parsed_delay = safe_int(d_val, -1)
                        if parsed_delay >= 0:
                            delay = parsed_delay
                            break

            pid_str = _get_attr(ctn, "presetID")
            pid = safe_int(pid_str, 10) if pid_str else 10

            sub_str = _get_attr(ctn, "presetSubtype")
            sub = safe_int(sub_str, 0) if sub_str else 0

            direction = None
            if cls in ("entr", "exit"):
                eff = ENTR_MAP.get(pid)
                if not eff:
                    anim_effect = next(
                        (c for c in ctn.iter() if _local_tag(c.tag) == "animEffect"), None
                    )
                    eff = _get_attr(anim_effect, "filter", "fade") or "fade"

                if cls == "exit":
                    eff = EXIT_MAP.get(eff, eff)

                direction = DIR_MAP.get(sub)
                if not direction and eff in ("flyIn", "flyOut"):
                    direction = "b"

                if eff in ("appear", "disappear"):
                    dur = 1

            elif cls == "emph":
                eff = EMPH_MAP.get(pid, "growShrink")
            elif cls == "path":
                eff = "custom"
            else:
                eff = "fade"

            by = "para" if para_idx is not None else "all"

            anim = Animation(
                id=f"a_{uuid.uuid4().hex[:6]}",
                sid=sid,
                cls=cls,
                eff=eff,
                dir=direction,
                start=start,
                dur=dur,
                delay=delay,
                by=by,
                para=para_idx,
            )
            animations.append(anim)

        return animations

    def _read_media_part(self, part_path: str) -> bytes | None:
        """Return a media part's bytes (cached in media_map), or None if absent."""
        if part_path in self.media_map:
            return self.media_map[part_path]
        if not self.package.has_part(part_path):
            return None
        data = self.package.read_part(part_path)
        if data is not None:
            self.media_map[part_path] = data
        return data

    def _parse_transition(self, trans_elem: ET.Element | None) -> Transition:
        """Parse slide transition timing and type."""
        if trans_elem is None:
            return Transition()

        trans_type = "none"
        dir_val = None
        orient_val = None
        spokes_val = None
        thru_blk = False

        KNOWN_TRANSITIONS = (
            "fade",
            "wipe",
            "push",
            "split",
            "cover",
            "pull",
            "wheel",
            "zoom",
            "blinds",
            "checker",
            "comb",
            "cut",
            "dissolve",
            "newsflash",
            "plus",
            "randomBar",
            "circle",
            "diamond",
            "strips",
            "wedge",
            "random",
        )

        for child in trans_elem:
            tag = _local_tag(child.tag)
            if tag in KNOWN_TRANSITIONS:
                trans_type = tag
                dir_val = _get_attr(child, "dir")
                orient_val = _get_attr(child, "orient")
                sp_attr = _get_attr(child, "spokes")
                if sp_attr:
                    try:
                        spokes_val = int(sp_attr)
                    except ValueError:
                        pass
                thru_attr = _get_attr(child, "thruBlk")
                if thru_attr in ("1", "true"):
                    thru_blk = True
                break

        speed = _get_attr(trans_elem, "spd", "fast") or "fast"
        adv_click = _get_attr(trans_elem, "advClick", "1") in ("1", "true")
        adv_tm = _get_attr(trans_elem, "advTm")
        after = safe_float(adv_tm, 0.0) / 1000.0 if adv_tm else None

        return Transition(
            type=trans_type,
            speed=speed,
            click=adv_click,
            after=after,
            dir=dir_val,
            orient=orient_val,
            spokes=spokes_val,
            thruBlk=thru_blk,
        )

    def _extract_notes(self, slide_path: str, rel_map: dict[str, Any]) -> str:
        """Extract speaker notes text from associated notesSlide if present."""
        for rel in rel_map.values():
            if rel.type == REL_NOTES_SLIDE or rel.type.endswith("/notesSlide"):
                notes_path = _resolve_path(slide_path, rel.target)
                if self.package.has_part(notes_path):
                    try:
                        n_bytes = self.package.read_part(notes_path)
                        n_xml = ET.fromstring(n_bytes)
                        texts: list[str] = []
                        for sp in n_xml.iter():
                            if _local_tag(sp.tag) == "sp":
                                nv_sp_pr = _get_child(sp, "nvSpPr")
                                nv_pr = (
                                    _get_child(nv_sp_pr, "nvPr") if nv_sp_pr is not None else None
                                )
                                ph = _get_child(nv_pr, "ph") if nv_pr is not None else None
                                if ph is not None and _get_attr(ph, "type") == "body":
                                    tx_body = _get_child(sp, "txBody")
                                    if tx_body is not None:
                                        for p in _get_children(tx_body, "p"):
                                            p_text = "".join(
                                                t.text
                                                for t in p.iter()
                                                if _local_tag(t.tag) == "t" and t.text
                                            )
                                            texts.append(p_text)
                        if texts:
                            return "\n".join(texts)
                    except Exception:
                        pass
        return ""

    def _parse_comment_authors(
        self, pres_part: str, pres_rels: list[Any], pres: Presentation
    ) -> None:
        """Parse legacy and modern comment authors into presentation model."""
        author_targets: list[str] = []
        for rel in pres_rels:
            r_type = rel.type or ""
            if (
                r_type == REL_COMMENT_AUTHORS
                or r_type == REL_AUTHORS_MODERN
                or r_type.endswith("/commentAuthors")
                or r_type.endswith("/authors")
            ):
                author_targets.append(_resolve_path(pres_part, rel.target))

        # Check default paths if relationships omitted
        if not author_targets:
            if self.package.has_part("ppt/commentAuthors.xml"):
                author_targets.append("ppt/commentAuthors.xml")
            if self.package.has_part("ppt/authors.xml"):
                author_targets.append("ppt/authors.xml")

        for part_path in author_targets:
            if not self.package.has_part(part_path):
                continue
            try:
                xml_data = self.package.read_part(part_path)
                root = ET.fromstring(xml_data)
                for elem in root.iter():
                    tag = _local_tag(elem.tag)
                    if tag in ("cmAuthor", "author"):
                        aid = _get_attr(elem, "id", "") or ""
                        name = _get_attr(elem, "name", "") or "Author"
                        initials = _get_attr(elem, "initials", "") or ""
                        last_idx = safe_int(_get_attr(elem, "lastIdx", "0"), 0)
                        clr_idx = safe_int(_get_attr(elem, "clrIdx", "0"), 0)
                        user_id = _get_attr(elem, "userId", "") or ""
                        provider_id = _get_attr(elem, "providerId", "") or ""
                        author = CommentAuthor(
                            id=aid,
                            name=name,
                            initials=initials,
                            last_idx=last_idx,
                            color_idx=clr_idx,
                            user_id=user_id,
                            provider_id=provider_id,
                        )
                        if not any(a.id == aid for a in pres.comment_authors):
                            pres.comment_authors.append(author)
            except Exception as exc:
                self._warnings.append(
                    LoadWarning(scope="comments", location=part_path, message=str(exc))
                )
                continue

    def _parse_slide_comments(
        self,
        slide_path: str,
        rel_map: dict[str, Any],
        slide: Slide,
        pres: Presentation,
    ) -> None:
        """Parse legacy and modern comments associated with this slide."""
        comment_parts: list[str] = []
        for rel in rel_map.values():
            r_type = rel.type or ""
            if (
                r_type == REL_COMMENTS
                or r_type == REL_COMMENTS_MODERN
                or r_type.endswith("/comments")
            ):
                target = _resolve_path(slide_path, rel.target)
                if self.package.has_part(target) and target not in comment_parts:
                    comment_parts.append(target)

        # Fallback check for standard naming
        if not comment_parts:
            stem = Path(slide_path).stem
            # e.g. slide1 -> comment1.xml
            idx_part = "".join(ch for ch in stem if ch.isdigit())
            candidate = f"ppt/comments/comment{idx_part}.xml" if idx_part else ""
            if candidate and self.package.has_part(candidate):
                comment_parts.append(candidate)

        for part_path in comment_parts:
            try:
                xml_data = self.package.read_part(part_path)
                root = ET.fromstring(xml_data)
                is_modern = (
                    "2018/8" in (root.tag or "")
                    or "2018/8" in (root.attrib.get("xmlns", "") or "")
                    or any("2018/8" in str(v) for v in root.attrib.values())
                )

                for elem in root.iter():
                    if _local_tag(elem.tag) != "cm":
                        continue

                    cm_id = _get_attr(elem, "id", "") or f"cm_{len(slide.comments) + 1}"
                    author_id = _get_attr(elem, "authorId", "0") or "0"
                    created = _get_attr(elem, "created", _get_attr(elem, "dt", "") or "") or ""
                    idx = safe_int(_get_attr(elem, "idx", "1"), 1)
                    status = _get_attr(elem, "status", "active") or "active"

                    # Coordinates from <pos>
                    pos_elem = _get_child(elem, "pos")
                    if pos_elem is None:
                        for sub in elem:
                            if _local_tag(sub.tag) == "pos":
                                pos_elem = sub
                                break

                    x_val, y_val = 20.0, 20.0
                    if pos_elem is not None:
                        raw_x = _get_attr(pos_elem, "x", "254000")
                        raw_y = _get_attr(pos_elem, "y", "254000")
                        fx = safe_float(raw_x, 254000.0)
                        fy = safe_float(raw_y, 254000.0)
                        x_val = round(fx / 12700.0, 2) if fx > 2000.0 else round(fx, 2)
                        y_val = round(fy / 12700.0, 2) if fy > 2000.0 else round(fy, 2)

                    # Extract text
                    text = ""
                    text_elem = _get_child(elem, "text")
                    if text_elem is not None and text_elem.text:
                        text = text_elem.text
                    else:
                        tx_body = _get_child(elem, "txBody")
                        if tx_body is not None:
                            body_parts = [
                                node.text
                                for node in tx_body.iter()
                                if _local_tag(node.tag) == "t" and node.text
                            ]
                            text = "".join(body_parts).strip()

                    # Shape anchor: search for <spMk id="...">
                    shape_id = None
                    for node in elem.iter():
                        if _local_tag(node.tag) == "spMk":
                            shape_id = _get_attr(node, "id")
                            if shape_id:
                                break

                    # Modern replies
                    replies: list[CommentReply] = []
                    reply_lst = _get_child(elem, "replyLst")
                    if reply_lst is not None:
                        for rep in _get_children(reply_lst, "reply"):
                            rep_id = _get_attr(rep, "id", "") or f"rep_{len(replies) + 1}"
                            rep_auth = _get_attr(rep, "authorId", author_id) or author_id
                            rep_created = _get_attr(rep, "created", created) or created
                            rep_text_parts: list[str] = [
                                t.text for t in rep.iter() if _local_tag(t.tag) == "t" and t.text
                            ]
                            replies.append(
                                CommentReply(
                                    id=rep_id,
                                    author_id=rep_auth,
                                    created=rep_created,
                                    text="".join(rep_text_parts).strip(),
                                )
                            )

                    # Ensure author exists in presentation
                    if not pres.find_author(author_id):
                        pres.get_or_create_author(name=f"Author {author_id}")

                    slide.comments.append(
                        Comment(
                            id=cm_id,
                            author_id=author_id,
                            text=text,
                            x=x_val,
                            y=y_val,
                            idx=idx,
                            created=created,
                            shape_id=shape_id,
                            status=status,
                            replies=replies,
                            is_modern=is_modern,
                        )
                    )
            except Exception as exc:
                self._warnings.append(
                    LoadWarning(scope="comments", location=part_path, message=str(exc))
                )
                continue
