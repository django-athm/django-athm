import json
import logging

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from django_athm.models import Client, Payment, Refund, WebhookEvent
from django_athm.services.payment_service import PaymentService
from django_athm.services.webhook_processor import WebhookProcessor
from django_athm.utils import get_webhook_url, validate_webhook_url

logger = logging.getLogger(__name__)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "ecommerce_id",
        "reference_number",
        "display_status_colored",
        "total",
        "total_refunded_amount",
        "transaction_date",
        "customer_name",
        "created_at",
    )
    list_display_links = ("reference_number",)
    list_filter = ("status", "created_at", "transaction_date")
    search_fields = (
        "reference_number",
        "ecommerce_id",
        "business_name",
        "daily_transaction_id",
        "customer_name",
        "customer_phone",
        "customer_email",
        "metadata_1",
        "metadata_2",
    )
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

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
                    "created_at",
                    "updated_at",
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
                ),
                "classes": ("wide",),
            },
        ),
        (
            _("Customer & Business Information"),
            {
                "fields": (
                    "client_link",
                    "customer_name",
                    "customer_phone",
                    "customer_email",
                    "business_name",
                )
            },
        ),
        (
            _("Metadata & Notes"),
            {
                "classes": ("collapse",),
                "fields": ("metadata_1", "metadata_2", "message"),
            },
        ),
        (
            _("Related Webhooks"),
            {
                "classes": ("collapse",),
                "fields": ("webhooks_timeline",),
            },
        ),
    )

    readonly_fields = (
        "ecommerce_id",
        "reference_number",
        "daily_transaction_id",
        "status",
        "transaction_date",
        "created_at",
        "updated_at",
        "total",
        "subtotal",
        "tax",
        "fee",
        "net_amount",
        "total_refunded_amount",
        "client_link",
        "customer_name",
        "customer_phone",
        "customer_email",
        "business_name",
        "metadata_1",
        "metadata_2",
        "message",
        "display_is_refundable",
        "display_refundable_amount",
        "webhooks_timeline",
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

    @admin.display(description=_("Webhook Events"))
    def webhooks_timeline(self, obj: Payment) -> str:
        if not obj.pk:
            return "-"

        webhooks = WebhookEvent.objects.filter(payment=obj).order_by("created_at")

        if not webhooks.exists():
            return _("No webhook events")

        items = []
        for webhook in webhooks:
            # Link to webhook detail
            url = reverse("admin:django_athm_webhookevent_change", args=[webhook.pk])

            # Processed status
            status = _("Processed") if webhook.processed else _("Pending")

            items.append(
                (
                    url,
                    webhook.get_event_type_display(),
                    status,
                    webhook.created_at.strftime("%Y-%m-%d %H:%M"),
                )
            )

        list_items = format_html_join(
            "",
            '<li><a href="{}">{}</a> ({}) - {}</li>',
            items,
        )
        return format_html("<ul>{}</ul>", list_items)

    @admin.display(description=_("Client"))
    def client_link(self, obj: Payment) -> str:
        if obj.client:
            url = reverse("admin:django_athm_client_change", args=[obj.client.pk])
            return format_html('<a href="{}">{}</a>', url, obj.client)
        return "-"

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
                    logger.exception("[django-athm] Refund failed: %s", e)
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
    list_display_links = ("reference_number",)
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
                    "client_link",
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
        "client_link",
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

    @admin.display(description=_("Client"))
    def client_link(self, obj: Refund) -> str:
        if obj.client:
            url = reverse("admin:django_athm_client_change", args=[obj.client.pk])
            return format_html('<a href="{}">{}</a>', url, obj.client)
        return "-"

    @admin.display(description=_("Amount"))
    def display_amount_with_currency(self, obj: Refund) -> str:
        return f"${obj.amount:.2f}"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Refund]:
        qs = super().get_queryset(request)
        return qs.select_related("payment", "client")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_type",
        "display_processed_icon",
        "payment_link",
        "refund_link",
        "remote_ip",
        "created_at",
    )
    list_display_links = ("id",)
    list_filter = ("event_type", "processed", "created_at")
    search_fields = (
        "id",
        "payment__reference_number",
        "payment__ecommerce_id",
        "refund__reference_number",
        "remote_ip",
        "idempotency_key",
    )
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
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
                    "created_at",
                    "updated_at",
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
            _("Associations"),
            {"fields": ("payment", "refund")},
        ),
    )

    readonly_fields = (
        "id",
        "idempotency_key",
        "event_type",
        "remote_ip",
        "payload_display",
        "processed",
        "payment",
        "refund",
        "created_at",
        "updated_at",
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

    @admin.display(description=_("Processed"), boolean=True)
    def display_processed_icon(self, obj: WebhookEvent) -> bool:
        return obj.processed

    @admin.display(description=_("Payment"))
    def payment_link(self, obj: WebhookEvent) -> str:
        if obj.payment:
            url = reverse(
                "admin:django_athm_payment_change", args=[obj.payment.ecommerce_id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.payment)
        return "-"

    @admin.display(description=_("Refund"))
    def refund_link(self, obj: WebhookEvent) -> str:
        if obj.refund:
            url = reverse("admin:django_athm_refund_change", args=[obj.refund.pk])
            return format_html('<a href="{}">{}</a>', url, obj.refund.reference_number)
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
    ) -> TemplateResponse | None:
        unprocessed = queryset.filter(processed=False)

        if not unprocessed.exists():
            self.message_user(
                request, _("No unprocessed events selected."), messages.INFO
            )
            return None

        # Show confirmation page first
        if not request.POST.get("confirm"):
            return TemplateResponse(
                request,
                "admin/django_athm/webhookevent/reprocess_confirmation.html",
                {
                    **self.admin_site.each_context(request),
                    "title": _("Confirm reprocessing"),
                    "webhooks": unprocessed,
                    "queryset": queryset,
                    "opts": self.model._meta,
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                },
            )

        # Execute reprocessing
        processed_count = 0
        error_count = 0

        for event in unprocessed:
            try:
                WebhookProcessor.process(event)
                processed_count += 1
                logger.info(
                    "[django-athm] Admin reprocessed webhook event %s", event.id
                )
            except Exception as e:
                logger.exception(
                    "[django-athm] Reprocess failed for event %s: %s", event.id, e
                )
                error_count += 1

        # Display appropriate message
        if error_count == 0:
            self.message_user(
                request,
                _(f"Successfully reprocessed {processed_count} events."),
                messages.SUCCESS,
            )
        elif processed_count == 0:
            self.message_user(
                request,
                _(f"Failed to reprocess: {error_count} errors."),
                messages.ERROR,
            )
        else:
            self.message_user(
                request,
                _(f"Reprocessed {processed_count} events with {error_count} errors."),
                messages.WARNING,
            )

        return None

    def get_queryset(self, request: HttpRequest) -> QuerySet[WebhookEvent]:
        qs = super().get_queryset(request)
        return qs.select_related("payment", "refund")

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

    def install_webhooks_view(
        self, request: HttpRequest
    ) -> TemplateResponse | HttpResponseRedirect:
        """Install webhook with auto-detected URL."""
        # Auto-detect URL
        try:
            initial_url = get_webhook_url(request=request)
        except DjangoValidationError:
            initial_url = ""

        class WebhookURLForm(forms.Form):
            url = forms.URLField(
                label=_("Webhook URL"),
                help_text=_("Auto-detected from current request. Must use HTTPS."),
                assume_scheme="https",
                widget=forms.URLInput(
                    attrs={
                        "class": "vURLField",
                        "size": "80",
                    }
                ),
            )

            def clean_url(self):
                return validate_webhook_url(self.cleaned_data["url"])

        if request.method == "POST":
            form = WebhookURLForm(request.POST)
            if form.is_valid():
                try:
                    client = PaymentService.get_client()
                    client.subscribe_webhook(listener_url=form.cleaned_data["url"])
                    self.message_user(request, _("Webhook installed"), messages.SUCCESS)
                    return HttpResponseRedirect(
                        reverse("admin:django_athm_webhookevent_changelist")
                    )
                except Exception as e:
                    logger.exception("[django-athm] Webhook install failed: %s", e)
                    self.message_user(request, f"Failed: {e}", messages.ERROR)
        else:
            form = WebhookURLForm(initial={"url": initial_url})

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


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "name",
        "email",
        "payment_count",
        "refund_count",
        "created_at",
    )
    list_display_links = ("phone_number",)
    list_filter = ("created_at", "updated_at")
    search_fields = ("phone_number", "name", "email")
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            _("Client Information"),
            {
                "fields": (
                    "id",
                    "phone_number",
                    "name",
                    "email",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            _("Activity Summary"),
            {"fields": ("payment_count", "refund_count")},
        ),
    )

    readonly_fields = (
        "id",
        "phone_number",
        "name",
        "email",
        "created_at",
        "updated_at",
        "payment_count",
        "refund_count",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Client | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Client | None = None
    ) -> bool:
        return False

    @admin.display(description=_("Payments"))
    def payment_count(self, obj: Client) -> int:
        if not obj.pk:
            return 0
        return obj.payments.count()

    @admin.display(description=_("Refunds"))
    def refund_count(self, obj: Client) -> int:
        if not obj.pk:
            return 0
        return obj.refunds.count()

    def get_queryset(self, request: HttpRequest) -> QuerySet[Client]:
        qs = super().get_queryset(request)
        return qs.prefetch_related("payments", "refunds")
