from django.contrib import admin

from . import models

admin.register(models.ATH_Transaction)


class ATH_TransactionAdmin(admin.ModelAdmin):
    pass


admin.register(models.ATH_Item)


class ATH_ItemAdmin(admin.ModelAdmin):
    pass
