# pages/urls.py

from django.urls import path
from . import views

app_name = 'pages'
urlpatterns = [
    path('', views.landing, name='landing'),
    # CORRECTED: Call the function directly, without .as_view()
    path('dashboard/', views.dashboard, name='dashboard'),
]