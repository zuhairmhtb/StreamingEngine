from django.http import HttpResponse, HttpRequest
class ResponseHandlerMiddleware():
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request:HttpRequest):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        if not request.path.endswith("/"):
            request.path += "/"
        if not request.path_info.endswith("/"):
            request.path_info += "/"
        response:HttpResponse = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response