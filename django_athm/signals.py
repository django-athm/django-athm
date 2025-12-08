from django.dispatch import Signal

payment_created = Signal()  # sender=Payment, payment=instance
payment_completed = Signal()  # sender=Payment, payment=instance
payment_failed = Signal()  # sender=Payment, payment=instance
payment_expired = Signal()  # sender=Payment, payment=instance

refund_completed = Signal()  # sender=Refund, refund=instance, payment=instance
