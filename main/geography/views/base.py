# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.context_processors import csrf
from django.shortcuts import render_to_response
from geography.utils import JsonResponse, StaticFiles
from geography.views import get_user
from django.http import HttpResponse
from geography.models import Place
import json
import os
from django.core.servers.basehttp import FileWrapper


def home(request):
    JS_FILES = (
        "static/lib/js/fallbacks.js",
        "static/lib/js/jquery-1.11.0.min.js",
        "static/lib/js/bootstrap.js",
        "static/lib/angular-1.2.9/angular.min.js",
        "static/lib/angular-1.2.9/angular-route.min.js",
        "static/lib/angular-1.2.9/angular-cookies.min.js",
        "static/lib/angular-1.2.9/angular-animate.min.js",
        "static/lib/angular-1.2.9/i18n/angular-locale_cs.js",
        "static/lib/js/raphael.js",
        "static/lib/js/raphael.pan-zoom.min.js",
        "static/lib/js/kartograph.js",
        "static/lib/js/chroma.min.js",
        "static/lib/js/jquery.qtip.min.js",
        "static/lib/js/angulartics.min.js",
        "static/lib/js/angulartics-google-analytics.min.js",
        "static/js/map.js",
        "static/js/app.js",
        "static/js/controllers.js",
        "static/js/services.js",
        "static/js/filters.js",
        "static/js/directives.js"
    )
    CSS_FILES = (
        "static/lib/css/bootstrap.min.css",
        "static/css/app.css",
        "static/lib/css/flags.css",
        "static/lib/css/tips.css",
        "static/css/map.css"
    )
    request.META["CSRF_COOKIE_USED"] = True
    if not settings.DEBUG:
        title = ''
    elif settings.ON_PRODUCTION:
        title = 'Stage - '
    else:
        title = 'Loc - '
    c = {
        'title': title,
        'isProduction': settings.ON_PRODUCTION,
        'css_files': StaticFiles.add_hash(CSS_FILES),
        'js_files': StaticFiles.add_hash(JS_FILES),
        'continents': Place.objects.get_continents(),
        'states': Place.objects.get_states_with_map(),
        'hashes': json.dumps(settings.HASHES),
        'user': get_user(request),
    }
    c.update(csrf(request))
    return render_to_response('home/home.html', c)


def csv_view(request, model):
    if not request.user.is_staff:
        response = {
            "error": "Permission denied: you need to be staff member. If you think you should be able to access logs, contact admins."}
        return JsonResponse(response)
    allowed_models = [
        'place',
        'placerelation',
        'answer',
        'answer_options']
    if model not in allowed_models:
        response = {"error": "the requested model '" + model + "' is not valid"}
        return JsonResponse(response)
    csv_file = "geography." + model + ".zip"
    logpath = os.path.join(settings.MEDIA_ROOT, csv_file)
    response = HttpResponse(FileWrapper(open(logpath)), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=' + csv_file
    return response
