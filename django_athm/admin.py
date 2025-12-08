import json
import logging
from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from django_athm.models import Payment, PaymentLineItem, Refund, WebhookEvent
from django_athm.services.payment_service import PaymentService
from django_athm.services.webhook_processor import WebhookProcessor

logger = logging.getLogger(__name__)


class PaymentLineItemInline(admin.TabularInline):
    model = PaymentLineItem
    fields = ("name", "description", "quantity", "price", "tax", "metadata")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference_number",
        "ecommerce_id",
        "display_status_colored",
        "total",
        "transaction_date",
        "customer_name",
        "created",
    )
    list_filter = ("status", "created", "transaction_date")
    search_fields = (
        "reference_number",
        "ecommerce_id",
        "customer_name",
        "customer_phone",
        "customer_email",
        "metadata_1",
        "metadata_2",
    )
    date_hierarchy = "created"
    ordering = ["-created"]
    inlines = [PaymentLineItemInline]

    fieldsets = (
        (
            _("Transaction Information"),
            {
                "fields": (
                    "ecommerce_id",
                    "reference_number",
                    "daily_transaction_id",
                    "status",
                    "transaction_date",
                    "created",
                    "modified",
                )
            },
        ),
        (
            _("Financial Details"),
            {
                "fields": (
                    "total",
                    "subtotal",
                    "tax",
                    "fee",
                    "net_amount",
                    "total_refunded_amount",
                    "display_is_refundable",
                    "display_refundable_amount",
                )
            },
        ),
        (
            _("Customer Information"),
            {
                "fields": (
                    "customer_name",
                    "customer_phone",
                    "customer_email",
                )
            },
        ),
        (
            _("Business Information"),
            {"fields": ("business_name",)},
        ),
        (
            _("Metadata & Notes"),
            {
                "classes": ("collapse",),
                "fields": ("metadata_1", "metadata_2", "message"),
            },
        ),
    )

    readonly_fields = (
        "ecommerce_id",
        "reference_number",
        "daily_transaction_id",
        "status",
        "transaction_date",
        "created",
        "modified",
        "total",
        "subtotal",
        "tax",
        "fee",
        "net_amount",
        "total_refunded_amount",
        "customer_name",
        "customer_phone",
        "customer_email",
        "business_name",
        "display_is_refundable",
        "display_refundable_amount",
    )

    actions = ["refund_selected_payments"]

    @admin.display(description=_("Status"), ordering="status")
    def display_status_colored(self, obj: Payment) -> str:
        colors = {
            Payment.Status.COMPLETED: "green",
            Payment.Status.CANCEL: "red",
            Payment.Status.EXPIRED: "red",
            Payment.Status.CONFIRM: "orange",
            Payment.Status.OPEN: "gray",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description=_("Is Refundable"), boolean=True)
    def display_is_refundable(self, obj: Payment) -> bool:
        return obj.is_refundable

    @admin.display(description=_("Refundable Amount"))
    def display_refundable_amount(self, obj: Payment) -> str:
        return f"${obj.refundable_amount:.2f}"

    @admin.action(description=_("Refund selected payments (full refund)"))
    def refund_selected_payments(
        self, request: HttpRequest, queryset: QuerySet[Payment]
    ) -> None:
        refunded_count = 0
        error_count = 0

        for payment in queryset:
            if not payment.is_refundable:
                logger.warning(
                    f"[django-athm] Payment {payment.ecommerce_id} not refundable"
                )
                error_count += 1
                continue

            try:
                refund = PaymentService.refund(
                    payment=payment,
                    amount=None,  # Full refund
                    message="Refunded via admin action",
                )
                refunded_count += 1
                logger.info(
                    f"[django-athm] Admin refunded payment {payment.ecommerce_id} -> refund {refund.reference_number}"
                )
            except Exception as e:
                logger.exception(
                    f"[django-athm] Refund failed for {payment.ecommerce_id}: {e}"
                )
                error_count += 1

        # Display appropriate message
        if error_count == 0:
            self.message_user(
                request,
                _(f"Successfully refunded {refunded_count} payments."),
                level="success",
            )
        elif refunded_count > 0:
            self.message_user(
                request,
                _(
                    f"Refunded {refunded_count} payments with {error_count} errors. Check logs for details."
                ),
                level="warning",
            )
        else:
            self.message_user(
                request,
                _(f"Failed to refund payments: {error_count} errors occurred."),
                level="error",
            )


@admin.register(PaymentLineItem)
class PaymentLineItemAdmin(admin.ModelAdmin):
    list_display = ("transaction_link", "name", "quantity", "price", "tax")
    list_filter = ("transaction",)
    search_fields = ("transaction__reference_number", "name", "description")
    date_hierarchy = "transaction__created"

    fields = (
        "id",
        "transaction",
        "name",
        "description",
        "quantity",
        "price",
        "tax",
        "metadata",
    )
    readonly_fields = fields

    @admin.display(description=_("Transaction"))
    def transaction_link(self, obj: PaymentLineItem) -> str:
        if obj.transaction:
            url = reverse(
                "admin:django_athm_payment_change", args=[obj.transaction.ecommerce_id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.transaction)
        return "-"


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "reference_number",
        "payment_link",
        "display_amount_with_currency",
        "status",
        "transaction_date",
        "customer_name",
        "created_at",
    )
    list_filter = ("status", "transaction_date", "created_at")
    search_fields = (
        "reference_number",
        "daily_transaction_id",
        "payment__reference_number",
        "customer_name",
        "customer_phone",
        "customer_email",
    )
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            _("Refund Information"),
            {
                "fields": (
                    "id",
                    "reference_number",
                    "daily_transaction_id",
                    "status",
                    "transaction_date",
                    "created_at",
                )
            },
        ),
        (
            _("Financial Details"),
            {"fields": ("amount", "payment")},
        ),
        (
            _("Customer Information"),
            {
                "fields": (
                    "customer_name",
                    "customer_phone",
                    "customer_email",
                )
            },
        ),
        (
            _("Notes"),
            {"fields": ("message",)},
        ),
    )

    readonly_fields = (
        "id",
        "payment",
        "reference_number",
        "daily_transaction_id",
        "amount",
        "status",
        "message",
        "customer_name",
        "customer_phone",
        "customer_email",
        "transaction_date",
        "created_at",
    )

    @admin.display(description=_("Payment"))
    def payment_link(self, obj: Refund) -> str:
        if obj.payment:
            url = reverse(
                "admin:django_athm_payment_change", args=[obj.payment.ecommerce_id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.payment)
        return "-"

    @admin.display(description=_("Amount"))
    def display_amount_with_currency(self, obj: Refund) -> str:
        return f"${obj.amount:.2f}"


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "display_id_short",
        "event_type",
        "display_processed_icon",
        "transaction_link",
        "remote_ip",
        "created",
    )
    list_filter = ("event_type", "processed", "created")
    search_fields = ("id", "remote_ip", "idempotency_key")
    date_hierarchy = "created"
    ordering = ["-created"]

    fieldsets = (
        (
            _("Event Information"),
            {
                "fields": (
                    "id",
                    "idempotency_key",
                    "event_type",
                    "processed",
                    "created",
                    "modified",
                )
            },
        ),
        (
            _("Request Details"),
            {"fields": ("remote_ip",)},
        ),
        (
            _("Payload"),
            {"fields": ("payload_display",)},
        ),
        (
            _("Processing"),
            {"fields": ("transaction",)},
        ),
    )

    readonly_fields = (
        "id",
        "idempotency_key",
        "event_type",
        "remote_ip",
        "payload_display",
        "processed",
        "transaction",
        "created",
        "modified",
    )

    actions = ["reprocess_events"]

    @admin.display(description=_("ID"))
    def display_id_short(self, obj: WebhookEvent) -> str:
        return str(obj.id)[:8]

    @admin.display(description=_("Processed"), boolean=True)
    def display_processed_icon(self, obj: WebhookEvent) -> bool:
        return obj.processed

    @admin.display(description=_("Transaction"))
    def transaction_link(self, obj: WebhookEvent) -> str:
        if obj.transaction:
            url = reverse(
                "admin:django_athm_payment_change", args=[obj.transaction.ecommerce_id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.transaction)
        return "-"

    @admin.display(description=_("Payload (JSON)"))
    def payload_display(self, obj: WebhookEvent) -> str:
        try:
            formatted_json = json.dumps(obj.payload, indent=2, ensure_ascii=False)
            return format_html("<pre>{}</pre>", formatted_json)
        except Exception:
            return format_html("<pre>{}</pre>", str(obj.payload))

    @admin.action(description=_("Reprocess selected webhook events"))
    def reprocess_events(
        self, request: HttpRequest, queryset: QuerySet[WebhookEvent]
    ) -> None:
        processed_count = 0
        error_count = 0

        for event in queryset.filter(processed=False):
            try:
                WebhookProcessor.process(event)
                processed_count += 1
                logger.info(f"[django-athm] Admin reprocessed webhook event {event.id}")
            except Exception as e:
                logger.exception(
                    f"[django-athm] Reprocess failed for event {event.id}: {e}"
                )
                error_count += 1

        # Display appropriate message
        if error_count == 0 and processed_count > 0:
            self.message_user(
                request,
                _(f"Successfully reprocessed {processed_count} events."),
                level="success",
            )
        elif processed_count > 0:
            self.message_user(
                request,
                _(
                    f"Reprocessed {processed_count} events with {error_count} errors. Check logs for details."
                ),
                level="warning",
            )
        elif error_count > 0:
            self.message_user(
                request,
                _(f"Failed to reprocess events: {error_count} errors occurred."),
                level="error",
            )
        else:
            self.message_user(
                request,
                _("No unprocessed events selected."),
                level="info",
            )
