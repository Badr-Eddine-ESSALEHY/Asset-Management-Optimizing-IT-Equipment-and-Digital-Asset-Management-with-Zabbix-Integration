# parcInfoCP/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('admin/', admin.site.urls),

    path('accounts/login/', auth_views.LoginView.as_view(template_name='members/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('', include('pages.urls')),

    # Wrap the include calls with login_required
    path('members/', include('members.urls', namespace='members')),
    path('assets/', include('assets.urls', namespace='assets')),
    path('messages/', include('messages.urls', namespace='messages')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)