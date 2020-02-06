from django.contrib import admin

from . import models


@admin.register(models.ATHM_Transaction)
class ATHM_TransactionAdmin(admin.ModelAdmin):
    actions = ["refund"]
    date_hierarchy = "date"
    list_display = ("reference_number", "date", "status", "total")
    list_filter = ("status",)
    readonly_fields = ("refunded_amount",)
    search_fields = ("reference_number",)

    def refund(self, request, queryset):
        try:
            for transaction in queryset:
                models.ATHM_Transaction.refund(transaction)

            self.message_user(
                request, f"Successfully refunded {queryset.count()} transactions!"
            )
        except Exception as err:
            self.message_user(request, f"An error ocurred: {err}")

    refund.short_description = "Fully refund selected ATHM Transactions"


@admin.register(models.ATHM_Item)
class ATHM_ItemAdmin(admin.ModelAdmin):
    date_hierarchy = "transaction__date"
    list_display = ("transaction", "name", "price")
    list_filter = ("transaction",)
    search_fields = ("transaction__reference_number", "name", "description")
