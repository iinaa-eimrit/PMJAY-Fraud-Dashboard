import contextvars
import uuid
import time

_request_id = contextvars.ContextVar('request_id', default=None)
_request_start_time = contextvars.ContextVar('request_start_time', default=None)
_correlation_id = contextvars.ContextVar('correlation_id', default=None)
_user_id = contextvars.ContextVar('user_id', default=None)

def set_request_context(req_id=None, corr_id=None, user=None):
    """Initializes context variables for the current request cycle."""
    if not req_id:
        req_id = str(uuid.uuid4())
    _request_id.set(req_id)
    _request_start_time.set(time.time())
    
    if corr_id:
        _correlation_id.set(corr_id)
    
    if user:
        _user_id.set(user)
        
    return req_id

def get_request_id():
    return _request_id.get()

def get_request_start_time():
    return _request_start_time.get()

def get_correlation_id():
    return _correlation_id.get()

def get_user_id():
    return _user_id.get()

def get_request_context_dict():
    """Returns a dictionary of all relevant context vars for log injection."""
    return {
        'request_id': get_request_id(),
        'correlation_id': get_correlation_id(),
        'user_id': get_user_id()
    }
