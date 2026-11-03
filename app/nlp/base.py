from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseEmergencyExtractor(ABC):
    """
    Abstract base class for all NLP Emergency Extraction models.
    This allows swapping between Rule-based, spaCy, and Transformer models easily.
    """
    
    @abstractmethod
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Parses the text and returns a dictionary with extracted fields:
        - food_type: str
        - quantity: int
        - number_of_people: int
        - location: str
        - emergency_type: str (Enum name)
        - urgency: str (Enum name)
        - deadline: datetime string (ISO)
        - confidence: float
        """
        pass
