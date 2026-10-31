"""Common office visual and auxiliary modules."""

from atboffice.modules.common.assistant_scout import (
    ScoutBalloon,
    ScoutWidget,
    get_scout_assistant,
    toggle_assistant,
)
from atboffice.modules.common.clipart_dialog import (
    CLIPART_DATABASE,
    ClipartCategory,
    ClipartDialog,
    ClipartItem,
    prompt_insert_clipart,
)
from atboffice.modules.common.wordart_gallery import (
    WordArtGalleryDialog,
    prompt_insert_wordart,
)

__all__ = [
    "WordArtGalleryDialog",
    "prompt_insert_wordart",
    "ClipartCategory",
    "ClipartItem",
    "CLIPART_DATABASE",
    "ClipartDialog",
    "prompt_insert_clipart",
    "ScoutBalloon",
    "ScoutWidget",
    "get_scout_assistant",
    "toggle_assistant",
]
