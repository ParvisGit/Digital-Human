from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from Banking_agent.app.Schemas.chat_history import ChatHistory


class MongoChatHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str):
        self.session_id = session_id

    def add_message(self, message):
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        ChatHistory(
            session_id=self.session_id,
            role=role,
            content=message.content
        ).save()

    @property
    def messages(self):
        records = (
            ChatHistory.objects(session_id=self.session_id)
            .order_by("timestamp")
        )

        messages = []
        for r in records:
            if r.role == "user":
                messages.append(HumanMessage(content=r.content))
            else:
                messages.append(AIMessage(content=r.content))
        return messages

    def clear(self):
        ChatHistory.objects(session_id=self.session_id).delete()


def get_chat_history(session_id: str):
    return MongoChatHistory(session_id)


def normalize_messages(history):
    if history is None:
        return []
    if hasattr(history, "messages"):
        return list(history.messages)
    if isinstance(history, list):
        return history
    raise TypeError(f"Unsupported history type: {type(history)}")
