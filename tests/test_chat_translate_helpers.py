import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import (
    build_chat_translate_prompt,
    build_models_url,
    build_reduced_context_window,
    normalize_models_response,
    split_bulk_paste_into_messages,
    strip_markdown_fence,
)


def test_build_reduced_context_window_includes_targets_and_prior_messages():
    messages = [
        {"id": "m1", "role": "role_a", "content": "A1"},
        {"id": "m2", "role": "role_b", "content": "B1"},
        {"id": "m3", "role": "role_a", "content": "A2"},
        {"id": "m4", "role": "role_b", "content": "B2"},
        {"id": "m5", "role": "role_a", "content": "A3"},
        {"id": "m6", "role": "role_b", "content": "B3"},
    ]

    result = build_reduced_context_window(
        messages=messages,
        message_ids_to_translate=["m6"],
        prior_limit=3,
    )

    assert [item["id"] for item in result] == ["m3", "m4", "m5", "m6"]


def test_build_chat_translate_prompt_mentions_target_language_and_ids():
    prompt = build_chat_translate_prompt(
        target_language="Vietnamese",
        context_messages=[
            {"id": "m1", "role": "role_a", "content": "Hello"},
            {"id": "m2", "role": "role_b", "content": "Xin chao"},
        ],
        message_ids_to_translate=["m2"],
    )

    assert "Vietnamese" in prompt
    assert "m2" in prompt
    assert "role_b" in prompt


def test_split_bulk_paste_into_messages_uses_blank_lines():
    messages = split_bulk_paste_into_messages(
        text="first message\n\nsecond message\n\n\nthird message",
        role="role_a",
        id_prefix="bulk",
    )

    assert [item["id"] for item in messages] == ["bulk-1", "bulk-2", "bulk-3"]
    assert [item["content"] for item in messages] == [
        "first message",
        "second message",
        "third message",
    ]


def test_split_bulk_paste_into_messages_supports_windows_newlines():
    messages = split_bulk_paste_into_messages(
        text="first message\r\n\r\nsecond message\r\n \r\nthird message",
        role="role_a",
        id_prefix="bulk",
    )

    assert [item["content"] for item in messages] == [
        "first message",
        "second message",
        "third message",
    ]


def test_build_reduced_context_window_raises_for_unknown_message_id():
    messages = [{"id": "m1", "role": "role_a", "content": "Hello"}]

    with pytest.raises(ValueError):
        build_reduced_context_window(
            messages=messages,
            message_ids_to_translate=["missing"],
            prior_limit=5,
        )


def test_build_reduced_context_window_raises_for_non_contiguous_targets():
    messages = [
        {"id": "m1", "role": "role_a", "content": "one"},
        {"id": "m2", "role": "role_b", "content": "two"},
        {"id": "m3", "role": "role_a", "content": "three"},
    ]

    with pytest.raises(ValueError):
        build_reduced_context_window(
            messages=messages,
            message_ids_to_translate=["m1", "m3"],
            prior_limit=2,
        )


def test_split_bulk_paste_into_messages_discards_empty_segments():
    messages = split_bulk_paste_into_messages(
        text="\n\nfirst\n\n   \n\nsecond\n\n",
        role="role_b",
        id_prefix="paste",
    )

    assert messages == [
        {"id": "paste-1", "role": "role_b", "content": "first"},
        {"id": "paste-2", "role": "role_b", "content": "second"},
    ]


def test_build_reduced_context_window_keeps_contiguous_slice_for_multiple_targets():
    messages = [
        {"id": "m1", "role": "role_a", "content": "one"},
        {"id": "m2", "role": "role_b", "content": "two"},
        {"id": "m3", "role": "role_a", "content": "three"},
        {"id": "m4", "role": "role_b", "content": "four"},
        {"id": "m5", "role": "role_a", "content": "five"},
    ]

    result = build_reduced_context_window(
        messages=messages,
        message_ids_to_translate=["m4", "m5"],
        prior_limit=2,
    )

    assert [item["id"] for item in result] == ["m2", "m3", "m4", "m5"]


def test_build_models_url_replaces_chat_completions_suffix():
    assert build_models_url("http://localhost:8045/v1/chat/completions") == "http://localhost:8045/v1/models"


def test_build_models_url_handles_trailing_slash():
    assert build_models_url("http://localhost:8045/v1/chat/completions/") == "http://localhost:8045/v1/models"


def test_build_models_url_handles_v1_base():
    assert build_models_url("http://localhost:8045/v1") == "http://localhost:8045/v1/models"
    assert build_models_url("http://localhost:8045/v1/") == "http://localhost:8045/v1/models"


def test_build_models_url_rejects_unsupported_url():
    with pytest.raises(ValueError):
        build_models_url("http://localhost:8045/unsupported")


def test_normalize_models_response_returns_id_and_name():
    assert normalize_models_response({"data": [{"id": "gemini-3.8-flash-high"}]}) == [
        {"id": "gemini-3.8-flash-high", "name": "gemini-3.8-flash-high"}
    ]


def test_normalize_models_response_rejects_invalid_data():
    with pytest.raises(ValueError):
        normalize_models_response({"data": [{"name": "missing-id"}]})
    with pytest.raises(ValueError):
        normalize_models_response({"data": []})
    with pytest.raises(ValueError):
        normalize_models_response({})
    with pytest.raises(ValueError):
        normalize_models_response({"data": [{"id": ""}]})


def test_build_chat_translate_prompt_with_verify_mentions_back_translation_and_vietnamese():
    prompt = build_chat_translate_prompt(
        target_language="English",
        context_messages=[{"id": "m1", "role": "role_a", "content": "Xin chào"}],
        message_ids_to_translate=["m1"],
        verify_back_translation=True,
    )
    assert "back_translated_text" in prompt
    assert "Vietnamese" in prompt


def test_strip_markdown_fence_removes_json_fence():
    assert strip_markdown_fence('```json\n{"key": "value"}\n```') == '{"key": "value"}'


def test_strip_markdown_fence_removes_generic_fence():
    assert strip_markdown_fence('```\n{"key": "value"}\n```') == '{"key": "value"}'


def test_strip_markdown_fence_leaves_unfenced_content_intact():
    assert strip_markdown_fence('{"key": "value"}') == '{"key": "value"}'


def test_strip_markdown_fence_handles_surrounding_whitespace():
    assert strip_markdown_fence('   \n```json\n{"key": "value"}\n```\n  ') == '{"key": "value"}'


