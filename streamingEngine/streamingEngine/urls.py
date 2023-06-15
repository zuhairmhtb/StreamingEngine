"""
URL configuration for streamingEngine project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('streaming/<str:file>/', views.StreamingView.as_view(), name='stream'),
    path('playlist/', views.PlayList.as_view(), name='playlist'),
    path('playlist/<path:segment_name>/', views.PlayList.as_view(), name='playlist'),
    path('keys/<str:id>/', views.KeysView.as_view(), name='keys'),
    path('vtt/<str:id>/', views.VttView.as_view(), name='vtt')
]
