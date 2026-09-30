# middleware.py
import logging
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)

class JWTSilentRefreshMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Exclude static assets, login, registration, etc.
        if request.path.startswith('/users/login/') or request.path.startswith('/static/'):
            return self.get_response(request)

        auth_header = request.headers.get('Authorization', '')
        refresh_token_cookie = request.COOKIES.get('refresh_token')
        
        should_attempt_refresh = False
        
        # Scenario A: Header exists but token might be expired/invalid
        if auth_header.startswith('Bearer '):
            raw_token = auth_header.split(' ')[1]
            try:
                JWTAuthentication().get_validated_token(raw_token)
            except (InvalidToken, TokenError):
                logger.info("Access token expired or corrupted. Checking for refresh cookie...")
                should_attempt_refresh = True
                
        # Scenario B: Header is completely missing on page load, but user has cookie session
        elif not auth_header and refresh_token_cookie:
            logger.info("Access token missing from RAM on page boot. Attempting cookie recovery...")
            should_attempt_refresh = True

        # Process the silent refresh if needed
        if should_attempt_refresh and refresh_token_cookie:
            try:
                refresh = RefreshToken(refresh_token_cookie)
                new_access_token = str(refresh.access_token)
                
                # Mutate request context so DRF views can validate right away
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {new_access_token}'
                request._mutated_access_token = new_access_token
                logger.info("Successfully generated new access token from HttpOnly cookie.")
            except TokenError:
                logger.warning("Refresh token inside cookie is expired or blacklisted.")
                # Don't break here; let it pass down so DRF properly throws a clean 401 response

        response = self.get_response(request)
        
        # Expose the new access token to JavaScript memory
        if hasattr(request, '_mutated_access_token'):
            response['X-New-Access-Token'] = request._mutated_access_token
            response['Access-Control-Expose-Headers'] = 'X-New-Access-Token'
            
        return response