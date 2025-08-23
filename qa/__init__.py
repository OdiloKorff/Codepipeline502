"""
QA (Quality Assurance) Paket.

Enthält alle Qualitätssicherungs-Tools und -Module:
- scorecard: Umfassende QA-Bewertung
- Weitere QA-Tools nach Bedarf
"""

__version__ = "0.1.0"

# QA-Paket Exporte
try:
    from ..qa_scorecard_comprehensive import ComprehensiveQAScorecard
    __all__ = ["ComprehensiveQAScorecard"]
except ImportError:
    __all__ = []
