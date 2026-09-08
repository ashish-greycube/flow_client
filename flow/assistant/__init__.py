# Re-exported so the after_migrate hook stays reachable at flow.assistant.<name>.
from flow.assistant.assistant import (
	ASSISTANT_AGENT_TITLE,
	ASSISTANT_INSTRUCTIONS,
	sync_builtin_assistant,
)
from flow.assistant.ocr_agent import (
	OCR_AGENT_INSTRUCTIONS,
	OCR_AGENT_TITLE,
	sync_ocr_agent,
)

__all__ = [
	"ASSISTANT_AGENT_TITLE",
	"ASSISTANT_INSTRUCTIONS",
	"OCR_AGENT_INSTRUCTIONS",
	"OCR_AGENT_TITLE",
	"sync_builtin_assistant",
	"sync_ocr_agent",
]
