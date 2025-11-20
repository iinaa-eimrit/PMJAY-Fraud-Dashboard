from django.http import JsonResponse
from typing import Any, Dict, List, Optional

def success_json(data: Any, message: str = "Success", **kwargs) -> JsonResponse:
    """Standardized success response."""
    response = {
        "status": "success",
        "message": message,
        "data": data
    }
    response.update(kwargs)
    return JsonResponse(response)

def error_json(message: str, status_code: int = 400, errors: Optional[Dict] = None) -> JsonResponse:
    """Standardized error response."""
    response = {
        "status": "error",
        "message": message,
    }
    if errors:
        response["errors"] = errors
    return JsonResponse(response, status=status_code)

def paginated_json(data: List[Any], total_records: int, total_pages: int, current_page: int) -> JsonResponse:
    """Standardized paginated response."""
    return JsonResponse({
        'data': data,
        'pagination': {
            'total_records': total_records,
            'total_pages': total_pages,
            'current_page': current_page,
            'has_next': current_page < total_pages,
            'has_previous': current_page > 1,
        }
    })
