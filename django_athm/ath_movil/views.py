from django.shortcuts import render


def index(request):
    context = {
        "ATHM_CONFIG": {
            "env": "sandbox",
            "public_token": "sandboxtoken01875617264",
            "lang": "en",
            "total": 1.00,
            "items": [
                {
                    "name": "First Item",
                    "description": "This is a description.",
                    "quantity": "1",
                    "price": "1.00",
                    "tax": "1.00",
                    "metadata": "metadata test",
                }
            ],
        }
    }
    return render(request, "button.html", context=context)


def transaction_detail(request):
    pass
