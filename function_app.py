"""Azure Functions entry point."""

import logging

import azure.functions as func

from order_sync.crm import get_crm
from order_sync.idempotency import get_store
from order_sync.settings import required
from order_sync.stripe_webhook import InvalidEvent, InvalidSignature, read_order, verify_signature
from order_sync.worker import parse_order, process_order

# These libraries log every request at INFO, which would use up the daily log cap.
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)

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


# An exception here puts the message back on the queue. After 5 tries it goes to orders-poison.
@app.queue_trigger(arg_name="msg", queue_name="orders", connection="AzureWebJobsStorage")
def process_order_message(msg: func.QueueMessage) -> None:
    order = parse_order(msg.get_body())
    try:
        process_order(order, get_store(), get_crm())
    except Exception as error:
        # The type only: an error's text might contain customer details.
        logging.warning(
            "Failed order_id=%s try=%s error=%s",
            order.order_id,
            msg.dequeue_count,
            type(error).__name__,
        )
        raise
