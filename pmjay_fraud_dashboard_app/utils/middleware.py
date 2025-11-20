import time
from django.utils.deprecation import MiddlewareMixin
from .context import set_request_context, get_request_id, get_request_start_time
import logging

logger = logging.getLogger('pmjay_dashboard.requests')

class RequestContextMiddleware(MiddlewareMixin):
    """
    Middleware to inject Request ID and other context variables into
    the current asyncio context or thread local using contextvars.
    """
    
    def process_request(self, request):
        # Extract existing headers if any (e.g. from an API Gateway or LB)
        corr_id = request.headers.get('X-Correlation-ID')
        req_id = request.headers.get('X-Request-ID')
        user_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Initialize contextvars
        set_request_context(req_id=req_id, corr_id=corr_id, user=user_id)
        
    def process_response(self, request, response):
        req_id = get_request_id()
        start_time = get_request_start_time()
        
        if req_id:
            response['X-Request-ID'] = req_id
            
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
            # Log the request lifecycle
            # Note: We rely on the logging framework to inject the request_id context
            logger.info(
                f"{request.method} {request.path} {response.status_code}",
                extra={
                    'http_method': request.method,
                    'http_path': request.path,
                    'http_status': response.status_code,
                    'execution_time_ms': round(duration_ms, 2)
                }
            )
            
        return response
    
    def process_exception(self, request, exception):
        logger.error(
            f"Unhandled exception during {request.method} {request.path}: {str(exception)}",
            exc_info=True,
            extra={
                'http_method': request.method,
                'http_path': request.path,
            }
        )
        return None
