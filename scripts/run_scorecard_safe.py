#!/usr/bin/env python3
"""
Sicherer Scorecard-Runner der Unicode-Probleme umgeht
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_scorecard_safe():
    """Führe Scorecard sicher aus"""
    
    # Set environment to avoid Unicode issues
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    try:
        # Import and run scorecard
        from qa.scorecard import run
        
        print("🎯 Running calibrated scorecard...")
        result = run()
        
        print("✅ Scorecard completed successfully")
        print(f"📊 Result: {json.dumps(result, indent=2)}")
        
        # Validate key metrics
        coverage_percent = result.get("coverage_percent", 0)
        security_high = result.get("metrics", {}).get("sast_findings", {}).get("high", 999)
        passed = result.get("passed", False)
        
        print(f"\n🎯 Key Metrics:")
        print(f"   Coverage: {coverage_percent:.2f}%")
        print(f"   Security HIGH: {security_high}")
        print(f"   Overall PASSED: {passed}")
        
        # Validate SCORE-401 criteria
        print(f"\n🎯 SCORE-401 Validation:")
        
        # 1. Coverage korrekt extrahiert
        coverage_ok = coverage_percent > 0
        print(f"   ✅ Coverage extracted: {coverage_ok} ({coverage_percent:.2f}%)")
        
        # 2. Security HIGH = 0
        security_ok = security_high == 0
        print(f"   {'✅' if security_ok else '❌'} Security HIGH = 0: {security_ok} ({security_high})")
        
        # 3. Hard-Must-Failures
        hard_failures = result.get("hard_must_failures", [])
        no_hard_failures = len(hard_failures) == 0
        print(f"   {'✅' if no_hard_failures else '❌'} No Hard-Must-Failures: {no_hard_failures} ({len(hard_failures)} failures)")
        
        if hard_failures:
            print(f"      Failures: {hard_failures}")
        
        # Overall SCORE-401 status
        score_401_success = coverage_ok and security_ok and no_hard_failures
        print(f"\n🏆 SCORE-401 Status: {'SUCCESS' if score_401_success else 'PARTIAL'}")
        
        return 0 if passed else 1
        
    except Exception as e:
        print(f"❌ Error running scorecard: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(run_scorecard_safe())
