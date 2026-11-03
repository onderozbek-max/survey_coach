"""Controlled, partial survey reading; never a full-coverage crawler."""
from .policy import UnsafeSurveyURL, validate_url
from .models import Capture, Coverage, ReadResult
from .definition import DefinitionRead, adapt_definition, apply_definition, find_definition
from .session import read_survey

__all__ = [
    "UnsafeSurveyURL", "validate_url", "read_survey", "Capture", "Coverage", "ReadResult",
    "DefinitionRead", "adapt_definition", "apply_definition", "find_definition",
]
