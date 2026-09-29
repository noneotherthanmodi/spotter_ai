from django.urls import path
from routing import views

urlpatterns = [
    path("api/route/", views.plan_route, name="plan-route"),
    path("api/health/", views.health, name="health"),
]
