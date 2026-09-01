# permissions.py
from rest_framework import permissions


class IsOrganizerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:  # GET, HEAD, OPTIONS
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.role == 'organizer'

class IsEventOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        if request.method in permissions.SAFE_METHODS:
            if user.role == 'participant':
                return True                    # participants can view any event
            return obj.created_by == user      # organizers can only view their own

        # write methods (PUT/PATCH/DELETE) — only the owning organizer
        return obj.created_by == user

class IsParticipant(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'participant'