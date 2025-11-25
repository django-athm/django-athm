import pytest
from django.template import Context, Template

from django_athm import models, signals


class TestTemplateTagSignals:
    """Test signals dispatched from the athm_response_signal template tag."""

    def test_cancelled_signal_dispatched(self):
        """Test that cancelled signal is dispatched from template tag."""
        received = {"called": False, "sender": None}

        def handler(sender, **kwargs):
            received["called"] = True
            received["sender"] = sender

        signals.athm_cancelled_response.connect(handler)
        try:
            template = Template(
                "{% load athm_response_signal %}{% athm_response_signal 'CANCELLED' %}"
            )
            template.render(context=Context())
            assert received["called"] is True
            assert received["sender"] == "django_athm"
        finally:
            signals.athm_cancelled_response.disconnect(handler)

    def test_expired_signal_dispatched(self):
        """Test that expired signal is dispatched from template tag."""
        received = {"called": False, "sender": None}

        def handler(sender, **kwargs):
            received["called"] = True
            received["sender"] = sender

        signals.athm_expired_response.connect(handler)
        try:
            template = Template(
                "{% load athm_response_signal %}{% athm_response_signal 'EXPIRED' %}"
            )
            template.render(context=Context())
            assert received["called"] is True
            assert received["sender"] == "django_athm"
        finally:
            signals.athm_expired_response.disconnect(handler)

    def test_completed_signal_dispatched(self):
        """Test that completed signal is dispatched from template tag."""
        received = {"called": False, "sender": None}

        def handler(sender, **kwargs):
            received["called"] = True
            received["sender"] = sender

        signals.athm_completed_response.connect(handler)
        try:
            template = Template(
                "{% load athm_response_signal %}{% athm_response_signal 'COMPLETED' %}"
            )
            template.render(context=Context())
            assert received["called"] is True
            assert received["sender"] == "django_athm"
        finally:
            signals.athm_completed_response.disconnect(handler)

    def test_general_response_signal_always_dispatched(self):
        """Test that general response signal is always dispatched."""
        received = {"called": False}

        def handler(sender, **kwargs):
            received["called"] = True

        signals.athm_response_received.connect(handler)
        try:
            template = Template(
                "{% load athm_response_signal %}{% athm_response_signal 'COMPLETED' %}"
            )
            template.render(context=Context())
            assert received["called"] is True
        finally:
            signals.athm_response_received.disconnect(handler)


@pytest.mark.django_db
class TestViewSignalDispatch:
    """Test signals dispatched from the callback view."""

    def test_completed_signal_dispatched_on_completed_status(self, rf):
        """Test that completed signal is dispatched when transaction is completed."""
        received = {"called": False, "transaction": None}

        def handler(sender, transaction, **kwargs):
            received["called"] = True
            received["transaction"] = transaction

        signals.athm_completed_response.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={
                    "referenceNumber": "test-completed-signal",
                    "total": "100.00",
                    "ecommerceStatus": "COMPLETED",
                },
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["called"] is True
            assert received["transaction"].reference_number == "test-completed-signal"
        finally:
            signals.athm_completed_response.disconnect(handler)

    def test_cancelled_signal_dispatched_on_cancel_status(self, rf):
        """Test that cancelled signal is dispatched when transaction is cancelled."""
        received = {"called": False, "transaction": None}

        def handler(sender, transaction, **kwargs):
            received["called"] = True
            received["transaction"] = transaction

        signals.athm_cancelled_response.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={
                    "referenceNumber": "test-cancelled-signal",
                    "total": "100.00",
                    "ecommerceStatus": "CANCEL",
                },
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["called"] is True
            assert received["transaction"].reference_number == "test-cancelled-signal"
        finally:
            signals.athm_cancelled_response.disconnect(handler)

    def test_general_response_signal_always_dispatched(self, rf):
        """Test that general response signal is always dispatched from view."""
        received = {"called": False, "transaction": None}

        def handler(sender, transaction, **kwargs):
            received["called"] = True
            received["transaction"] = transaction

        signals.athm_response_received.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={
                    "referenceNumber": "test-general-signal",
                    "total": "50.00",
                },
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["called"] is True
            assert received["transaction"].reference_number == "test-general-signal"
        finally:
            signals.athm_response_received.disconnect(handler)

    def test_signal_contains_transaction_object(self, rf):
        """Test that signal provides the transaction object."""
        received = {"transaction": None}

        def handler(sender, transaction, **kwargs):
            received["transaction"] = transaction

        signals.athm_response_received.connect(handler)
        try:
            from django_athm.views import default_callback

            request = rf.post(
                "/callback/",
                data={
                    "referenceNumber": "test-txn-object",
                    "total": "75.00",
                    "ecommerceStatus": "COMPLETED",
                },
            )
            response = default_callback(request)
            assert response.status_code == 201
            assert received["transaction"] is not None
            assert isinstance(received["transaction"], models.ATHM_Transaction)
            assert received["transaction"].total == 75.00
        finally:
            signals.athm_response_received.disconnect(handler)
