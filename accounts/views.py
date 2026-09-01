import logging
import threading

from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from django.shortcuts import get_object_or_404
from .serializers import RegisterSerializer, EventSerializer, EventRegistrationSerializer
from .models import User, EventRegistration, Event
from .permissions import IsOrganizerOrReadOnly, IsEventOwner, IsParticipant
from .tasks import send_registration_email

logger = logging.getLogger(__name__)


def queue_registration_email(event_id, user_id):
    def enqueue_email():
        try:
            send_registration_email.apply_async(args=[event_id, user_id], retry=False)
        except Exception:
            logger.exception(
                'Registration email could not be queued for event_id=%s user_id=%s',
                event_id,
                user_id,
            )
            send_registration_email(event_id, user_id)

    threading.Thread(target=enqueue_email, daemon=True).start()


@extend_schema(
    tags=['Authentication'],
    summary='Register a new user',
    description='Create an organizer or participant account. No authentication required.',
    auth=[],
    request=RegisterSerializer,
    responses={
        201: RegisterSerializer,
        400: OpenApiResponse(
            description='Validation error. Check the response body for duplicate username/email or password issues.'
        ),
    },
    examples=[
        OpenApiExample(
            'Organizer signup',
            value={
                'username': 'organizer_unique_001',
                'email': 'organizer_unique_001@example.com',
                'password': 'StrongPass123!',
                'role': 'organizer',
            },
            request_only=True,
        ),
        OpenApiExample(
            'Participant signup',
            value={
                'username': 'participant_unique_001',
                'email': 'participant_unique_001@example.com',
                'password': 'StrongPass123!',
                'role': 'participant',
            },
            request_only=True,
        ),
    ],
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['username'] = user.username
        return token

@extend_schema(
    tags=['Authentication'],
    summary='Login and get JWT tokens',
    description='Use the returned access token in Swagger Authorize as: Bearer <access_token>.',
    auth=[],
    examples=[
        OpenApiExample(
            'Login request',
            value={'username': 'organizer1', 'password': 'StrongPass123!'},
            request_only=True,
        ),
    ],
)
class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


@extend_schema(
    tags=['Authentication'],
    summary='Refresh JWT access token',
    description='Send your refresh token to get a new access token. No access token required.',
    auth=[],
)
class LoginRefreshView(TokenRefreshView):
    pass


@extend_schema_view(
    get=extend_schema(
        tags=['Events'],
        summary='List events',
        description=(
            'Organizers see only events they created. Participants see all available events. '
            'JWT authentication required.'
        ),
        responses={200: EventSerializer(many=True)},
    ),
    post=extend_schema(
        tags=['Events'],
        summary='Create an event',
        description='Organizer role required. The authenticated organizer is saved as created_by.',
        request=EventSerializer,
        responses={201: EventSerializer},
        examples=[
            OpenApiExample(
                'Create event',
                value={
                    'title': 'Django Workshop',
                    'description': 'Hands-on Django REST Framework session.',
                    'start_time': '2026-09-10T10:00:00Z',
                    'end_time': '2026-09-10T12:00:00Z',
                    'location': 'Ahmedabad',
                    'capacity': 50,
                },
                request_only=True,
            ),
        ],
    ),
)
class EventListCreateView(generics.ListCreateAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsOrganizerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'organizer':
            return Event.objects.filter(created_by=user)   # Table 2: their own events
        return Event.objects.all()                          # Table 3: all available events

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=['Events'],
        summary='Get event details',
        description='JWT authentication required.',
        responses={200: EventSerializer},
    ),
    put=extend_schema(
        tags=['Events'],
        summary='Replace an event',
        description='Organizer role required. Only the organizer who created the event can update it.',
        request=EventSerializer,
        responses={200: EventSerializer},
    ),
    patch=extend_schema(
        tags=['Events'],
        summary='Partially update an event',
        description='Organizer role required. Only the organizer who created the event can update it.',
        request=EventSerializer,
        responses={200: EventSerializer},
    ),
    delete=extend_schema(
        tags=['Events'],
        summary='Delete an event',
        description='Organizer role required. Only the organizer who created the event can delete it.',
        responses={204: OpenApiResponse(description='Event deleted successfully.')},
    ),
)
class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsOrganizerOrReadOnly, IsEventOwner]


@extend_schema(
    tags=['Registrations'],
    summary='Register for an event',
    description='Participant role required. The event id comes from the URL and the user comes from the JWT token.',
    request=None,
    responses={201: EventRegistrationSerializer},
)
class EventRegistrationView(generics.CreateAPIView):
    serializer_class = EventRegistrationSerializer
    permission_classes = [IsParticipant]

    def perform_create(self, serializer):
        event = get_object_or_404(Event, pk=self.kwargs['pk'])
        if EventRegistration.objects.filter(event=event, user=self.request.user).exists():
            raise ValidationError("You're already registered for this event.")
        registration = serializer.save(event=event, user=self.request.user)
        queue_registration_email(event.id, self.request.user.id)


class EventUnRegistrationView(APIView):
    permission_classes = [IsParticipant]

    @extend_schema(
        tags=['Registrations'],
        summary='Unregister from an event',
        description='Participant role required. Removes the authenticated participant from the event.',
        request=None,
        responses={
            204: OpenApiResponse(description='Registration removed successfully.'),
            404: OpenApiResponse(description='The authenticated participant is not registered for this event.'),
        },
    )
    def post(self, request, pk):
        registration = EventRegistration.objects.filter(
            event_id=pk, user=request.user
        ).first()
        if not registration:
            return Response(
                {'detail': 'You are not registered for this event.'},
                status=status.HTTP_404_NOT_FOUND
            )
        registration.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['Registrations'],
    summary='List event participants',
    description='Only the organizer who created the event can see its participant registrations.',
    responses={200: EventRegistrationSerializer(many=True)},
)
class EventParticipantsView(generics.ListAPIView):
    serializer_class = EventRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs['pk'])

        # only the organizer who owns this event can see its participants
        if event.created_by != self.request.user:
            raise PermissionDenied("You can only view participants for your own events.")

        return EventRegistration.objects.filter(event=event)


@extend_schema(
    tags=['Registrations'],
    summary='List my registered events',
    description='Participant role required. Returns events the authenticated participant registered for.',
    responses={200: EventSerializer(many=True)},
)
class MyEventsView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsParticipant]

    def get_queryset(self):
        return Event.objects.filter(registrations__user=self.request.user)

