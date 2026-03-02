from django.http import JsonResponse
from django.db import connection

def liveness_check(request):
    """
    /health/live
    Indicates if the application container is running and able to accept traffic.
    Does not check downstream dependencies (database, cache, etc.).
    """
    return JsonResponse({"status": "ok"})

def readiness_check(request):
    """
    /health/ready
    Indicates if the application is fully ready to serve traffic.
    Checks required downstream dependencies (e.g. database).
    """
    dependencies = {
        "database": "ok"
    }
    
    # Check Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row is None:
                raise Exception("Database returned no rows")
    except Exception as e:
        dependencies["database"] = "error"
        return JsonResponse({"status": "error", "dependencies": dependencies}, status=503)
        
    return JsonResponse({"status": "ok", "dependencies": dependencies})
