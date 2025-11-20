class PMJAYBaseException(Exception):
    """Base exception for all application-specific errors."""
    pass

class ValidationError(PMJAYBaseException):
    """Raised when request parameters fail validation."""
    pass

class BusinessLogicError(PMJAYBaseException):
    """Raised when a business rule is violated."""
    pass

class DataImportError(PMJAYBaseException):
    """Raised during data ingestion failures."""
    pass

class ReportGenerationError(PMJAYBaseException):
    """Raised when PDF or Excel generation fails."""
    pass

class ExternalServiceError(PMJAYBaseException):
    """Raised when an external API or service fails."""
    pass
