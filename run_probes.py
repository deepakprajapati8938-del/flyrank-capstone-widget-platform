import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from tests.test_probes import (
    reset_test_environment,
    test_probe_1_valid_submission_and_dashboard_visibility,
    test_probe_2_boundary_validation_malformed_payloads,
    test_probe_3_rate_limiting_burst_and_recovery,
    test_probe_4_geo_provider_fallback_chain,
    test_probe_5_safe_side_effects_failure_tolerance,
    test_probe_6_honeypot_spam_trap,
    test_multi_tenant_isolation
)

def run_all_probes():
    print("=" * 65)
    print("FLYRANK CAPSTONE: EMBEDDABLE WIDGET ACCEPTANCE PROBES SUITE")
    print("=" * 65 + "\n")

    probes = [
        ("PROBE 1: Valid Cross-Origin Submission & Dashboard Visibility", test_probe_1_valid_submission_and_dashboard_visibility),
        ("PROBE 2: Boundary Validation (Malformed Payloads -> Clean 4xx)", test_probe_2_boundary_validation_malformed_payloads),
        ("PROBE 3: Rate Limiting Burst Defense (429) & Recovery", test_probe_3_rate_limiting_burst_and_recovery),
        ("PROBE 4: Geo Provider Fallback Chain (Provider A -> B -> Degrade)", test_probe_4_geo_provider_fallback_chain),
        ("PROBE 5: Safe Side-Effect Failure Tolerance (Email Throws Exception)", test_probe_5_safe_side_effects_failure_tolerance),
        ("PROBE 6: Honeypot Anti-Spam Detection (Bot Trap)", test_probe_6_honeypot_spam_trap),
        ("MULTI-TENANCY: Strict Tenant Isolation (Acme vs Globex)", test_multi_tenant_isolation)
    ]

    passed = 0
    total = len(probes)

    for name, func in probes:
        print(f"[*] Executing: {name}...")
        try:
            reset_test_environment()
            func()
            print(f"    -> [PASS] OK\n")
            passed += 1
        except Exception as e:
            print(f"    -> [FAIL] Exception: {type(e).__name__}: {e}\n")

    print("=" * 65)
    print(f"PROBE AUDIT RESULT: {passed} / {total} Tests Passed ({(passed/total)*100:.1f}%)")
    print("=" * 65)
    return passed == total

if __name__ == "__main__":
    success = run_all_probes()
    sys.exit(0 if success else 1)
