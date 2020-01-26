from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def handle_response_payload(context, response):
    pass
