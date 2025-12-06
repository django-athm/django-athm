import logging

from django.contrib import admin
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from athm.exceptions import ATHMovilError

from . import models
from .client import ATHMClient

logger = logging.getLogger(__name__)


class ATHM_ItemInline(admin.TabularInline):
    model = models.ATHM_Item
    extra = 0
    readonly_fields = ("id",)
    fields = ("name", "description", "quantity", "price", "tax", "metadata")


@admin.register(models.ATHM_Transaction)
class ATHM_TransactionAdmin(admin.ModelAdmin):
    actions = ["refund_action", "sync_action", "configure_webhook_action"]
    date_hierarchy = "created"
    list_display = (
        "reference_number",
        "ecommerce_id",
        "status",
        "total",
        "created",
        "customer_name",
    )
    list_filter = ("status", "created", "date")
    readonly_fields = (
        "id",
        "reference_number",
        "ecommerce_id",
        "daily_transaction_id",
        "refunded_amount",
        "fee",
        "net_amount",
        "date",
        "created",
        "modified",
        "is_refundable",
    )
    search_fields = (
        "reference_number",
        "ecommerce_id",
        "customer_name",
        "customer_phone",
        "metadata_1",
        "metadata_2",
    )
    inlines = [ATHM_ItemInline]
    fieldsets = (
        (
            _("Transaction Info"),
            {
                "fields": (
                    "id",
                    "reference_number",
                    "ecommerce_id",
                    "daily_transaction_id",
                    "status",
                    "date",
                    "created",
                    "modified",
                )
            },
        ),
        (
            _("Amounts"),
            {
                "fields": (
                    "total",
                    "subtotal",
                    "tax",
                    "fee",
                    "net_amount",
                    "refunded_amount",
                    "is_refundable",
                )
            },
        ),
        (
            _("Customer Info"),
            {"fields": ("client", "customer_name", "customer_phone")},
        ),
        (
            _("Business Info"),
            {"fields": ("business_name",)},
        ),
        (
            _("Metadata"),
            {
                "fields": ("metadata_1", "metadata_2", "message"),
                "classes": ("collapse",),
            },
        ),
    )

    def refund_action(self, request, queryset):
        """Refund selected transactions."""
        refunded_count = 0
        error_count = 0
        client = ATHMClient()

        for transaction in queryset:
            # Skip non-refundable transactions
            if not transaction.is_refundable:
                logger.warning(
                    "[django_athm:admin:refund:not_refundable]",
                    extra={"transaction_id": str(transaction.id)},
                )
                error_count += 1
                continue

            try:
                # Use client to refund
                client.refund_payment(transaction.reference_number)
                transaction.status = models.ATHM_Transaction.Status.REFUNDED
                transaction.refunded_amount = transaction.total
                transaction.save(update_fields=["status", "refunded_amount", "modified"])

                refunded_count += 1
                logger.info(
                    "[django_athm:admin:refund:success]",
                    extra={"transaction_id": str(transaction.id)},
                )

            except ATHMovilError as err:
                logger.exception(
                    "[django_athm:admin:refund:error]",
                    extra={"transaction_id": str(transaction.id), "error": str(err)},
                )
                error_count += 1

        # Report results
        if error_count == 0:
            self.message_user(
                request,
                _(f"Successfully refunded {refunded_count} transactions."),
                level="success",
            )
        elif refunded_count > 0:
            self.message_user(
                request,
                _(
                    f"Refunded {refunded_count} transactions with {error_count} errors."
                ),
                level="warning",
            )
        else:
            self.message_user(
                request,
                _(f"Failed to refund transactions: {error_count} errors occurred."),
                level="error",
            )

    refund_action.short_description = _("Refund selected transactions")

    def sync_action(self, request, queryset):
        """Sync transaction status from ATH Móvil API."""
        synced_count = 0
        error_count = 0
        client = ATHMClient()

        for transaction in queryset:
            if not transaction.ecommerce_id:
                logger.warning(
                    "[django_athm:admin:sync:no_ecommerce_id]",
                    extra={"transaction_id": str(transaction.id)},
                )
                error_count += 1
                continue

            try:
                # Check payment status via API
                api_data = client.check_payment_status(transaction.ecommerce_id)

                # Update status
                if "status" in api_data:
                    from django_athm.webhooks import _map_transaction_status

                    new_status = _map_transaction_status(api_data["status"])
                    if transaction.status != new_status:
                        transaction.status = new_status
                        transaction.save(update_fields=["status", "modified"])
                        synced_count += 1
                        logger.info(
                            "[django_athm:admin:sync:success]",
                            extra={
                                "transaction_id": str(transaction.id),
                                "new_status": new_status,
                            },
                        )

            except ATHMovilError as err:
                logger.exception(
                    "[django_athm:admin:sync:error]",
                    extra={"transaction_id": str(transaction.id), "error": str(err)},
                )
                error_count += 1

        # Report results
        if error_count == 0:
            self.message_user(
                request,
                _(f"Successfully synced {synced_count} transactions."),
                level="success",
            )
        elif synced_count > 0:
            self.message_user(
                request,
                _(f"Synced {synced_count} transactions with {error_count} errors."),
                level="warning",
            )
        else:
            self.message_user(
                request,
                _(f"Failed to sync transactions: {error_count} errors occurred."),
                level="error",
            )

    sync_action.short_description = _("Sync status from ATH Móvil API")

    def configure_webhook_action(self, request, queryset):
        """Configure webhook URL with ATH Móvil."""
        # Build webhook URL
        current_site = get_current_site(request)
        protocol = "https" if request.is_secure() else "http"
        webhook_path = reverse("django_athm:athm_webhook")
        webhook_url = f"{protocol}://{current_site.domain}{webhook_path}"

        try:
            client = ATHMClient()
            response = client.subscribe_webhook(
                webhook_url=webhook_url,
                ecommerce_payment=True,
                ecommerce_refund=True,
                ecommerce_cancel=True,
                ecommerce_expire=True,
            )

            self.message_user(
                request,
                _(f"Successfully configured webhook: {webhook_url}"),
                level="success",
            )
            logger.info(
                "[django_athm:admin:webhook:configured]",
                extra={"webhook_url": webhook_url, "response": response},
            )

        except ATHMovilError as err:
            self.message_user(
                request,
                _(f"Failed to configure webhook: {err}"),
                level="error",
            )
            logger.exception(
                "[django_athm:admin:webhook:error]",
                extra={"webhook_url": webhook_url, "error": str(err)},
            )

    configure_webhook_action.short_description = _("Configure ATH Móvil webhook URL")


@admin.register(models.ATHM_Item)
class ATHM_ItemAdmin(admin.ModelAdmin):
    date_hierarchy = "transaction__created"
    list_display = ("transaction", "name", "quantity", "price")
    list_filter = ("transaction",)
    search_fields = ("transaction__reference_number", "name", "description")
    readonly_fields = ("id",)


@admin.register(models.ATHM_WebhookEvent)
class ATHM_WebhookEventAdmin(admin.ModelAdmin):
    date_hierarchy = "created"
    list_display = (
        "id",
        "event_type",
        "transaction_status",
        "valid",
        "processed",
        "created",
        "transaction_link",
    )
    list_filter = ("valid", "processed", "event_type", "created")
    readonly_fields = (
        "id",
        "remote_ip",
        "headers",
        "body",
        "valid",
        "processed",
        "event_type",
        "transaction_status",
        "exception",
        "traceback",
        "transaction",
        "created",
        "modified",
    )
    search_fields = ("id", "remote_ip", "body", "exception")
    fieldsets = (
        (
            _("Event Info"),
            {
                "fields": (
                    "id",
                    "event_type",
                    "transaction_status",
                    "valid",
                    "processed",
                    "created",
                    "modified",
                )
            },
        ),
        (
            _("Request Details"),
            {"fields": ("remote_ip", "headers", "body")},
        ),
        (
            _("Processing"),
            {
                "fields": ("transaction", "exception", "traceback"),
                "classes": ("collapse",),
            },
        ),
    )

    def transaction_link(self, obj):
        """Display link to associated transaction."""
        if obj.transaction:
            url = reverse(
                "admin:django_athm_athm_transaction_change",
                args=[obj.transaction.id],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.transaction.reference_number or obj.transaction.ecommerce_id,
            )
        return "-"

    transaction_link.short_description = _("Transaction")
