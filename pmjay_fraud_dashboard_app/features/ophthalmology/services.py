import datetime
from typing import Dict, List, Any

# Mock pandas to avoid MINGW-W64 segfault during checks
pd = None

from pmjay_fraud_dashboard_app.utils.pandas_loader import load_dataframes
from pmjay_fraud_dashboard_app.utils.constants import SHAPEFILE_DISTRICT_MAPPING
from .selectors import get_hospital_district_map


def _build_period_mask(df, start_d, end_d, districts: List[str] = None):
    mask = (
        (df["hospital_type"] == "P")
        & (
            df["category_details"]
            .astype(str)
            .str.contains(
                "Opthalmology|Ophthalmology", case=False, regex=True, na=False
            )
        )
        & (df["date"] >= start_d)
        & (df["date"] <= end_d)
    )
    if districts:
        mask &= df["patient_district_name"].isin(districts)
    return mask


def aggregate_ophthalmology_cases(
    start_date: datetime.date, end_date: datetime.date, districts: List[str]
) -> Dict[str, Any]:
    yesterday = end_date - datetime.timedelta(days=1)
    thirty_days_ago = end_date - datetime.timedelta(days=30)

    df, cap_map = load_dataframes()

    mask_total = _build_period_mask(df, start_date, end_date, districts)
    mask_yest = _build_period_mask(df, yesterday, yesterday, districts)
    mask_30 = _build_period_mask(df, thirty_days_ago, end_date, districts)

    cond_age = df["age"] < 40
    cond_preauth = (df["preauth_hour"] < 8) | (df["preauth_hour"] >= 18)
    cond_ot = df["ot_violation"]

    def count_cases(p_mask, violation_cond):
        return int(df.loc[p_mask & violation_cond].shape[0])

    def calculate_ot_excess(p_mask):
        subset = df.loc[p_mask & cond_ot].copy()
        if subset.empty:
            return 0
        daily_counts = (
            subset.groupby(["hospital_id", "date"])
            .size()
            .reset_index(name="daily_count")
        )
        daily_counts["capacity"] = (
            daily_counts["hospital_id"].map(cap_map).fillna(float("inf"))
        )
        daily_counts["excess"] = (
            daily_counts["daily_count"] - daily_counts["capacity"]
        ).clip(lower=0)
        return int(daily_counts["excess"].sum())

    age_total = count_cases(mask_total, cond_age)
    age_yesterday = count_cases(mask_yest, cond_age)
    age_last_30 = count_cases(mask_30, cond_age)

    preauth_total = count_cases(mask_total, cond_preauth)
    preauth_yesterday = count_cases(mask_yest, cond_preauth)
    preauth_last_30 = count_cases(mask_30, cond_preauth)

    ot_total = calculate_ot_excess(mask_total)
    ot_yesterday = calculate_ot_excess(mask_yest)
    ot_last_30 = calculate_ot_excess(mask_30)

    cond_any_violation = cond_ot | cond_age | cond_preauth
    total_flagged_hospitals = df.loc[
        mask_total & cond_any_violation, "hospital_id"
    ].nunique()
    total_unique_cases = int(df.loc[mask_total & cond_any_violation].shape[0])

    age_hospitals = int(df.loc[mask_total & cond_age, "hospital_id"].nunique())
    ot_hospitals = int(df.loc[mask_total & cond_ot, "hospital_id"].nunique())
    preauth_hospitals = int(df.loc[mask_total & cond_preauth, "hospital_id"].nunique())

    flagged_df = df.loc[mask_total & cond_any_violation].copy()
    if not flagged_df.empty:
        hospital_summary = (
            flagged_df.groupby(["hospital_id", "hospital_name"])
            .size()
            .reset_index(name="violation_count")
            .sort_values(by="violation_count", ascending=False)
        )
        flagged_hospitals = hospital_summary.to_dict(orient="records")
    else:
        flagged_hospitals = []

    return {
        "total": total_flagged_hospitals,
        "total_unique_cases": total_unique_cases,
        "age_under_40": {
            "total": age_total,
            "hospitals": age_hospitals,
            "yesterday": age_yesterday,
            "last_30_days": age_last_30,
        },
        "ot_cases": {
            "total": ot_total,
            "hospitals": ot_hospitals,
            "yesterday": ot_yesterday,
            "last_30_days": ot_last_30,
        },
        "preauth_time": {
            "total": preauth_total,
            "hospitals": preauth_hospitals,
            "yesterday": preauth_yesterday,
            "last_30_days": preauth_last_30,
        },
        "flagged_hospitals": flagged_hospitals,
    }


def get_ophthalmology_details_data(
    start_date: datetime.date,
    end_date: datetime.date,
    districts: List[str],
    violation_type: str,
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    df, cap_map = load_dataframes()

    mask = (
        df["hospital_type"].eq("P")
        & df["category_details"].str.contains("Opthalmology", case=False, na=False)
        & df["preauth_init_date"].dt.date.ge(start_date)
        & df["preauth_init_date"].dt.date.le(end_date)
    )
    if districts:
        mask &= df["patient_district_name"].isin(districts)

    df_base = df.loc[mask].copy()

    if violation_type == "hospital_summary":
        df_base["is_age"] = (df_base["age"] < 40).astype(int)
        df_base["is_time"] = (
            (df_base["preauth_hour"] < 8) | (df_base["preauth_hour"] >= 18)
        ).astype(int)
        df_base["is_ot"] = df_base["ot_violation"].astype(int)
        df_base["is_any"] = (
            (df_base["is_age"] + df_base["is_time"] + df_base["is_ot"]) > 0
        ).astype(int)

        df_violators = df_base[df_base["is_any"] == 1].copy()

        summary = (
            df_violators.groupby(["hospital_id", "hospital_name"])
            .agg(age_violations=("is_age", "sum"), time_violations=("is_time", "sum"))
            .reset_index()
        )

        df_ot = df_base[df_base["ot_violation"]]
        if not df_ot.empty:
            daily_ot = (
                df_ot.groupby(["hospital_id", "date"])
                .size()
                .reset_index(name="daily_count")
            )
            daily_ot["capacity"] = (
                daily_ot["hospital_id"].map(cap_map).fillna(float("inf"))
            )
            daily_ot["excess"] = (daily_ot["daily_count"] - daily_ot["capacity"]).clip(
                lower=0
            )
            hospital_ot_excess = (
                daily_ot.groupby("hospital_id")["excess"].sum().reset_index()
            )
            hospital_ot_excess.rename(columns={"excess": "ot_violations"}, inplace=True)
        else:
            hospital_ot_excess = pd.DataFrame(columns=["hospital_id", "ot_violations"])

        summary = pd.merge(summary, hospital_ot_excess, on="hospital_id", how="left")
        summary["ot_violations"] = summary["ot_violations"].fillna(0)

        summary["total_violations"] = (
            summary["age_violations"]
            + summary["time_violations"]
            + summary["ot_violations"]
        )

        grand_total = summary["total_violations"].sum()
        if grand_total > 0:
            summary["share_percent"] = (
                (summary["total_violations"] / grand_total) * 100
            ).round(2)
        else:
            summary["share_percent"] = 0.0

        summary = summary.sort_values(by="total_violations", ascending=False)

        total_records = len(summary)
        start = (page - 1) * page_size
        end = start + page_size
        page_df = summary.iloc[start:end]
        total_pages = (total_records + page_size - 1) // page_size

        data = []
        for i, row in enumerate(page_df.itertuples(), start=1):
            data.append(
                {
                    "serial_no": start + i,
                    "hospital_id": row.hospital_id,
                    "hospital_name": row.hospital_name,
                    "total_violations": int(row.total_violations),
                    "age_violations": int(row.age_violations),
                    "time_violations": int(row.time_violations),
                    "ot_violations": int(row.ot_violations),
                    "share_percent": f"{row.share_percent}%",
                    "claim_id": "-",
                    "patient_name": "-",
                    "district_name": "-",
                    "amount": 0,
                }
            )

    else:
        df_base.sort_values(by="preauth_init_date", inplace=True)
        m_age = df_base["age"] < 40
        m_preauth = (df_base["preauth_hour"] < 8) | (df_base["preauth_hour"] >= 18)
        m_ot = df_base["ot_violation"]

        if violation_type == "age":
            vio_mask = m_age
        elif violation_type == "preauth":
            vio_mask = m_preauth
        elif violation_type == "ot":
            vio_mask = m_ot
        elif violation_type == "multiple":
            vio_mask = (
                m_age.astype(int) + m_preauth.astype(int) + m_ot.astype(int)
            ) > 1
        else:
            vio_mask = m_age | m_preauth | m_ot

        df_cases = df_base.loc[vio_mask]

        total_records = len(df_cases)
        start = (page - 1) * page_size
        end = start + page_size
        page_df = df_cases.iloc[start:end]
        total_pages = (total_records + page_size - 1) // page_size

        hospital_district_map = get_hospital_district_map()

        data = []
        for i, row in enumerate(page_df.itertuples(), start=1):
            data.append(
                {
                    "serial_no": start + i,
                    "claim_id": row.registration_id or row.case_id or "N/A",
                    "patient_name": row.patient_name or f"Patient {row.member_id}",
                    "patient_district": row.patient_district_name or "N/A",
                    "hospital_id": row.hospital_id or "N/A",
                    "hospital_name": row.hospital_name or "N/A",
                    "hospital_district": hospital_district_map.get(
                        row.hospital_id, "N/A"
                    ),
                    "district_name": row.patient_district_name or "N/A",
                    "amount": getattr(row, "preauth_initiated_amount", 0) or 0,
                    "age": row.age,
                    "preauth_time": (
                        row.preauth_init_date.strftime("%Y-%m-%d %H:%M:%S")
                        if row.preauth_init_date
                        else "N/A"
                    ),
                    "age_violation": (
                        bool(row.age < 40)
                        if violation_type in ("age", "all", "multiple")
                        else None
                    ),
                    "preauth_violation": (
                        bool((row.preauth_hour < 8) or (row.preauth_hour >= 18))
                        if violation_type in ("preauth", "all", "multiple")
                        else None
                    ),
                    "ot_violation": (
                        bool(row.ot_violation)
                        if violation_type in ("ot", "all", "multiple")
                        else None
                    ),
                }
            )

    return {
        "data": data,
        "pagination": {
            "total_records": total_records,
            "total_pages": total_pages,
            "current_page": page,
            "has_next": end < total_records,
            "has_previous": start > 0,
        },
    }

from django.db.models import Q, Count
from pmjay_fraud_dashboard_app.models import Last24Hour
from pmjay_fraud_dashboard_app.utils.orm_annotations import get_age_bucket_annotation, get_gender_annotation


def get_ophthalmology_distribution_data(
    start_date: datetime.date,
    end_date: datetime.date,
    districts: List[str],
    violation_type: str,
) -> Dict[str, list]:
    if violation_type in ("age", "preauth"):
        end_date_inclusive = end_date + datetime.timedelta(days=1)
        qs = Last24Hour.objects.filter(
            hospital_type='P',
            category_details__icontains='Opthalmology',
            preauth_init_date__gte=start_date,
            preauth_init_date__lt=end_date_inclusive,
        )
        
        if districts:
            qs = qs.filter(patient_district_name__in=districts)
            
        if violation_type == "age":
            qs = qs.filter(age__lt=40)
        elif violation_type == "preauth":
            qs = qs.filter(
                Q(preauth_init_date__hour__lt=8) | Q(preauth_init_date__hour__gte=18)
            )
            
        district_counts = (
            qs.values('patient_district_name')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )
        
        districts_out = []
        counts_out = []
        
        for item in district_counts:
            d_name = item['patient_district_name']
            districts_out.append(d_name if d_name else "Unknown")
            counts_out.append(item['cnt'])
            
        return {"districts": districts_out, "counts": counts_out}

    df, _ = load_dataframes()

    mask = (
        df["hospital_type"].eq("P")
        & df["category_details"].str.contains("Opthalmology", case=False, na=False)
        & df["date"].between(start_date, end_date)
    )
    if districts:
        mask &= df["patient_district_name"].isin(districts)

    df_base = df.loc[mask]

    m_age = df_base["age"] < 40
    m_preauth = df_base["preauth_hour"].lt(8) | df_base["preauth_hour"].ge(18)
    m_ot = df_base["ot_violation"]

    if violation_type == "age":
        vio_mask = m_age
    elif violation_type == "preauth":
        vio_mask = m_preauth
    elif violation_type == "ot":
        vio_mask = m_ot
    elif violation_type == "multiple":
        vio_mask = (m_age.astype(int) + m_preauth.astype(int) + m_ot.astype(int)) > 1
    else:
        vio_mask = m_age | m_preauth | m_ot

    df_filtered = df_base.loc[vio_mask]
    counts = (
        df_filtered["patient_district_name"]
        .fillna("Unknown")
        .astype(str)
        .value_counts()
    )

    return {"districts": counts.index.tolist(), "counts": counts.values.tolist()}


def get_ophthalmology_demographics_data(
    start_date: datetime.date,
    end_date: datetime.date,
    districts: List[str],
    demo_type: str,
    violation_type: str,
) -> Dict[str, list]:
    if violation_type in ("age", "preauth"):
        end_date_inclusive = end_date + datetime.timedelta(days=1)
        qs = Last24Hour.objects.filter(
            hospital_type='P',
            category_details__icontains='Opthalmology',
            preauth_init_date__gte=start_date,
            preauth_init_date__lt=end_date_inclusive,
        )
        if districts:
            qs = qs.filter(patient_district_name__in=districts)
            
        if violation_type == "age":
            qs = qs.filter(age__lt=40)
        elif violation_type == "preauth":
            qs = qs.filter(
                Q(preauth_init_date__hour__lt=8) | Q(preauth_init_date__hour__gte=18)
            )

        if demo_type == "age":
            qs = qs.annotate(age_group=get_age_bucket_annotation('age'))
            counts = qs.values('age_group').annotate(cnt=Count('id'))
            
            labels = ["≤20", "21-30", "31-40", "41-50", "51-60", "60+", "Unknown"]
            counts_dict = {item['age_group']: item['cnt'] for item in counts}
            data = [counts_dict.get(label, 0) for label in labels]
            colors = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#C9CBCF"]
            return {"labels": labels, "data": data, "colors": colors}
        else:
            qs = qs.annotate(gender_label=get_gender_annotation('gender'))
            counts = qs.values('gender_label').annotate(cnt=Count('id'))
            
            labels = ["Male", "Female", "Other", "Unknown"]
            counts_dict = {item['gender_label']: item['cnt'] for item in counts}
            data = [counts_dict.get(label, 0) for label in labels]
            colors = ["#36A2EB", "#FF6384", "#4BC0C0", "#C9CBCF"]
            return {"labels": labels, "data": data, "colors": colors}

    df, _ = load_dataframes()

    mask = (
        df["hospital_type"].eq("P")
        & df["category_details"].str.contains("Opthalmology", case=False, na=False)
        & df["date"].between(start_date, end_date)
    )
    if districts:
        mask &= df["patient_district_name"].isin(districts)

    df_base = df.loc[mask].copy()

    m_age = df_base["age"] < 40
    m_preauth = df_base["preauth_hour"].lt(8) | df_base["preauth_hour"].ge(18)
    m_ot = df_base["ot_violation"]

    if violation_type == "age":
        vio_mask = m_age
    elif violation_type == "preauth":
        vio_mask = m_preauth
    elif violation_type == "ot":
        vio_mask = m_ot
    elif violation_type == "multiple":
        vio_mask = (m_age.astype(int) + m_preauth.astype(int) + m_ot.astype(int)) > 1
    else:
        vio_mask = m_age | m_preauth | m_ot

    df_flagged = df_base.loc[vio_mask]

    if demo_type == "age":
        bins = [0, 20, 30, 40, 50, 60, 200]
        labels = ["≤20", "21-30", "31-40", "41-50", "51-60", "60+"]
        df_flagged["age_group"] = (
            pd.cut(df_flagged["age"].fillna(-1), bins=bins, labels=labels, right=False)
            .cat.add_categories(["Unknown"])
            .fillna("Unknown")
        )

        counts = (
            df_flagged["age_group"]
            .value_counts()
            .reindex(labels + ["Unknown"], fill_value=0)
        )
        colors = [
            "#FF6384",
            "#36A2EB",
            "#FFCE56",
            "#4BC0C0",
            "#9966FF",
            "#FF9F40",
            "#C9CBCF",
        ]

        return {
            "labels": labels + ["Unknown"],
            "data": counts.tolist(),
            "colors": colors,
        }
    else:
        gender_map = {"M": "Male", "F": "Female", "O": "Other"}
        df_flagged["gender_label"] = (
            df_flagged["gender"].map(gender_map).fillna("Unknown")
        )

        labels = ["Male", "Female", "Other", "Unknown"]
        counts = df_flagged["gender_label"].value_counts().reindex(labels, fill_value=0)
        colors = ["#36A2EB", "#FF6384", "#4BC0C0", "#C9CBCF"]

        return {"labels": labels, "data": counts.tolist(), "colors": colors}


def get_ophthalmology_violations_geo_data(
    start_date: datetime.date,
    end_date: datetime.date,
    districts: List[str],
    violation_type: str,
) -> List[Dict[str, int]]:
    df, _ = load_dataframes()

    mask = (
        df["hospital_type"].eq("P")
        & df["category_details"].str.contains("Opthalmology", case=False, na=False)
        & df["date"].between(start_date, end_date)
    )
    if districts:
        mask &= df["patient_district_name"].isin(districts)

    df_base = df.loc[mask]

    m_age = df_base["age"] < 40
    m_preauth = df_base["preauth_hour"].lt(8) | df_base["preauth_hour"].ge(18)
    m_ot = df_base["ot_violation"]

    if violation_type == "age":
        vio_mask = m_age
    elif violation_type == "preauth":
        vio_mask = m_preauth
    elif violation_type == "ot":
        vio_mask = m_ot
    elif violation_type == "multiple":
        vio_mask = (m_age.astype(int) + m_preauth.astype(int) + m_ot.astype(int)) > 1
    else:
        vio_mask = m_age | m_preauth | m_ot

    df_filtered = df_base.loc[vio_mask]
    counts = df_filtered["patient_district_name"].fillna("Unknown").value_counts()

    result = [
        {"fid": SHAPEFILE_DISTRICT_MAPPING.get(district.lower()), "count": int(cnt)}
        for district, cnt in counts.items()
        if SHAPEFILE_DISTRICT_MAPPING.get(district.lower()) is not None
    ]
    return result
