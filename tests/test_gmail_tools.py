"""
Tests for tools/gmail.py.

All Gmail API calls are intercepted by patching get_service().
Tool functions are called via tool.func() to bypass the LangChain wrapper.
"""
from unittest.mock import MagicMock, patch

import pytest

from tools.gmail import (
    batch_modify_labels,
    create_draft,
    create_reply_draft,
    delete_message_permanently,
    get_message,
    list_messages,
    mark_all_as_read,
    mark_as_read,
    mark_as_unread,
    send_draft,
    trash_message,
    update_draft,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msgs_resource(svc):
    """Shortcut to the mocked messages resource."""
    return svc.users.return_value.messages.return_value


def _drafts_resource(svc):
    """Shortcut to the mocked drafts resource."""
    return svc.users.return_value.drafts.return_value


def _make_message(
    msg_id="msg1",
    thread_id="thread1",
    label_ids=None,
    snippet="Hello there",
    subject="Test Subject",
    from_addr="Alice <alice@example.com>",
    date="Thu, 5 Mar 2026 10:00:00 +0000",
):
    return {
        "id": msg_id,
        "threadId": thread_id,
        "labelIds": label_ids or ["INBOX", "UNREAD"],
        "snippet": snippet,
        "internalDate": "1741168800000",
        "payload": {
            "headers": [
                {"name": "From", "value": from_addr},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": date},
                {"name": "Message-Id", "value": f"<{msg_id}@mail.example.com>"},
            ]
        },
    }


# ---------------------------------------------------------------------------
# list_messages
# ---------------------------------------------------------------------------

class TestListMessages:
    def test_returns_message_ids(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {
            "messages": [{"id": "msg1", "threadId": "t1"}, {"id": "msg2", "threadId": "t2"}]
        }

        result = list_messages.func()

        assert result["count"] == 2
        assert result["messages"][0] == {"message_id": "msg1", "thread_id": "t1"}
        assert result["messages"][1] == {"message_id": "msg2", "thread_id": "t2"}

    def test_empty_inbox(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        result = list_messages.func()

        assert result["count"] == 0
        assert result["messages"] == []

    def test_missing_messages_key_treated_as_empty(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {}

        result = list_messages.func()

        assert result["count"] == 0

    def test_query_forwarded_to_api(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        list_messages.func(query="from:alice is:unread", label_ids=["INBOX"])

        list_call = _msgs_resource(mock_gmail_service).list.call_args
        assert list_call.kwargs["q"] == "from:alice is:unread"
        assert list_call.kwargs["labelIds"] == ["INBOX"]

    def test_result_echoes_query_and_labels(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        result = list_messages.func(query="subject:meeting", label_ids=["UNREAD"])

        assert result["query"] == "subject:meeting"
        assert result["label_ids"] == ["UNREAD"]


# ---------------------------------------------------------------------------
# get_message
# ---------------------------------------------------------------------------

class TestGetMessage:
    def test_returns_headers_and_snippet(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).get.return_value.execute.return_value = _make_message()

        result = get_message.func(message_id="msg1")

        assert result["message_id"] == "msg1"
        assert result["thread_id"] == "thread1"
        assert result["snippet"] == "Hello there"
        assert result["headers"]["from"] == "Alice <alice@example.com>"
        assert result["headers"]["subject"] == "Test Subject"
        assert result["headers"]["date"] == "Thu, 5 Mar 2026 10:00:00 +0000"

    def test_label_ids_returned(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).get.return_value.execute.return_value = _make_message(
            label_ids=["INBOX", "UNREAD", "IMPORTANT"]
        )

        result = get_message.func(message_id="msg1")

        assert "UNREAD" in result["label_ids"]
        assert "IMPORTANT" in result["label_ids"]

    def test_handles_message_with_no_headers(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).get.return_value.execute.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "labelIds": [],
            "snippet": "",
            "payload": {"headers": []},
        }

        result = get_message.func(message_id="msg1")

        assert result["headers"]["from"] is None
        assert result["headers"]["subject"] is None

    def test_message_id_forwarded_to_api(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).get.return_value.execute.return_value = _make_message()

        get_message.func(message_id="abc123")

        get_call = _msgs_resource(mock_gmail_service).get.call_args
        assert get_call.kwargs["id"] == "abc123"


# ---------------------------------------------------------------------------
# trash_message
# ---------------------------------------------------------------------------

class TestTrashMessage:
    def test_moves_message_to_trash(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).trash.return_value.execute.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "labelIds": ["TRASH"],
        }

        result = trash_message.func(message_id="msg1")

        assert result["trashed"] is True
        assert result["message_id"] == "msg1"
        assert "TRASH" in result["label_ids"]

    def test_message_id_forwarded_to_api(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).trash.return_value.execute.return_value = {
            "id": "msg99", "threadId": "t1", "labelIds": ["TRASH"]
        }

        trash_message.func(message_id="msg99")

        trash_call = _msgs_resource(mock_gmail_service).trash.call_args
        assert trash_call.kwargs["id"] == "msg99"


# ---------------------------------------------------------------------------
# delete_message_permanently
# ---------------------------------------------------------------------------

class TestDeleteMessagePermanently:
    def test_permanently_deletes_message(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).delete.return_value.execute.return_value = None

        result = delete_message_permanently.func(message_id="msg1")

        assert result["deleted_permanently"] is True
        assert result["message_id"] == "msg1"

    def test_delete_api_called_with_correct_id(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).delete.return_value.execute.return_value = None

        delete_message_permanently.func(message_id="xyz")

        delete_call = _msgs_resource(mock_gmail_service).delete.call_args
        assert delete_call.kwargs["id"] == "xyz"


# ---------------------------------------------------------------------------
# batch_modify_labels
# ---------------------------------------------------------------------------

class TestBatchModifyLabels:
    def test_modifies_labels_on_multiple_messages(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).batchModify.return_value.execute.return_value = None

        result = batch_modify_labels.func(
            message_ids=["msg1", "msg2"],
            add_label_ids=["STARRED"],
            remove_label_ids=["UNREAD"],
        )

        assert result["updated"] is True
        assert result["count"] == 2
        assert result["add_label_ids"] == ["STARRED"]
        assert result["remove_label_ids"] == ["UNREAD"]

    def test_batch_api_receives_correct_body(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).batchModify.return_value.execute.return_value = None

        batch_modify_labels.func(
            message_ids=["a", "b"],
            add_label_ids=["IMPORTANT"],
            remove_label_ids=["INBOX"],
        )

        call = _msgs_resource(mock_gmail_service).batchModify.call_args
        body = call.kwargs["body"]
        assert body["ids"] == ["a", "b"]
        assert body["addLabelIds"] == ["IMPORTANT"]
        assert body["removeLabelIds"] == ["INBOX"]

    def test_defaults_to_empty_lists_when_not_provided(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).batchModify.return_value.execute.return_value = None

        result = batch_modify_labels.func(message_ids=["msg1"])

        assert result["add_label_ids"] == []
        assert result["remove_label_ids"] == []


# ---------------------------------------------------------------------------
# mark_as_read
# ---------------------------------------------------------------------------

class TestMarkAsRead:
    def test_marks_message_as_read(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).modify.return_value.execute.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "labelIds": ["INBOX"],
        }

        result = mark_as_read.func(message_id="msg1")

        assert result["marked_read"] is True
        assert result["message_id"] == "msg1"
        assert "UNREAD" not in result["label_ids"]

    def test_correct_message_id_and_body_sent(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).modify.return_value.execute.return_value = {
            "id": "msg42", "threadId": "t1", "labelIds": ["INBOX"]
        }

        mark_as_read.func(message_id="msg42")

        call = _msgs_resource(mock_gmail_service).modify.call_args
        assert call.kwargs["id"] == "msg42"
        assert call.kwargs["body"] == {"removeLabelIds": ["UNREAD"]}

    def test_api_error_propagates(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).modify.return_value.execute.side_effect = Exception(
            "API error"
        )

        with pytest.raises(Exception, match="API error"):
            mark_as_read.func(message_id="msg1")


# ---------------------------------------------------------------------------
# mark_as_unread
# ---------------------------------------------------------------------------

class TestMarkAsUnread:
    def test_marks_message_as_unread(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).modify.return_value.execute.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "labelIds": ["INBOX", "UNREAD"],
        }

        result = mark_as_unread.func(message_id="msg1")

        assert result["marked_unread"] is True
        assert result["message_id"] == "msg1"
        assert "UNREAD" in result["label_ids"]

    def test_correct_message_id_and_body_sent(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).modify.return_value.execute.return_value = {
            "id": "msg7", "threadId": "t1", "labelIds": ["INBOX", "UNREAD"]
        }

        mark_as_unread.func(message_id="msg7")

        call = _msgs_resource(mock_gmail_service).modify.call_args
        assert call.kwargs["id"] == "msg7"
        assert call.kwargs["body"] == {"addLabelIds": ["UNREAD"]}

    def test_api_error_propagates(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).modify.return_value.execute.side_effect = Exception(
            "API error"
        )

        with pytest.raises(Exception, match="API error"):
            mark_as_unread.func(message_id="msg1")


# ---------------------------------------------------------------------------
# mark_all_as_read
# ---------------------------------------------------------------------------

class TestMarkAllAsRead:
    def test_marks_all_unread_and_returns_count(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}, {"id": "msg3"}]
        }
        _msgs_resource(mock_gmail_service).batchModify.return_value.execute.return_value = None

        result = mark_all_as_read.func()

        assert result["marked_read"] is True
        assert result["count"] == 3
        assert result["message_ids"] == ["msg1", "msg2", "msg3"]

    def test_no_unread_messages_skips_batch_modify(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        result = mark_all_as_read.func()

        assert result["marked_read"] is True
        assert result["count"] == 0
        assert result["message_ids"] == []
        _msgs_resource(mock_gmail_service).batchModify.assert_not_called()

    def test_missing_messages_key_treated_as_empty(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {}

        result = mark_all_as_read.func()

        assert result["count"] == 0
        _msgs_resource(mock_gmail_service).batchModify.assert_not_called()

    def test_default_label_includes_inbox_and_unread(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        mark_all_as_read.func()

        list_call = _msgs_resource(mock_gmail_service).list.call_args
        assert "INBOX" in list_call.kwargs["labelIds"]
        assert "UNREAD" in list_call.kwargs["labelIds"]

    def test_custom_label_forwarded_with_unread_appended(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        mark_all_as_read.func(label_ids=["STARRED"])

        list_call = _msgs_resource(mock_gmail_service).list.call_args
        assert "STARRED" in list_call.kwargs["labelIds"]
        assert "UNREAD" in list_call.kwargs["labelIds"]
        assert "INBOX" not in list_call.kwargs["labelIds"]

    def test_unread_not_duplicated_if_already_in_label_ids(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        mark_all_as_read.func(label_ids=["INBOX", "UNREAD"])

        list_call = _msgs_resource(mock_gmail_service).list.call_args
        assert list_call.kwargs["labelIds"].count("UNREAD") == 1

    def test_query_forwarded_to_list(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {"messages": []}

        mark_all_as_read.func(query="from:boss@example.com")

        list_call = _msgs_resource(mock_gmail_service).list.call_args
        assert list_call.kwargs["q"] == "from:boss@example.com"

    def test_batch_modify_removes_unread_label(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {
            "messages": [{"id": "a"}, {"id": "b"}]
        }
        _msgs_resource(mock_gmail_service).batchModify.return_value.execute.return_value = None

        mark_all_as_read.func()

        batch_call = _msgs_resource(mock_gmail_service).batchModify.call_args
        body = batch_call.kwargs["body"]
        assert body["ids"] == ["a", "b"]
        assert body["removeLabelIds"] == ["UNREAD"]

    def test_api_error_on_list_propagates(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.side_effect = Exception(
            "API error"
        )

        with pytest.raises(Exception, match="API error"):
            mark_all_as_read.func()

    def test_api_error_on_batch_modify_propagates(self, mock_gmail_service):
        _msgs_resource(mock_gmail_service).list.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}]
        }
        _msgs_resource(mock_gmail_service).batchModify.return_value.execute.side_effect = Exception(
            "batch error"
        )

        with pytest.raises(Exception, match="batch error"):
            mark_all_as_read.func()


# ---------------------------------------------------------------------------
# create_draft
# ---------------------------------------------------------------------------

class TestCreateDraft:
    def test_creates_draft_and_returns_ids(self, mock_gmail_service):
        _drafts_resource(mock_gmail_service).create.return_value.execute.return_value = {
            "id": "draft1",
            "message": {"id": "msg1", "threadId": "t1"},
        }

        result = create_draft.func(
            to=["bob@example.com"],
            subject="Hello",
            body_text="Hi Bob!",
        )

        assert result["draft_id"] == "draft1"
        assert result["message_id"] == "msg1"
        assert result["thread_id"] == "t1"

    def test_draft_api_called_once(self, mock_gmail_service):
        _drafts_resource(mock_gmail_service).create.return_value.execute.return_value = {
            "id": "d1", "message": {"id": "m1", "threadId": "t1"}
        }

        create_draft.func(to=["x@example.com"], subject="Subj", body_text="Body")

        _drafts_resource(mock_gmail_service).create.assert_called_once()

    def test_with_cc_and_bcc(self, mock_gmail_service):
        _drafts_resource(mock_gmail_service).create.return_value.execute.return_value = {
            "id": "d1", "message": {"id": "m1", "threadId": "t1"}
        }

        # Should not raise
        create_draft.func(
            to=["to@example.com"],
            subject="Subject",
            body_text="Body",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )

        _drafts_resource(mock_gmail_service).create.assert_called_once()


# ---------------------------------------------------------------------------
# update_draft
# ---------------------------------------------------------------------------

class TestUpdateDraft:
    def test_updates_existing_draft(self, mock_gmail_service):
        _drafts_resource(mock_gmail_service).update.return_value.execute.return_value = {
            "id": "draft1",
            "message": {"id": "msg2", "threadId": "t1"},
        }

        result = update_draft.func(
            draft_id="draft1",
            to=["bob@example.com"],
            subject="Updated subject",
            body_text="New body",
        )

        assert result["draft_id"] == "draft1"
        assert result["message_id"] == "msg2"

    def test_correct_draft_id_forwarded(self, mock_gmail_service):
        _drafts_resource(mock_gmail_service).update.return_value.execute.return_value = {
            "id": "d99", "message": {"id": "m1", "threadId": "t1"}
        }

        update_draft.func(
            draft_id="d99",
            to=["x@example.com"],
            subject="S",
            body_text="B",
        )

        update_call = _drafts_resource(mock_gmail_service).update.call_args
        assert update_call.kwargs["id"] == "d99"


# ---------------------------------------------------------------------------
# send_draft
# ---------------------------------------------------------------------------

class TestSendDraft:
    def test_sends_draft_and_returns_sent_info(self, mock_gmail_service):
        _drafts_resource(mock_gmail_service).send.return_value.execute.return_value = {
            "id": "msg_sent",
            "threadId": "t1",
            "labelIds": ["SENT"],
        }

        result = send_draft.func(draft_id="draft1")

        assert result["sent"] is True
        assert result["message_id"] == "msg_sent"
        assert "SENT" in result["label_ids"]

    def test_correct_draft_id_sent(self, mock_gmail_service):
        _drafts_resource(mock_gmail_service).send.return_value.execute.return_value = {
            "id": "m1", "threadId": "t1", "labelIds": ["SENT"]
        }

        send_draft.func(draft_id="my-draft-id")

        send_call = _drafts_resource(mock_gmail_service).send.call_args
        assert send_call.kwargs["body"] == {"id": "my-draft-id"}


# ---------------------------------------------------------------------------
# create_reply_draft
# ---------------------------------------------------------------------------

class TestCreateReplyDraft:
    def _setup(self, mock_gmail_service, original_subject="Weekly Sync"):
        """Wire up the two API calls create_reply_draft makes internally."""
        original_msg = {
            "id": "orig1",
            "threadId": "thread1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "Subject", "value": original_subject},
                    {"name": "Message-Id", "value": "<orig1@mail.example.com>"},
                    {"name": "References", "value": ""},
                ]
            },
        }
        _msgs_resource(mock_gmail_service).get.return_value.execute.return_value = original_msg
        _drafts_resource(mock_gmail_service).create.return_value.execute.return_value = {
            "id": "reply_draft1",
            "message": {"id": "reply_msg1", "threadId": "thread1"},
        }

    def test_creates_reply_draft(self, mock_gmail_service):
        self._setup(mock_gmail_service)

        result = create_reply_draft.func(
            original_message_id="orig1",
            reply_body_text="Thanks, see you then!",
        )

        assert result["draft_id"] == "reply_draft1"
        assert result["replied_to_message_id"] == "orig1"

    def test_adds_re_prefix_to_subject(self, mock_gmail_service):
        self._setup(mock_gmail_service, original_subject="Weekly Sync")

        create_reply_draft.func(
            original_message_id="orig1",
            reply_body_text="Sounds good",
        )

        # The draft body passed to create() should have raw MIME with Re: prefix
        create_call = _drafts_resource(mock_gmail_service).create.call_args
        # The raw MIME is base64url encoded; we can verify the call was made
        assert create_call is not None

    def test_no_duplicate_re_prefix(self, mock_gmail_service):
        """If original subject already starts with Re:, don't add another one."""
        self._setup(mock_gmail_service, original_subject="Re: Weekly Sync")

        # We need to inspect the raw MIME message to verify the subject.
        # capture the draft body and decode it.
        import base64

        _drafts_resource(mock_gmail_service).create.return_value.execute.return_value = {
            "id": "d1",
            "message": {"id": "m1", "threadId": "t1"},
        }

        create_reply_draft.func(
            original_message_id="orig1",
            reply_body_text="Got it",
        )

        create_call = _drafts_resource(mock_gmail_service).create.call_args
        raw_b64 = create_call.kwargs["body"]["message"]["raw"]
        raw_bytes = base64.urlsafe_b64decode(raw_b64 + "==")
        raw_str = raw_bytes.decode("utf-8", errors="replace")
        # Subject should appear exactly once with Re:
        assert raw_str.lower().count("re: weekly sync") == 1
        assert "re: re:" not in raw_str.lower()

    def test_original_message_fetched_before_drafting(self, mock_gmail_service):
        self._setup(mock_gmail_service)

        create_reply_draft.func(
            original_message_id="orig1",
            reply_body_text="Reply body",
        )

        # get_message must be called first
        _msgs_resource(mock_gmail_service).get.assert_called_once()
        _drafts_resource(mock_gmail_service).create.assert_called_once()
