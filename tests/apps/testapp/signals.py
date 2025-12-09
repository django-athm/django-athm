from django.dispatch import receiver

from django_athm.signals import (
    payment_cancelled,
    payment_completed,
    payment_expired,
    refund_sent,
)


@receiver(payment_completed)
def handle_payment_completed(sender, payment, **kwargs):
    """Handle completed payments."""
    # Mark that this handler was called (for testing)
    if not hasattr(payment, "_signal_handlers_called"):
        payment._signal_handlers_called = []
    payment._signal_handlers_called.append("payment_completed")


@receiver(payment_cancelled)
def handle_payment_cancelled(sender, payment, **kwargs):
    """Handle cancelled payments."""
    if not hasattr(payment, "_signal_handlers_called"):
        payment._signal_handlers_called = []
    payment._signal_handlers_called.append("payment_cancelled")


@receiver(payment_expired)
def handle_payment_expired(sender, payment, **kwargs):
    """Handle expired payments."""
    if not hasattr(payment, "_signal_handlers_called"):
        payment._signal_handlers_called = []
    payment._signal_handlers_called.append("payment_expired")


@receiver(refund_sent)
def handle_refund_sent(sender, refund, payment, **kwargs):
    """Handle refunds sent."""
    if not hasattr(refund, "_signal_handlers_called"):
        refund._signal_handlers_called = []
    refund._signal_handlers_called.append("refund_sent")
