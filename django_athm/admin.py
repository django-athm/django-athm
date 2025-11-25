import logging

from django.contrib import admin

from . import models

logger = logging.getLogger(__name__)


class ATHM_ItemInline(admin.TabularInline):
    model = models.ATHM_Item
    extra = 0
    readonly_fields = ("id",)
    fields = ("name", "description", "quantity", "price", "tax", "metadata")


@admin.register(models.ATHM_Transaction)
class ATHM_TransactionAdmin(admin.ModelAdmin):
    actions = ["refund", "sync"]
    date_hierarchy = "date"
    list_display = ("reference_number", "date", "status", "total", "client")
    list_filter = ("status", "date")
    readonly_fields = (
        "id",
        "ecommerce_id",
        "reference_number",
        "refunded_amount",
        "fee",
        "net_amount",
        "date",
    )
    search_fields = ("reference_number", "ecommerce_id", "customer_name")
    inlines = [ATHM_ItemInline]
    fieldsets = (
        (
            "Transaction Info",
            {
                "fields": (
                    "id",
                    "reference_number",
                    "ecommerce_id",
                    "status",
                    "date",
                )
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "total",
                    "subtotal",
                    "tax",
                    "fee",
                    "net_amount",
                    "refunded_amount",
                )
            },
        ),
        (
            "Customer Info",
            {"fields": ("client", "customer_name", "customer_phone")},
        ),
        (
            "Metadata",
            {
                "fields": ("metadata_1", "metadata_2", "message"),
                "classes": ("collapse",),
            },
        ),
    )

    def refund(self, request, queryset):
        try:
            for transaction in queryset:
                models.ATHM_Transaction.refund(transaction)
                logger.debug(
                    "[django_athm:refund success]",
                    extra={"transaction": transaction.id},
                )

            self.message_user(
                request, f"Successfully refunded {queryset.count()} transactions!"
            )
        except Exception as err:
            self.message_user(request, f"An error ocurred: {err}")

    def sync(self, request, queryset):
        synced_count = 0
        error_count = 0
        status_mapping = {
            "COMPLETED": models.ATHM_Transaction.Status.COMPLETED,
            "CANCEL": models.ATHM_Transaction.Status.CANCEL,
            "CANCELLED": models.ATHM_Transaction.Status.CANCEL,
            "OPEN": models.ATHM_Transaction.Status.OPEN,
            "CONFIRM": models.ATHM_Transaction.Status.CONFIRM,
            "REFUNDED": models.ATHM_Transaction.Status.REFUNDED,
        }

        for transaction in queryset:
            try:
                # Fetch latest data from ATH Móvil API
                api_data = models.ATHM_Transaction.search(transaction)

                # Check for API error response
                if api_data and "errorCode" in api_data:
                    logger.warning(
                        "[django_athm:sync_api_error]",
                        extra={
                            "transaction": transaction.id,
                            "error_code": api_data.get("errorCode"),
                            "description": api_data.get("description"),
                        },
                    )
                    error_count += 1
                    continue

                # Update transaction with latest data if found
                if api_data and "status" in api_data:
                    api_status = api_data["status"]
                    if api_status in status_mapping:
                        transaction.status = status_mapping[api_status]
                        transaction.save(update_fields=["status"])
                        synced_count += 1
                        logger.debug(
                            "[django_athm:sync_success]",
                            extra={"transaction": transaction.id, "status": api_status},
                        )
                    else:
                        logger.warning(
                            "[django_athm:sync_unknown_status]",
                            extra={
                                "transaction": transaction.id,
                                "status": api_status,
                            },
                        )
                        error_count += 1
                else:
                    logger.warning(
                        "[django_athm:sync_no_data]",
                        extra={"transaction": transaction.id},
                    )
                    error_count += 1

            except Exception as err:
                logger.exception(
                    "[django_athm:sync_error]",
                    extra={"transaction": transaction.id, "error": str(err)},
                )
                error_count += 1

        # Report results to user
        if error_count == 0:
            self.message_user(
                request, f"Successfully synced {synced_count} transactions!"
            )
        elif synced_count > 0:
            self.message_user(
                request,
                f"Synced {synced_count} transactions with {error_count} errors.",
            )
        else:
            self.message_user(
                request, f"Failed to sync transactions: {error_count} errors occurred."
            )

    refund.short_description = "Fully refund selected transactions"
    sync.short_description = (
        "Sync the selected transactions with the latest data from the API"
    )


@admin.register(models.ATHM_Item)
class ATHM_ItemAdmin(admin.ModelAdmin):
    date_hierarchy = "transaction__date"
    list_display = ("transaction", "name", "price")
    list_filter = ("transaction",)
    search_fields = ("transaction__reference_number", "name", "description")
