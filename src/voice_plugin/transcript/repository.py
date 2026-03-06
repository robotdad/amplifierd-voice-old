"""Voice conversation repository for disk-backed persistence.

Disk layout:
  ~/.amplifier-voice/{session_id}/conversation.json  (atomic write)
  ~/.amplifier-voice/{session_id}/transcript.jsonl   (append-only)
  ~/.amplifier-voice/index.json                      (fast listing)

For amplifierd integration, voice sessions are also written to:
  {sessions_dir}/{session_id}/transcript.jsonl       (cross-app visibility)
  {sessions_dir}/{session_id}/metadata.json          (session metadata)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from voice_plugin.transcript.models import TranscriptEntry, VoiceConversation


class VoiceConversationRepository:
    """Disk-backed repository for voice conversations and transcripts."""

    def __init__(
        self,
        base_dir: Path | None = None,
        sessions_dir: Path | None = None,
    ) -> None:
        self.base_dir = base_dir or Path.home() / ".amplifier-voice"
        self.sessions_dir = sessions_dir
        self._index_path = self.base_dir / "index.json"

    def _write_atomic(self, path: Path, data: dict[str, Any] | list[Any]) -> None:
        """Write JSON atomically via .tmp -> rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp.rename(path)

    def _read_index(self) -> list[dict[str, Any]]:
        """Read current index; return empty list if not present."""
        if not self._index_path.exists():
            return []
        return cast(list[dict[str, Any]], json.loads(self._index_path.read_text()))

    def _write_index(self, entries: list[dict[str, Any]]) -> None:
        """Atomically overwrite index.json."""
        self._write_atomic(self._index_path, entries)

    def _patch_index_entry(self, session_id: str, **fields: Any) -> None:
        """Read index, update fields on the matching entry, write back."""
        index = self._read_index()
        for item in index:
            if item["id"] == session_id:
                item.update(fields)
                break
        self._write_index(index)

    def create_conversation(self, conv: VoiceConversation) -> None:
        """Create session directory, touch transcript.jsonl, write conversation.json
        and update index.json."""
        session_dir = self.base_dir / conv.id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "transcript.jsonl").touch()
        self._write_atomic(session_dir / "conversation.json", conv.to_dict())

        index = self._read_index()
        index.append(
            {
                "id": conv.id,
                "title": conv.title,
                "status": conv.status,
                "created_at": conv.created_at.isoformat(),
            }
        )
        self._write_index(index)

    def get_conversation(self, session_id: str) -> VoiceConversation | None:
        """Return VoiceConversation for session_id, or None if not found."""
        conv_path = self.base_dir / session_id / "conversation.json"
        if not conv_path.exists():
            return None
        return VoiceConversation.from_dict(json.loads(conv_path.read_text()))

    def update_conversation(self, conv: VoiceConversation) -> None:
        """Atomic write of conversation.json only."""
        session_dir = self.base_dir / conv.id
        self._write_atomic(session_dir / "conversation.json", conv.to_dict())

    def update_status(
        self,
        session_id: str,
        status: Literal["active", "disconnected", "ended"],
    ) -> None:
        """Update status in both conversation.json and index.json."""
        conv = self.get_conversation(session_id)
        if conv is None:
            return
        conv.status = status
        conv.updated_at = datetime.now(UTC)
        self._write_atomic(
            self.base_dir / session_id / "conversation.json", conv.to_dict()
        )
        self._patch_index_entry(session_id, status=status)

    def end_conversation(
        self,
        session_id: str,
        reason: Literal[
            "session_limit", "network_error", "user_ended", "idle_timeout", "error"
        ],
    ) -> None:
        """Set status='ended', end_reason, ended_at, duration_seconds."""
        conv = self.get_conversation(session_id)
        if conv is None:
            return
        now = datetime.now(UTC)
        conv.status = "ended"
        conv.end_reason = reason
        conv.ended_at = now
        conv.updated_at = now
        conv.duration_seconds = (now - conv.created_at).total_seconds()
        self._write_atomic(
            self.base_dir / session_id / "conversation.json", conv.to_dict()
        )
        self._patch_index_entry(session_id, status="ended", end_reason=reason)

    def _maybe_set_title(self, session_id: str, text: str) -> None:
        """Update session title from the first user message if still at default."""
        conv = self.get_conversation(session_id)
        if conv is None:
            return
        if not conv.title.startswith("Voice session "):
            return
        words = text.strip().split()
        title = " ".join(words[:6])
        if len(title) > 40:
            title = title[:37] + "..."
        if not title:
            return
        conv.title = title
        conv.updated_at = datetime.now(UTC)
        self._write_atomic(
            self.base_dir / session_id / "conversation.json", conv.to_dict()
        )
        self._patch_index_entry(session_id, title=title)

    def add_entries(self, session_id: str, entries: list[TranscriptEntry]) -> None:
        """Batch-append entries to transcript.jsonl."""
        jsonl_path = self.base_dir / session_id / "transcript.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        for entry in entries:
            if entry.role == "user":
                self._maybe_set_title(session_id, entry.content)
                break

    def get_resumption_context(self, session_id: str) -> list[dict[str, Any]]:
        """Read transcript.jsonl and return items in OpenAI Realtime API format."""
        jsonl_path = self.base_dir / session_id / "transcript.jsonl"
        if not jsonl_path.exists():
            return []

        items: list[dict[str, Any]] = []
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            entry_data: dict[str, Any] = json.loads(line)
            role = entry_data.get("role", "")
            content = entry_data.get("content", "")

            if role == "user":
                items.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": content}],
                    }
                )
            elif role == "assistant":
                items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": content}],
                    }
                )
            elif role == "tool_call":
                items.append(
                    {
                        "type": "function_call",
                        "name": entry_data.get("tool_name"),
                        "call_id": entry_data.get("call_id"),
                        "arguments": content,
                    }
                )
            elif role == "tool_result":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": entry_data.get("call_id"),
                        "output": content,
                    }
                )

        return items

    def list_conversations(self) -> list[dict[str, Any]]:
        """Return all conversations from index.json (fast listing)."""
        return self._read_index()

    def write_to_amplifierd_transcript(
        self,
        session_id: str,
        entries: list[TranscriptEntry],
    ) -> None:
        """Write voice turns to the amplifierd session transcript for cross-app
        visibility.

        Only user/assistant turns are written.
        """
        if self.sessions_dir is None:
            return
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = session_dir / "transcript.jsonl"
        transcript_path.touch(exist_ok=True)

        lines_to_write = []
        for entry in entries:
            if entry.role not in ("user", "assistant"):
                continue
            msg = {
                "role": entry.role,
                "content": [{"type": "text", "text": entry.content}],
            }
            lines_to_write.append(json.dumps(msg, ensure_ascii=False))

        if lines_to_write:
            with transcript_path.open("a", encoding="utf-8") as f:
                for line in lines_to_write:
                    f.write(line + "\n")

    def write_amplifierd_metadata(
        self,
        session_id: str,
        conv: VoiceConversation,
    ) -> None:
        """Write metadata.json to the amplifierd session directory."""
        if self.sessions_dir is None:
            return
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        metadata: dict[str, str | int] = {
            "session_id": session_id,
            "bundle": "voice",
            "name": conv.title,
            "created": conv.created_at.isoformat(),
            "model": "voice",
            "turn_count": 0,
        }
        self._write_atomic(session_dir / "metadata.json", metadata)
