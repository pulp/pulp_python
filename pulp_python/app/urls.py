from django.conf.urls import url

from .viewsets import PythonOneShotUploadViewSet


urlpatterns = [
    url(r'python/upload/$', PythonOneShotUploadViewSet.as_view({'post': 'create'}))
]
