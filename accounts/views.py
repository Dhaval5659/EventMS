from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .serializers import RegisterSerializer, EventSerializer, EventRegistrationSerializer
from .models import User, EventRegistration, Event
from .permissions import IsOrganizerOrReadOnly, IsEventOwner, IsParticipant


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

class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer

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

class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsOrganizerOrReadOnly, IsEventOwner]

class EventRegistrationView(generics.CreateAPIView):
    serializer_class = EventRegistrationSerializer
    permission_classes = [IsParticipant]

    def perform_create(self, serializer):
        event = Event.objects.get(pk=self.kwargs['pk'])
        if EventRegistration.objects.filter(event=event, user=self.request.user).exists():
            raise serializers.ValidationError("You're already registered for this event.")
        serializer.save(event=event, user=self.request.user)

class EventUnRegistrationView(APIView):
    permission_classes = [IsParticipant]

    def delete(self, request, pk):
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