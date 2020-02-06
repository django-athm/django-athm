from django.dispatch import receiver

from django_athm.signals import athm_response_received


@receiver(athm_response_received)
def received(sender):
    print("Received athm_response_received signal")
