import uuid
from django.db import models

class SuspiciousHospital(models.Model):
    district = models.TextField(null=True, unique=False)
    hospital_id = models.TextField(unique=True)
    hospital_name = models.TextField()
    number_of_surgeons = models.IntegerField(null=True, blank=True)
    number_of_ot = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.hospital_name

class Last24Hour(models.Model):
    registration_id = models.TextField(null=True, blank=True)
    case_id = models.TextField(null=True, blank=True)
    member_id = models.TextField(null=True, blank=True)
    family_id = models.TextField(null=True, blank=True)
    patient_name = models.TextField(null=True, blank=True)
    patient_dob = models.TextField(null=True, blank=True)  # Could be DateField if always YYYY or YYYY-MM-DD
    patient_state_code = models.TextField(null=True, blank=True)
    patient_district_code = models.TextField(null=True, blank=True)
    patient_district_name = models.TextField(null=True, blank=True)
    patient_state_name = models.TextField(null=True, blank=True)
    gender = models.TextField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    policy_code = models.TextField(null=True, blank=True)
    renewal_code = models.TextField(null=True, blank=True)
    category_details = models.TextField(null=True, blank=True)
    speciality_code = models.TextField(null=True, blank=True)
    procedure_details = models.TextField(null=True, blank=True)
    procedure_code = models.TextField(null=True, blank=True)
    case_type = models.TextField(null=True, blank=True)
    status_id_pk = models.TextField(null=True, blank=True)
    case_status = models.TextField(null=True, blank=True)
    hospital_id = models.TextField(null=True, blank=True)
    hospital_name = models.TextField(null=True, blank=True)
    hosp_district_name = models.TextField(null=True, blank=True)
    hosp_state_name = models.TextField(null=True, blank=True)
    hospital_state_cd = models.TextField(null=True, blank=True)
    hospital_district_cd = models.TextField(null=True, blank=True)
    hosp_pan_number = models.TextField(null=True, blank=True)
    hospital_type = models.TextField(null=True, blank=True)
    admission_dt = models.DateTimeField(null=True, blank=True)  # Could be DateTimeField if always date/time
    preauth_init_date = models.DateTimeField(null=True, blank=True)  # Could be DateTimeField
    amount_preauth_initiated = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    preauth_approved_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    amount_preauth_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    preauth_rejected_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    surgery_dt = models.TextField(null=True, blank=True)  # Could be DateTimeField
    death_dt = models.TextField(null=True, blank=True)  # Could be DateTimeField
    discharge_dt = models.TextField(null=True, blank=True)  # Could be DateTimeField
    claim_init_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    amount_claim_initiated = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    amount_claim_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    amount_claim_paid = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    claim_rejected_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    rf_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    utr_no = models.TextField(null=True, blank=True)
    payment_paid_dt = models.TextField(null=True, blank=True)  # Could be DateTimeField
    transaction_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cpd_approved_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    cpd_approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cpd_user = models.TextField(null=True, blank=True)
    aco_approved_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    aco_approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    aco_user = models.TextField(null=True, blank=True)
    sha_approved_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    sha_approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sha_user = models.TextField(null=True, blank=True)
    json_object_perauth = models.TextField(null=True, blank=True)
    json_object_claim = models.TextField(null=True, blank=True)
    json_object_ben = models.TextField(null=True, blank=True)
    src_account_no = models.TextField(null=True, blank=True)
    src_ifsc_code = models.TextField(null=True, blank=True)
    paid_flag = models.TextField(null=True, blank=True)
    hosp_account_number = models.TextField(null=True, blank=True)
    ben_ifsc_code = models.TextField(null=True, blank=True)
    current_workflow_role = models.TextField(null=True, blank=True)
    current_workflow_user = models.TextField(null=True, blank=True)
    service_request_type = models.TextField(null=True, blank=True)
    m_flag = models.TextField(null=True, blank=True)
    careplan_desc = models.TextField(null=True, blank=True)
    discharge_type = models.TextField(null=True, blank=True)
    admission_type = models.TextField(null=True, blank=True)
    claim_approved_date = models.TextField(null=True, blank=True)  # Could be DateTimeField
    last_insert_dt = models.TextField(null=True, blank=True)  # Could be DateTimeField

    class Meta:
        unique_together = ('registration_id', 'preauth_init_date')
        indexes = [
            models.Index(fields=['hospital_type', 'category_details']),
            models.Index(fields=['admission_dt']),
            models.Index(fields=['patient_district_name']),
            models.Index(fields=['age']),
            models.Index(fields=['hospital_id']),
            models.Index(fields=['preauth_init_date']),
        ]

    def __str__(self):
        return f"{self.registration_id} - {self.patient_name}"

class BackgroundJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'Queued', 'Queued'
        PENDING = 'Pending', 'Pending'
        RUNNING = 'Running', 'Running'
        RETRYING = 'Retrying', 'Retrying'
        COMPLETED = 'Completed', 'Completed'
        FAILED = 'Failed', 'Failed'
        CANCELLED = 'Cancelled', 'Cancelled'
        EXPIRED = 'Expired', 'Expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    
    payload = models.JSONField(default=dict)
    payload_version = models.CharField(max_length=10, default="1.0")
    
    # Allows reusing active jobs if identical requests come in
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    
    # Progress and state
    progress = models.IntegerField(default=0)
    result = models.JSONField(null=True, blank=True)
    
    # Tracing
    owner_id = models.CharField(max_length=255, null=True, blank=True)
    request_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.task_name} ({self.status})"

class JobArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(BackgroundJob, on_delete=models.CASCADE, related_name='artifacts')
    name = models.CharField(max_length=255) # e.g. "report.xlsx", "summary.json"
    content_type = models.CharField(max_length=100) # e.g. "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    file_url = models.TextField() # S3 URI or local path
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} for Job {self.job.id}"

    
class HospitalBeds(models.Model):
    hospital_id = models.TextField(unique=True)
    hospital_name = models.TextField(null=True, blank=True)
    hospital_district = models.TextField(null=True, blank=True)
    hospital_email_id = models.EmailField(max_length=254, null=True, blank=True)
    bed_strength = models.IntegerField()
    number_of_surgeons = models.IntegerField(null=True, blank=True)
    number_of_ot = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['hospital_district']),
        ]

    def __str__(self):
        return f"{self.hospital_id} — {self.hospital_name}"

class UploadHistory(models.Model):
    MODEL_CHOICES = [
        ('suspicious', 'Suspicious Hospital List'),
        ('beds',       'Hospital Beds'),
    ]
    model_type  = models.TextField(choices=MODEL_CHOICES, unique=True)
    filename    = models.TextField()
    uploaded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.model_type} uploaded at {self.uploaded_at:%Y-%m-%d %H:%M:%S}"