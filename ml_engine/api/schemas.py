"""
Pydantic schemas for RxShield FastAPI endpoints
Defines request and response models
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class ErrorType(str, Enum):
    """Types of prescription errors detected."""
    DDI = "DDI"
    INDICATION_MISMATCH = "INDICATION_MISMATCH"
    DOSAGE_ERROR = "DOSAGE_ERROR"
    LASA = "LASA"
    ALLERGY = "ALLERGY"


class Severity(str, Enum):
    """Severity levels for detected errors."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NORMAL = "NORMAL"


class Language(str, Enum):
    """Supported languages for OCR."""
    AUTO = "auto"
    ENGLISH = "english"
    HINDI = "hindi"
    MARATHI = "marathi"
    DEVANAGARI = "devanagari"


# ============================================================================
# REQUEST MODELS
# ============================================================================

class PatientData(BaseModel):
    """Patient demographic and medical information."""
    age: int = Field(..., ge=0, le=120)
    gender: str = Field(..., pattern="^(Male|Female|Other)$")
    weight_kg: Optional[float] = Field(None, ge=1, le=300)
    diagnosis: List[str] = []
    allergies: List[str] = []
    current_medications: List[str] = []
    comorbidities: Optional[List[str]] = []


class AnalyzeRequest(BaseModel):
    """Request model for prescription analysis."""
    prescriptionText: str = Field(..., min_length=5)
    patientData: PatientData
    patientId: Optional[str] = None


class OCRRequest(BaseModel):
    """Request model for OCR processing."""
    image_b64: str = Field(..., min_length=100)
    language: Language = Language.AUTO


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class ExtractedDrug(BaseModel):
    """Extracted drug information from prescription."""
    drug_name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None


class ErrorDetail(BaseModel):
    """Details about a detected prescription error."""
    error_type: str
    drug: Optional[str] = None
    drug_a: Optional[str] = None
    drug_b: Optional[str] = None
    severity: str
    message: str
    explanation: Optional[str] = None   # WHY this is a problem
    solution: Optional[str] = None      # WHAT to do about it
    confidence: Optional[float] = None
    details: Optional[dict] = None


class AnalyzeResponse(BaseModel):
    """Response model for prescription analysis."""
    status: str
    prescriptionId: Optional[str] = None
    extractedDrugs: List[ExtractedDrug]
    errors: List[ErrorDetail]
    riskScore: float = Field(..., ge=0.0, le=1.0)
    riskLevel: str
    summary: str
    processingTime_ms: Optional[float] = None


class OCRResponse(BaseModel):
    """Response model for OCR processing."""
    extractedText: str
    cleanedText: str
    engine: str
    language: str
    confidence: Optional[float] = None
    charCount: int
    success: bool


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str
    service: str
    models_loaded: dict
    version: str = "1.0.0"
