from django.contrib import admin
from .models import SuspiciousHospital, Last24Hour

# Register your models here.
admin.site.register(SuspiciousHospital)
admin.site.register(Last24Hour)