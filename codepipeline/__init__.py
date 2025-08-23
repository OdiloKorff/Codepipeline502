"""
CodePipeline - Enterprise-Grade Pipeline for Automated Software Development.

Top-level package with unified imports and API access.
"""

__version__ = "1.0.0"
__author__ = "CodePipeline Team"

# Core imports
from .secure_smoke_test import SecureSmokeTestRunner, run_secure_smoke_test
from .lean_gui_suite import LeanGUISuite, create_lean_gui_suite
from .ultimate_security_audit_suite import UltimateSecurityAuditSuite
from .final_enterprise_suite import FinalEnterpriseSuite
from .enterprise_hardening_suite import EnterpriseHardeningSuite

# Make key classes available at package level
__all__ = [
    "SecureSmokeTestRunner",
    "run_secure_smoke_test", 
    "LeanGUISuite",
    "create_lean_gui_suite",
    "UltimateSecurityAuditSuite",
    "FinalEnterpriseSuite", 
    "EnterpriseHardeningSuite"
]