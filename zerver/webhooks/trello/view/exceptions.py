from zerver.lib.exceptions import UnexpectedWebhookEventType

class TrelloWebhookException(UnexpectedWebhookEventType):
    def __init__(self, action_type: str) -> None:
        self.webhook_name = "Trello"
        self.action_type = action_type

class UnsupportedAction(TrelloWebhookException):
    pass

class UnknownUpdateCardAction(TrelloWebhookException):
    pass

class UnknownUpdateBoardAction(TrelloWebhookException):
    pass
