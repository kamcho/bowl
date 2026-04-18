import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class PinValidator:
    """
    Validates that the password is exactly a 4-digit numeric PIN.
    """
    def validate(self, password, user=None):
        if not re.fullmatch(r'\d{4}', password):
            raise ValidationError(
                _('PIN must be exactly 4 digits.'),
                code='invalid_pin',
            )

    def get_help_text(self):
        return _('Your PIN must be exactly 4 digits.')
