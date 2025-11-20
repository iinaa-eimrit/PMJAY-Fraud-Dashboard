from django.db.models import Case, When, Value, CharField

def get_age_bucket_annotation(age_field="age"):
    """
    Returns a Case/When annotation that groups ages into standard buckets.
    Bins: [0, 20, 30, 40, 50, 60, 200]
    Labels: ["≤20", "21-30", "31-40", "41-50", "51-60", "60+"]
    """
    return Case(
        When(**{f"{age_field}__isnull": True}, then=Value("Unknown")),
        When(**{f"{age_field}__lt": 0}, then=Value("Unknown")), # Handles negative ages if any
        When(**{f"{age_field}__lt": 20}, then=Value("≤20")),
        When(**{f"{age_field}__lt": 30}, then=Value("21-30")),
        When(**{f"{age_field}__lt": 40}, then=Value("31-40")),
        When(**{f"{age_field}__lt": 50}, then=Value("41-50")),
        When(**{f"{age_field}__lt": 60}, then=Value("51-60")),
        default=Value("60+"),
        output_field=CharField()
    )

def get_gender_annotation(gender_field="gender"):
    """
    Returns a Case/When annotation that normalizes gender codes.
    Maps: 'M' -> 'Male', 'F' -> 'Female', 'O' -> 'Other'
    """
    return Case(
        When(**{f"{gender_field}__iexact": "M"}, then=Value("Male")),
        When(**{f"{gender_field}__iexact": "F"}, then=Value("Female")),
        When(**{f"{gender_field}__iexact": "O"}, then=Value("Other")),
        default=Value("Unknown"),
        output_field=CharField()
    )
