import os
import logging

logger = logging.getLogger("widget_platform.side_effects")

# Flag for deterministic testing of failing side effects (PROBE 5)
EMAIL_SERVICE_UP = os.environ.get("MOCK_EMAIL_SERVICE_UP", "true").lower() in ("true", "1")

def set_email_service_state(is_up: bool):
    global EMAIL_SERVICE_UP
    EMAIL_SERVICE_UP = is_up

def trigger_safe_side_effects(submission_data: dict) -> bool:
    """
    Executes secondary notification (e.g. confirmation email / webhook).
    RULE: If this secondary action throws an exception, it is caught, logged,
    and isolated. The main submission path MUST NEVER fail.
    """
    try:
        if not EMAIL_SERVICE_UP:
            raise ConnectionError("SMTP Provider [Simulated] Refused Connection: Connection reset by peer")
            
        # Simulating successful email delivery / console capture
        email = submission_data.get("email")
        widget_id = submission_data.get("widget_id")
        logger.info(f"[SAFE SIDE-EFFECT] Confirmation email successfully dispatched to: {email} for widget: {widget_id}")
        return True
    except Exception as e:
        # Non-critical operations never break the main response
        logger.warning(f"[SAFE SIDE-EFFECT ISOLATED] Email side effect failed: {str(e)}. Submission success preserved.")
        return False

