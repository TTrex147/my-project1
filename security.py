"""
security.py
1. PasswordHasher  - saves passwords safely (never as plain text)
2. ContentFilter   - detects offensive / inappropriate words in feedback
"""
import hashlib
import hmac
import re
import secrets


class PasswordHasher:
    ITERATIONS = 120_000

    @staticmethod
    def hash(password):
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                     PasswordHasher.ITERATIONS)
        return f"{salt}${digest.hex()}"

    @staticmethod
    def verify(password, stored):
        try:
            salt, digest = stored.split("$")
            check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                        PasswordHasher.ITERATIONS)
            return hmac.compare_digest(check.hex(), digest)
        except (ValueError, AttributeError):
            return False


class ContentFilter:
    """
    Simple word-list filter. You can add or remove words in BAD_WORDS.
    It also catches tricks like 'f u c k', 'sh1t' or 'fuuuck'.
    """
    BAD_WORDS = {
        # English
        "fuck", "fucking", "fucker", "shit", "bullshit", "bitch", "asshole", "bastard",
        "dick", "cunt", "slut", "whore", "idiot", "stupid", "moron", "dumbass", "retard",
        # Filipino
        "putangina", "tangina", "putang", "gago", "gaga", "bobo", "tanga", "ulol",
        "tarantado", "pakyu", "pakshet", "inutil",
    }
    LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
                          "7": "t", "@": "a", "$": "s", "!": "i"})

    def find_bad_words(self, text):
        clean = text.lower().translate(self.LEET)
        clean = re.sub(r"(.)\1{2,}", r"\1", clean)          # fuuuck -> fuck
        words = re.findall(r"[a-z]+", clean)
        found = [w for w in words if w in self.BAD_WORDS]
        # catch spaced-out letters like "f u c k"
        squeezed = re.sub(r"(?<=\b[a-z]) (?=[a-z]\b)", "", clean)
        found += [w for w in re.findall(r"[a-z]+", squeezed)
                  if w in self.BAD_WORDS and w not in found]
        return found

    def is_clean(self, text):
        return not self.find_bad_words(text)
