from clinicflow.access import get_staff_role

def role_context_processor(request):
    if request.user.is_authenticated:
        return {'user_role': get_staff_role(request.user)}
    return {'user_role': None}
