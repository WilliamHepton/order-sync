"""Azure Functions entry point."""

import logging

import azure.functions as func

from order_sync.settings import required
from order_sync.stripe_webhook import InvalidEvent, InvalidSignature, read_order, verify_signature

app = func.FunctionApp()


# Anonymous because Stripe cannot send a function key. The signature check protects it instead.
@app.route(route="stripe/webhook", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@app.queue_output(arg_name="message", queue_name="orders", connection="AzureWebJobsStorage")
def receive_webhook(req: func.HttpRequest, message: func.Out[str]) -> func.HttpResponse:
    payload = req.get_body()
    secret = required("STRIPE_WEBHOOK_SECRET")
    try:
        verify_signature(payload, req.headers.get("Stripe-Signature"), secret)
        order = read_order(payload)
    except InvalidSignature:
        logging.warning("Webhook rejected: invalid signature")
        return func.HttpResponse("Invalid signature", status_code=400)
    except InvalidEvent:
        logging.warning("Webhook rejected: invalid event")
        return func.HttpResponse("Invalid event", status_code=400)

    if order is None:
        return func.HttpResponse("Ignored", status_code=200)

    message.set(order.model_dump_json())
    logging.info("Queuing order order_id=%s", order.order_id)
    return func.HttpResponse("Queued", status_code=200)
