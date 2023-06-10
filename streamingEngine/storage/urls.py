from django.urls import path

from . import views
urlpatterns = [
    path('video/', views.StorageView.as_view(), name='upload'),
]
