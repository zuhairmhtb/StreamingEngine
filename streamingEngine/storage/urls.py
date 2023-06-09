from django.urls import path

from . import views
urlpatterns = [
    path('upload/', views.StorageView.as_view(), name='upload'),
]
