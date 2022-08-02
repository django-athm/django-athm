# flake8: noqa

__version__ = "0.6.0"


def parse_version(version):
    """
    FROM: https://github.com/carltongibson/django-filter/blob/master/django_filters/__init__.py

    '0.1.2.dev1' -> (0, 1, 2, 'dev1')
    '0.1.2' -> (0, 1, 2)
    """
    v = version.split(".")
    ret = []
    for p in v:
        if p.isdigit():
            ret.append(int(p))
        else:
            ret.append(p)
    return tuple(ret)


VERSION = parse_version(__version__)
