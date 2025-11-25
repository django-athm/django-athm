import django.dispatch

# General signal
athm_response_received = django.dispatch.Signal()

# Status specific signals
athm_completed_response = django.dispatch.Signal()
athm_cancelled_response = django.dispatch.Signal()
athm_expired_response = django.dispatch.Signal()
