from django.urls import path
from .views import (
 RegisterView, LoginView, LoginRefreshView,
 EventListCreateView, EventDetailView, 
 EventRegistrationView, EventUnRegistrationView,
 EventParticipantsView, MyEventsView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('login/refresh/', LoginRefreshView.as_view(), name='login_refresh'),

    # Events — organizer CRUD + participant read (shared view, role-based inside)
    path('events/', EventListCreateView.as_view(), name='event-list-create'),
    path('events/<int:pk>/', EventDetailView.as_view(), name='event-detail'),

    # Participant actions
    path('events/<int:pk>/register/', EventRegistrationView.as_view(), name='event-register'),
    path('events/<int:pk>/unregister/', EventUnRegistrationView.as_view(), name='event-unregister'),

    # Still missing — views not built yet, see below
    # path('events/<int:pk>/participants/', EventParticipantsView.as_view(), name='event-participants'),
    # path('my-events/', MyEventsView.as_view(), name='my-events'),

    path('events/<int:pk>/participants/', EventParticipantsView.as_view(), name='event-participants'),
    path('my-events/', MyEventsView.as_view(), name='my-events'),
]
