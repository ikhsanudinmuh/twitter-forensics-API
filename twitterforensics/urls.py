from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('devices', views.get_devices),
    path('twitter/<id>', views.pullTwitter),
    path('twitter/chat/<id>', views.showTwitterChat),
    path('twitter/user/<id>', views.showTwitterUser),
]
