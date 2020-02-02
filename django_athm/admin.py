from django.contrib import admin

from . import models

admin.register(models.ATHM_Transaction)


class ATHM_TransactionAdmin(admin.ModelAdmin):
    pass


admin.register(models.ATHM_Item)


class ATHM_ItemAdmin(admin.ModelAdmin):
    pass
