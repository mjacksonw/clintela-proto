"""Custom token generators for patient authentication."""

import hashlib
import secrets
import string
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class ShortCodeTokenGenerator(PasswordResetTokenGenerator):
    """Token generator that creates secure tokens with short display codes.
    
    Uses Django's PasswordResetTokenGenerator for security, derives a 
    6-character alphanumeric code for patient-friendly display.
    
    Works with Patient model instead of User model.
    """
    
    CODE_LENGTH = 6
    CODE_ALPHABET = string.ascii_uppercase + string.digits
    
    def _make_hash_value(self, patient, timestamp):
        """Override to work with Patient model instead of User.
        
        Hash includes:
        - Patient ID
        - Timestamp (for time-limited tokens)
        - Patient's leaflet_code (changes on regeneration)
        - Patient's last_updated timestamp
        """
        from django.utils.crypto import constant_time_compare
        
        return (
            str(patient.pk) + str(timestamp) + 
            str(patient.leaflet_code) + str(patient.updated_at)
        )
    
    def get_short_code(self, token):
        """Derive a short 6-character code from the full token.
        
        Uses hash of token + secret key to create deterministic but 
        unguessable short code.
        """
        from django.conf import settings
        
        # Hash the token with secret key
        hash_input = f"{token}{settings.SECRET_KEY}".encode()
        hash_bytes = hashlib.sha256(hash_input).digest()
        
        # Convert to alphanumeric code
        code = ""
        for byte in hash_bytes:
            code += self.CODE_ALPHABET[byte % len(self.CODE_ALPHABET)]
            if len(code) >= self.CODE_LENGTH:
                break
        
        return code
    
    def generate_short_code(self):
        """Generate a random short code (for leaflet codes, not auth tokens)."""
        return "".join(
            secrets.choice(self.CODE_ALPHABET)
            for _ in range(self.CODE_LENGTH)
        )


# Singleton instance
short_code_token_generator = ShortCodeTokenGenerator()
