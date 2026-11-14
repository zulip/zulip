from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string, check_int
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Afdian")
@typed_endpoint
def api_afdian_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    data = payload["data"]
    order = data["order"]

    amount = order["show_amount"].tame(check_string)
    trade_no = order["out_trade_no"].tame(check_string)
    month = order["month"].tame(check_int)
    status = order["status"].tame(check_int)

    status_text = "paid" if status == 2 else "pending"

    topic = "Afdian"
    body = f"**New Afdian order**\n- Amount: {amount}\n- Months: {month}\n- Status: {status_text}\n- Order: `{trade_no}`"

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
