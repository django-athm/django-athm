import pytest
from django.urls import reverse

from django_athm.models import ATHM_Item, ATHM_Transaction
from django_athm.views import default_callback


class TestDefaultCallbackView:
    @pytest.mark.django_db
    def test_callback_view_with_data(self, rf):
        data = {
            "status": "completed",
            "referenceNumber": "33908215-4028f9e06fd3c5c1016fdef4714a369a",
            "date": "2020-01-25 19:05:53.0",
            "refundedAmount": "1.00",
            "total": "1.00",
            "tax": "0.00",
            "subtotal": "0.00",
            "metadata1": "Metadata 1",
            "metadata2": "Metadata 2",
            "items": '[{"name":"First Item","description":"This is a description.","quantity":"1","price":"1.00","tax":"1.00","metadata":"metadata test"}]',
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201

        assert ATHM_Transaction.objects.count() == 1
        transaction = ATHM_Transaction.objects.first()
        assert transaction.status == "COMPLETED"
        assert (
            transaction.reference_number == "33908215-4028f9e06fd3c5c1016fdef4714a369a"
        )
        assert transaction.total == 1.0

        assert ATHM_Item.objects.count() == 1
        item = ATHM_Item.objects.first()
        assert item.name == "First Item"
        assert item.price == 1.0

    @pytest.mark.django_db
    def test_callback_view_with_minimal_data(self, rf):
        data = {
            "status": "completed",
            "referenceNumber": "33908215-4028f9e06fd3c5c1016fdef4714a369a",
            "date": "2020-01-25 19:05:53.0",
            "refundedAmount": "1.00",
            "total": "1.0",
            "tax": "",
            "subtotal": "",
            "metadata1": "",
            "metadata2": "",
            "items": '[{"name":"First Item","description":"This is a description.","quantity":"1","price":"1.00","tax":"1.00","metadata":"metadata test"}]',
        }

        url = reverse("django_athm:athm_callback")
        request = rf.post(url, data=data)
        response = default_callback(request)

        assert response.status_code == 201

        assert ATHM_Transaction.objects.count() == 1
        transaction = ATHM_Transaction.objects.first()
        assert transaction.status == "COMPLETED"
        assert (
            transaction.reference_number == "33908215-4028f9e06fd3c5c1016fdef4714a369a"
        )
        assert transaction.total == 1.0

        assert ATHM_Item.objects.count() == 1
        item = ATHM_Item.objects.first()
        assert item.name == "First Item"
        assert item.price == 1.0
