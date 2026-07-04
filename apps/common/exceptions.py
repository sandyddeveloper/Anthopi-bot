import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger('error')
security_logger = logging.getLogger('security')

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    request = context.get('request') if context else None
    path = request.path if request else 'Unknown path'
    method = request.method if request else 'Unknown method'

    if response is not None:
        errors = response.data
        status_code = response.status_code
        
        message = "A client or validation error occurred."
        if isinstance(errors, dict):
            if 'detail' in errors:
                message = str(errors['detail'])
                if len(errors) == 1:
                    errors = None
            elif 'non_field_errors' in errors:
                message = " ".join([str(e) for e in errors['non_field_errors']])
        elif isinstance(errors, list):
            message = " ".join([str(e) for e in errors])

        if status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]:
            user = request.user if request and request.user and request.user.is_authenticated else 'Anonymous'
            security_logger.warning(
                "Security Exception (%s) at %s %s: %s by user %s",
                status_code, method, path, message, user
            )

        response.data = {
            'success': False,
            'message': message,
            'data': None,
            'errors': errors,
            'meta': {}
        }
    else:
        if isinstance(exc, IntegrityError):
            message = "Database integrity violation. The record may already exist or violates constraints."
            logger.warning("IntegrityError at %s %s: %s", method, path, str(exc))
            response = Response(
                {
                    'success': False,
                    'message': message,
                    'data': None,
                    'errors': {'database_integrity': str(exc)},
                    'meta': {}
                },
                status=status.HTTP_409_CONFLICT
            )
        elif isinstance(exc, DjangoValidationError):
            message = "Validation error occurred."
            errors = exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            response = Response(
                {
                    'success': False,
                    'message': message,
                    'data': None,
                    'errors': errors,
                    'meta': {}
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            logger.exception("Internal Server Error at %s %s: %s", method, path, str(exc))
            response = Response(
                {
                    'success': False,
                    'message': "An internal server error occurred.",
                    'data': None,
                    'errors': {'detail': str(exc)},
                    'meta': {}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return response
