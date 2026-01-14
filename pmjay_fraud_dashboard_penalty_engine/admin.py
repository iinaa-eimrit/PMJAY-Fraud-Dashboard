from django.contrib import admin
from .models import PenaltyCase, PenaltyAuditLog


@admin.register(PenaltyCase)
class PenaltyCaseAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'hospital_id', 'hospital_name', 'penalty_type',
        'status', 'penalty_amount', 'suspension_until', 'imposed_at', 'created_by',
    ]
    list_filter  = ['status', 'penalty_type']
    search_fields = ['hospital_id', 'hospital_name']
    readonly_fields = ['imposed_at', 'created_at', 'updated_at']


@admin.register(PenaltyAuditLog)
class PenaltyAuditLogAdmin(admin.ModelAdmin):
    list_display = ['penalty', 'action', 'performed_by', 'performed_at']
    list_filter  = ['action']
    readonly_fields = ['performed_at']