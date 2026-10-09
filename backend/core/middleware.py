"""Keep private data off caches and restrict production ingress to the Pages proxy."""
from secrets import compare_digest

from django.conf import settings
from django.http import HttpResponseNotFound, JsonResponse
from django.utils.cache import patch_vary_headers


class PrivateAPIMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/media/') or (not settings.DEBUG and request.path.startswith('/admin/')):
            response = HttpResponseNotFound()
        elif settings.DJANGO_REQUIRE_PROXY_SECRET and not compare_digest(
            request.headers.get('X-Hongik-Proxy-Secret', ''), settings.HONGIK_PROXY_SECRET
        ):
            response = JsonResponse({'error': 'Forbidden'}, status=403)
        else:
            response = self.get_response(request)
        if request.path.startswith(('/api/', '/media/', '/admin/')):
            response.setdefault('Cache-Control', 'private, no-store, max-age=0')
            response['CDN-Cache-Control'] = 'no-store'
            response['Cloudflare-CDN-Cache-Control'] = 'no-store'
            patch_vary_headers(response, ['Authorization'])
        return response
