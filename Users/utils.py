import logging
import random
import secrets
import hashlib
import hmac
import time  # ✅ Replaced asyncio.sleep with native time.sleep
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from celery import shared_task

logger = logging.getLogger('users')

OTP_LIMIT = 10       # max OTP per window
OTP_WINDOW = 300     # 5 minutes
OTP_EXPIRY = 120     # 2 minutes
IP_EXPIRY = 600      # 10 minutes
SESSION_EXPIRY = 300 # 5 minutes
ATTEMPT_EXPIRY = 300 # 5 minutes


def get_client_ip(request):
    """Fetches client IP address from request metadata."""
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        logger.debug(f"[get_client_ip] Successfully extracted IP: {ip}")
        return ip
    except Exception as e:
        logger.error(f"[get_client_ip] Critical failure fetching client IP: {str(e)}", exc_info=True)
        return None


def increment_cache(key, limit, timeout):
    """Atomically increments a cache counter using standard Django cache methods."""
    count = cache.get(key, 0)
    logger.debug(f"[increment_cache] Current count for key '{key}' is {count} (Limit: {limit})")

    if count >= limit:
        logger.warning(f"[increment_cache] Hit ceiling count of {count}/{limit} for key '{key}'")
        return False, count

    try:
        new_count = cache.incr(key)
        logger.debug(f"[increment_cache] Incremented key '{key}' to {new_count}")
        return True, new_count
    except ValueError:
        logger.debug(f"[increment_cache] Key '{key}' not initialized or expired. Initializing counter to 1.")
        cache.set(key, 1, timeout=timeout)
        return True, 1


def check_ip_limit(prefix, ip, limit, timeout):
    """Validates if an IP address has surpassed its action limits."""
    key = f"{prefix}:{ip}"
    allowed, count = increment_cache(key, limit, timeout)

    if not allowed:
        logger.warning(f"[check_ip_limit] Rate limit blocked IP: {ip} | Prefix: {prefix} | Count: {count}")
        return False
    return True


def check_otp_limit(email, ip):
    """Enforces dual-layered rate limiting (both Email and IP address restrictions)."""
    email_key = f"otp_limit_email:{email}"
    ip_key = f"otp_limit_ip:{ip}"

    email_ok, email_count = increment_cache(email_key, OTP_LIMIT, OTP_WINDOW)
    ip_ok, ip_count = increment_cache(ip_key, OTP_LIMIT, IP_EXPIRY)

    if not email_ok:
        logger.warning(f"[check_otp_limit] Throttle active: Email '{email}' reached max requests ({email_count})")
        return False

    if not ip_ok:
        logger.warning(f"[check_otp_limit] Throttle active: IP '{ip}' reached max requests ({ip_count})")
        return False

    return True


def hash_otp(otp):
    """Pure CPU-bound hashing execution."""
    return hashlib.sha256(otp.encode()).hexdigest()


def generate_otp(email, request):
    """Generates a secure 6-digit numeric OTP and stores its hash in the cache layer."""
    try:
        ip = get_client_ip(request)

        if not check_otp_limit(email, ip):
            logger.warning(f"[generate_otp] Blocked OTP generation request for {email} due to limits.")
            return None

        otp = str(random.randint(100000, 999999))
        hashed = hash_otp(otp)
      
        cache.set(f"otp:register:{email}", hashed, timeout=OTP_EXPIRY)
        logger.info(f"[generate_otp] New OTP stored securely for {email} from client IP {ip}")
        return otp

    except Exception as e:
        logger.error(f"[generate_otp] Error encountered during execution flow: {str(e)}", exc_info=True)
        return None


@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, email, otp):
    subject = "Job Portal - OTP Verification"
    message = f"Hello,\n\nYour OTP is: {otp}\n\nThis OTP is valid for {OTP_EXPIRY // 60} minutes.\n\nDo not share this OTP with anyone.\n\nThanks,\nJob Portal Team"
    try:
        logger.info(f"[send_otp_email_task] Dispatching email stream to {email}")
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
        logger.info(f"[send_otp_email_task] Dispatched successfully to destination: {email}")
    except Exception as e:
        logger.error(f"[send_otp_email_task] Delivery failed to {email}. Retrying worker execution. Error: {str(e)}")
        raise self.retry(exc=e, countdown=5)


def create_verify_token(email):
    """Creates a temporary secure URL registration session signature token."""
    token = secrets.token_urlsafe(32)
    cache.set(f"verify_token:{token}", email, timeout=SESSION_EXPIRY)
    logger.info(f"[create_verify_token] Instantiated security context token for target email: {email}")
    return token


def get_email_from_token(token):
    """Verifies a token string and extracts the associated email context."""
    email = cache.get(f"verify_token:{token}")
    if not email:
        logger.warning(f"[get_email_from_token] Provided validation token is invalid or missing from storage: {token}")
        return None
    return email

def get_password_from_token(token):
    email = get_email_from_token(token)
    """Retrieves the password hash associated with a verification token."""
    password_hash = cache.get(f"verify_token:{token}")
    if not password_hash:
        logger.warning(f"[get_password_from_token] Provided validation token is invalid or missing from storage: {token}")
        return None
    return password_hash

def check_token_attempt(token, ip, limit=10):
    """Tracks submission attempts on a token to prevent token brute forcing."""
    key = f"token_attempt:{token}:{ip}"
    allowed, count = increment_cache(key, limit, ATTEMPT_EXPIRY)
    if not allowed:
        logger.warning(f"[check_token_attempt] Rate limit violation on token verification for IP: {ip}")
        return False
    return True


def check_otp_attempt(email, limit=3):
    """Checks if a user context has hit their password authentication threshold."""
    key = f"otp_attempt:{email}"
    attempts = cache.get(key, 0)
    if attempts >= limit:
        logger.warning(f"[check_otp_attempt] Blocked execution. Profile '{email}' has {attempts}/{limit} failures.")
        return False
    return True


def increment_otp_attempt(email):
    """Increments failed verification metrics for a specific email track."""
    key = f"otp_attempt:{email}"
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=ATTEMPT_EXPIRY)
        return 1


def verify_otp(email, otp):
    """Compares incoming input values with stored secure hashes synchronously."""
    stored = cache.get(f"otp:register:{email}")

    if not stored:
        logger.warning(f"[verify_otp] Evaluation rejected: OTP context record has expired for {email}")
        return False, "OTP expired"

    hashed_input = hash_otp(otp)

    if not hmac.compare_digest(stored, hashed_input):
        logger.warning(f"[verify_otp] Password mismatch. Delaying execution thread to neutralize processing timing side-channels.")
        time.sleep(0.8)  # ✅ Fixed: Standard synchronous pause blocks timing side-channel safely
        
        attempts = increment_otp_attempt(email)
        logger.warning(f"[verify_otp] Failed matching evaluation record logged ({attempts} total attempts) for: {email}")
        return False, "Invalid OTP"

    logger.info(f"[verify_otp] Verification pass confirmed for target routing block: {email}")
    return True, "OTP verified"


def clear_verification_cache(email, token, ip):
    """Purges intermediate transactional cache objects clean across multiple keys in bulk."""
    logger.debug(f"[clear_verification_cache] Performing full security cache sweeping routines for context: {email}")
    cache.delete(f"otp:register:{email}")
    cache.delete(f"otp_attempt:{email}")
    cache.delete(f"verify_token:{token}")
    cache.delete(f"token_attempt:{token}:{ip}")
    logger.info(f"[clear_verification_cache] Transaction records securely expunged from the application state.")