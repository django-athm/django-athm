import json
import logging
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.validators import URLValidator
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
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
        "total_refunded_amount",
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
        "metadata_1",
        "metadata_2",
        "message",
        "display_is_refundable",
        "display_refundable_amount",
    )

    actions = ["refund_selected_payments"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Payment | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Payment | None = None
    ) -> bool:
        return False

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
    ) -> TemplateResponse | None:
        refundable = [p for p in queryset if p.is_refundable]

        if request.POST.get("confirm"):
            success, errors = 0, 0
            for payment in refundable:
                try:
                    PaymentService.refund(payment)
                    success += 1
                except Exception as e:
                    logger.exception(f"[django-athm] Refund failed: {e}")
                    errors += 1
            if success:
                self.message_user(
                    request, f"Refunded {success} payment(s).", messages.SUCCESS
                )
            if errors:
                self.message_user(
                    request, f"{errors} refund(s) failed.", messages.ERROR
                )
            return None

        return TemplateResponse(
            request,
            "admin/django_athm/payment/refund_confirmation.html",
            {
                **self.admin_site.each_context(request),
                "title": _("Confirm refund"),
                "payments": refundable,
                "queryset": queryset,
                "opts": self.model._meta,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            },
        )


@admin.register(PaymentLineItem)
class PaymentLineItemAdmin(admin.ModelAdmin):
    list_display = ("transaction_link", "name", "quantity", "price", "tax")
    search_fields = ("transaction__reference_number", "name", "description")
    date_hierarchy = "transaction__created"
    ordering = ["-transaction__created"]

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

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: PaymentLineItem | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: PaymentLineItem | None = None
    ) -> bool:
        return False

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

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Refund | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Refund | None = None
    ) -> bool:
        return False

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
    change_list_template = "admin/django_athm/webhookevent/change_list.html"

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

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: WebhookEvent | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: WebhookEvent | None = None
    ) -> bool:
        return False

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
        if processed_count == 0 and error_count == 0:
            self.message_user(request, _("No unprocessed events selected."), "info")
        elif error_count == 0:
            self.message_user(
                request,
                _(f"Successfully reprocessed {processed_count} events."),
                "success",
            )
        elif processed_count == 0:
            self.message_user(
                request, _(f"Failed to reprocess: {error_count} errors."), "error"
            )
        else:
            self.message_user(
                request,
                _(f"Reprocessed {processed_count} events with {error_count} errors."),
                "warning",
            )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "install-webhooks/",
                self.admin_site.admin_view(self.install_webhooks_view),
                name="django_athm_webhookevent_install_webhooks",
            ),
        ]
        return custom_urls + urls

    def install_webhooks_view(self, request: HttpRequest) -> TemplateResponse:
        """View for installing ATH Móvil webhooks."""

        class WebhookURLForm(forms.Form):
            url = forms.URLField(
                label=_("Webhook URL"),
                validators=[URLValidator(schemes=["https"])],
                widget=forms.URLInput(attrs={"class": "vLargeTextField", "size": "60"}),
                assume_scheme="https",
            )

        if request.method == "POST":
            form = WebhookURLForm(request.POST)
            if form.is_valid():
                try:
                    client = PaymentService.get_client()
                    client.subscribe_webhook(listener_url=form.cleaned_data["url"])
                    self.message_user(
                        request, _("Webhook installed."), messages.SUCCESS
                    )
                    return HttpResponseRedirect(
                        reverse("admin:django_athm_webhookevent_changelist")
                    )
                except Exception as e:
                    logger.exception(f"[django-athm] Webhook install failed: {e}")
                    self.message_user(request, f"Failed: {e}", messages.ERROR)
        else:
            form = WebhookURLForm()

        return TemplateResponse(
            request,
            "admin/django_athm/webhookevent/install_webhooks.html",
            {
                **self.admin_site.each_context(request),
                "title": _("Install Webhooks"),
                "opts": self.model._meta,
                "form": form,
            },
        )
