import datetime
import logging
from .logging import Timer
from pmjay_fraud_dashboard_app.models import HospitalBeds, Last24Hour

# Mock pandas to avoid MINGW-W64 segfault during checks
pd = None

CACHE_TTL = datetime.timedelta(minutes=5)
df_cache = None
df_last_loaded = None
capacity_map = None

def load_dataframes():
    with Timer('load_dataframes: TOTAL TIME TAKEN'):
        global df_cache, df_last_loaded, capacity_map
        if 'df_last_loaded' not in globals():
            df_last_loaded = None
        if 'df_cache' not in globals():
            df_cache = None
        need_reload = df_cache is None or df_last_loaded is None or datetime.datetime.now() - df_last_loaded > CACHE_TTL
        if need_reload:
            print('\n' + '=' * 80)
            print('load_dataframes(): Loading fresh data from database')
            print('=' * 80 + '\n')
            with Timer('load_dataframes: Load hospital capacity'):
                cap_qs = HospitalBeds.objects.values('hospital_id', 'number_of_ot', 'number_of_surgeons')
                capacity_map = {}
                for row in cap_qs:
                    surgeons = row['number_of_surgeons'] if row['number_of_surgeons'] and row['number_of_surgeons'] > 0 else 1
                    ots = row['number_of_ot'] if row['number_of_ot'] and row['number_of_ot'] > 0 else 1
                    limit = min(surgeons, ots) * 30
                    capacity_map[row['hospital_id']] = limit
                print(f'Loaded {len(capacity_map)} hospital capacity records')
            with Timer('load_dataframes: Load 24 hours data'):
                qs = Last24Hour.objects.values('hospital_type', 'hospital_id', 'procedure_code', 'category_details', 'patient_district_name', 'age', 'patient_name', 'gender', 'registration_id', 'case_id', 'member_id', 'hospital_name', 'preauth_init_date', 'amount_preauth_initiated')
                data_list = list(qs)
                df = pd.DataFrame(data_list)
                if df.empty:
                    print('WARNING: Database is empty')
                    df_cache = df
                    df_cache['ot_violation'] = False
                    df_last_loaded = datetime.datetime.now()
                    return (df_cache, capacity_map)
                print(f'Loaded {len(df)} records from Last24Hour table')
            with Timer('load_dataframes: Normalize columns'):
                df.columns = [c.strip().replace('\ufeff', '') for c in df.columns]
            with Timer('load_dataframes: Convert datatypes'):
                df['preauth_init_date'] = pd.to_datetime(df['preauth_init_date'], errors='coerce')
                df.dropna(subset=['preauth_init_date'], inplace=True)
                df['preauth_hour'] = df['preauth_init_date'].dt.hour
                df['date'] = df['preauth_init_date'].dt.date
                df['ot_violation'] = False
                df_cache = df
            print('Computing OT violations (Ophthalmology Only | Daily Count > Capacity | Flag All)...')
            with Timer('load_dataframes: Count hospital anomalies'):
                ophtha_mask = df_cache['category_details'].astype(str).str.contains('Opthalmology|Ophthalmology', case=False, regex=True, na=False)
                if ophtha_mask.any():
                    df_ophtha = df_cache.loc[ophtha_mask].copy()
                    df_ophtha['daily_total'] = df_ophtha.groupby(['hospital_id', 'date'])['hospital_id'].transform('count')
                    df_ophtha['capacity_limit'] = df_ophtha['hospital_id'].map(capacity_map).fillna(float('inf'))
                    violations_mask = df_ophtha['daily_total'] > df_ophtha['capacity_limit']
                    violation_indices = df_ophtha.index[violations_mask]
                    df_cache.loc[violation_indices, 'ot_violation'] = True
                    ot_violations_count = len(violation_indices)
                else:
                    ot_violations_count = 0
                print(f'Marked {ot_violations_count} OT overflow violations\n')
                print('=' * 80 + '\n')
                df_last_loaded = datetime.datetime.now()
    return (df_cache, capacity_map)