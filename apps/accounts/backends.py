from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import exceptions

from apps.accounts.models import Admin, LabHospital, User


def get_tokens_for_admin(admin: Admin) -> dict:
    refresh = RefreshToken()
    refresh['portal'] = 'admin'
    refresh['entity_id'] = str(admin.id)
    refresh['username'] = admin.username
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'portal': 'admin',
    }


def get_tokens_for_lab(lab: LabHospital) -> dict:
    refresh = RefreshToken()
    refresh['portal'] = 'lab'
    refresh['entity_id'] = str(lab.id)
    refresh['lab_id'] = lab.lab_id
    refresh['lab_name'] = lab.name
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'portal': 'lab',
    }


def get_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken()
    refresh['portal'] = 'user'
    refresh['entity_id'] = str(user.id)
    refresh['user_uid'] = user.user_uid
    refresh['phone'] = user.phone
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'portal': 'user',
    }


class PortalAwareJWTAuthentication(JWTAuthentication):
    """
    Custom JWT auth that attaches a lightweight proxy user object
    to request.user with the portal claim and entity ID.
    Avoids hitting the Django auth user table at all.
    """

    def get_user(self, validated_token):
        try:
            portal = validated_token['portal']
            entity_id = validated_token['entity_id']
        except KeyError:
            raise InvalidToken('Token missing portal or entity_id claim.')

        try:
            if portal == 'admin':
                obj = Admin.objects.get(id=entity_id)
            elif portal == 'lab':
                obj = LabHospital.objects.get(id=entity_id)
                if not obj.is_plan_active:
                    raise exceptions.AuthenticationFailed(
                        'Lab account is inactive or plan has expired.'
                    )
            elif portal == 'user':
                obj = User.objects.get(id=entity_id, is_active=True)
            else:
                raise InvalidToken('Unknown portal claim.')
        except (Admin.DoesNotExist, LabHospital.DoesNotExist, User.DoesNotExist):
            raise InvalidToken('Entity not found.')

        # Attach portal so permission classes can read it
        obj.is_authenticated = True
        obj.portal = portal
        return obj
