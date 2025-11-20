from typing import Tuple

def parse_pagination_params(request, default_page: int = 1, default_size: int = 50, max_size: int = 100) -> Tuple[int, int]:
    """
    Safely parses page and page_size from the request.
    Enforces maximum boundaries to protect against large queries.
    """
    try:
        page = int(request.GET.get('page', default_page))
        if page < 1:
            page = 1
    except ValueError:
        page = default_page
        
    try:
        page_size = int(request.GET.get('page_size', default_size))
        if page_size < 1:
            page_size = default_size
        elif page_size > max_size:
            page_size = max_size
    except ValueError:
        page_size = default_size
        
    return page, page_size

def calculate_pagination_metadata(total_records: int, page: int, page_size: int) -> Tuple[int, int]:
    """
    Calculates start and end indexes for standard slicing, 
    and returns (start_idx, end_idx, total_pages).
    """
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    total_pages = (total_records + page_size - 1) // page_size
    return start_idx, end_idx, total_pages
