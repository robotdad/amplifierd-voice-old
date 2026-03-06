"""Tests for voice transcript models and repository."""

from datetime import UTC, datetime

from voice_plugin.transcript.models import (
    DisconnectEvent,
    TranscriptEntry,
    VoiceConversation,
)
from voice_plugin.transcript.repository import VoiceConversationRepository


def test_voice_conversation_roundtrip():
    now = datetime.now(UTC)
    conv = VoiceConversation(
        id="test-123",
        title="Test session",
        status="active",
        created_at=now,
        updated_at=now,
    )
    d = conv.to_dict()
    restored = VoiceConversation.from_dict(d)
    assert restored.id == conv.id
    assert restored.title == conv.title
    assert restored.status == conv.status


def test_transcript_entry_roundtrip():
    now = datetime.now(UTC)
    entry = TranscriptEntry(
        id="entry-1",
        conversation_id="test-123",
        role="user",
        content="Hello",
        created_at=now,
    )
    d = entry.to_dict()
    restored = TranscriptEntry.from_dict(d)
    assert restored.id == entry.id
    assert restored.content == entry.content


def test_disconnect_event_roundtrip():
    evt = DisconnectEvent(timestamp="2026-01-01T00:00:00", reason="network_error")
    d = evt.to_dict()
    restored = DisconnectEvent.from_dict(d)
    assert restored.reason == "network_error"
    assert restored.reconnected is False


def test_repository_create_and_list(tmp_path):
    repo = VoiceConversationRepository(base_dir=tmp_path)
    now = datetime.now(UTC)
    conv = VoiceConversation(
        id="sess-001",
        title="Voice session sess-001",
        status="active",
        created_at=now,
        updated_at=now,
    )
    repo.create_conversation(conv)

    conversations = repo.list_conversations()
    assert len(conversations) == 1
    assert conversations[0]["id"] == "sess-001"


def test_repository_end_conversation(tmp_path):
    repo = VoiceConversationRepository(base_dir=tmp_path)
    now = datetime.now(UTC)
    conv = VoiceConversation(
        id="sess-002",
        title="Voice session sess-002",
        status="active",
        created_at=now,
        updated_at=now,
    )
    repo.create_conversation(conv)
    repo.end_conversation("sess-002", "user_ended")

    restored = repo.get_conversation("sess-002")
    assert restored is not None
    assert restored.status == "ended"
    assert restored.end_reason == "user_ended"


def test_repository_add_entries_and_title(tmp_path):
    repo = VoiceConversationRepository(base_dir=tmp_path)
    now = datetime.now(UTC)
    conv = VoiceConversation(
        id="sess-003",
        title="Voice session sess-003",
        status="active",
        created_at=now,
        updated_at=now,
    )
    repo.create_conversation(conv)

    entries = [
        TranscriptEntry(
            id="e1",
            conversation_id="sess-003",
            role="user",
            content="Hello world how are you",
            created_at=now,
        ),
    ]
    repo.add_entries("sess-003", entries)

    restored = repo.get_conversation("sess-003")
    assert restored is not None
    assert restored.title == "Hello world how are you"


def test_repository_resumption_context(tmp_path):
    repo = VoiceConversationRepository(base_dir=tmp_path)
    now = datetime.now(UTC)
    conv = VoiceConversation(
        id="sess-004",
        title="Voice session sess-004",
        status="active",
        created_at=now,
        updated_at=now,
    )
    repo.create_conversation(conv)

    entries = [
        TranscriptEntry(
            id="e1",
            conversation_id="sess-004",
            role="user",
            content="Hello",
            created_at=now,
        ),
        TranscriptEntry(
            id="e2",
            conversation_id="sess-004",
            role="assistant",
            content="Hi there!",
            created_at=now,
        ),
    ]
    repo.add_entries("sess-004", entries)

    context = repo.get_resumption_context("sess-004")
    assert len(context) == 2
    assert context[0]["type"] == "message"
    assert context[0]["role"] == "user"
    assert context[1]["role"] == "assistant"


def test_repository_amplifierd_transcript(tmp_path):
    sessions_dir = tmp_path / "sessions"
    repo = VoiceConversationRepository(
        base_dir=tmp_path / "voice", sessions_dir=sessions_dir
    )
    now = datetime.now(UTC)

    entries = [
        TranscriptEntry(
            id="e1",
            conversation_id="sess-005",
            role="user",
            content="Hello",
            created_at=now,
        ),
        TranscriptEntry(
            id="e2",
            conversation_id="sess-005",
            role="tool_call",
            content="{}",
            created_at=now,
            tool_name="delegate",
        ),
    ]
    repo.write_to_amplifierd_transcript("sess-005", entries)

    transcript_path = sessions_dir / "sess-005" / "transcript.jsonl"
    assert transcript_path.exists()
    lines = transcript_path.read_text().strip().split("\n")
    # Only user/assistant turns are written
    assert len(lines) == 1
