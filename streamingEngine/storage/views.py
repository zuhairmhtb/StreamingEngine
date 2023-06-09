from django.shortcuts import render
from django.http import HttpResponse, HttpRequest

# Create your views here.
def upload(request:HttpRequest):
    file = request.GET.get('file', '')
    return HttpResponse(f"Uploading file {file}")