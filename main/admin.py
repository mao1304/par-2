from django.contrib import admin
from . import models

admin.site.register(models.Usuario)
admin.site.register(models.Vehiculo)
admin.site.register(models.RegistroParqueo)
admin.site.register(models.SuscripcionMensual)
admin.site.register(models.Tarifa)


