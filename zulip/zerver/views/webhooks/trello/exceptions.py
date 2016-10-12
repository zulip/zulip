class TrelloWebhookException(Exception):
    pass

class UnsupportedAction(TrelloWebhookException):
    pass

class UnknownUpdateCardAction(TrelloWebhookException):
    pass

class UnknownUpdateBoardAction(TrelloWebhookException):
    pass
