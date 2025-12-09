from django.dispatch import Signal

# Webhook-triggered signals aligned with ATH Móvil event names
payment_completed = Signal()  # sender=Payment, payment=instance
payment_cancelled = Signal()  # sender=Payment, payment=instance
payment_expired = Signal()  # sender=Payment, payment=instance

refund_sent = Signal()  # sender=Refund, refund=instance, payment=instance
