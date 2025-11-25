import json
from pathlib import Path

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

athm_config_fixture = (
    Path(__file__).resolve().parent.parent.parent / "fixtures" / "athm_config.json"
)


def home_view(request):
    with athm_config_fixture.open() as fp:
        return render(request, "home.html", context=json.load(fp))


@csrf_exempt
@require_POST
def custom_test_callback(request):
    """Test callback for configuration tests."""
    return HttpResponse(status=200)
