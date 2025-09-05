from django.urls import re_path, path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from messages import consumers

websocket_urlpatterns = [
    path('ws/messages/', consumers.MessageConsumer.as_asgi()),
    path('ws/notifications/', consumers.SystemNotificationConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})