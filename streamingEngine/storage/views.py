from django.shortcuts import render
from django.http import HttpResponse, HttpRequest
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
# Create your views here.

@method_decorator(csrf_exempt, name='post')
class StorageView(View):

    def post(self, request:HttpRequest, *args, **kwargs):
        if not (request.FILES is None):
            file = request.FILES.get('file', None)
            if not (file is None):
                print(type(file))
        return HttpResponse("ok")

    def get(self, request:HttpRequest, *args, **kwargs):
        file = request.GET.get('file', '')
        return HttpResponse(f"Uploading file {file}")