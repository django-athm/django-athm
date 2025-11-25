import pytest
from django.core.exceptions import ImproperlyConfigured

from django_athm.conf import get_callback_function, is_callable
from django_athm.views import default_callback


class TestIsCallable:
    """Test the is_callable helper function."""

    def test_function_is_callable(self):
        """Test that a function is considered callable."""

        def my_func():
            pass

        assert is_callable(my_func) is True

    def test_lambda_is_callable(self):
        """Test that a lambda is considered callable."""
        assert is_callable(lambda: None) is True

    def test_class_is_not_callable(self):
        """Test that a class type is not considered callable."""

        class MyClass:
            pass

        assert is_callable(MyClass) is False

    def test_class_instance_with_call_is_callable(self):
        """Test that a class instance with __call__ is callable."""

        class CallableClass:
            def __call__(self):
                pass

        assert is_callable(CallableClass()) is True

    def test_string_is_not_callable(self):
        """Test that a string is not callable."""
        assert is_callable("some.module.function") is False


class TestGetCallbackFunction:
    """Test the get_callback_function helper."""

    def test_callable_returned_as_is(self):
        """Test that a callable function is returned unchanged."""

        def my_callback(request):
            pass

        result = get_callback_function(my_callback)
        assert result is my_callback

    def test_import_string_resolves_to_function(self):
        """Test that a dotted import path resolves to the function."""
        result = get_callback_function("django_athm.views.default_callback")
        assert result is default_callback

    def test_import_string_resolves_custom_callback(self):
        """Test that a custom callback import path resolves correctly."""
        result = get_callback_function("tests.apps.testapp.views.custom_test_callback")
        from tests.apps.testapp.views import custom_test_callback

        assert result is custom_test_callback

    def test_invalid_import_path_raises_error(self):
        """Test that an invalid import path raises ImportError."""
        with pytest.raises(ImportError):
            get_callback_function("nonexistent.module.callback")

    def test_non_callable_raises_improperly_configured(self):
        """Test that a non-callable raises ImproperlyConfigured."""
        with pytest.raises(ImproperlyConfigured):
            get_callback_function(12345)

    def test_class_raises_improperly_configured(self):
        """Test that passing a class (not instance) raises ImproperlyConfigured."""

        class MyClass:
            pass

        with pytest.raises(ImproperlyConfigured):
            get_callback_function(MyClass)


@pytest.mark.django_db
class TestCallbackViewSetting:
    """Test DJANGO_ATHM_CALLBACK_VIEW setting behavior."""

    def test_default_callback_used_when_not_configured(self, settings):
        """Test that default_callback is used when setting is not set."""
        # Ensure setting is not set
        if hasattr(settings, "DJANGO_ATHM_CALLBACK_VIEW"):
            delattr(settings, "DJANGO_ATHM_CALLBACK_VIEW")

        from django_athm.conf import Settings

        test_settings = Settings()
        callback = test_settings.get_setting("CALLBACK_VIEW")
        assert callback is default_callback

    def test_custom_callback_via_import_string(self, settings):
        """Test that a dotted import path resolves correctly."""
        settings.DJANGO_ATHM_CALLBACK_VIEW = (
            "tests.apps.testapp.views.custom_test_callback"
        )

        from django_athm.conf import Settings

        test_settings = Settings()
        callback = test_settings.get_setting("CALLBACK_VIEW")

        from tests.apps.testapp.views import custom_test_callback

        assert callback is custom_test_callback

    def test_custom_callback_via_callable(self, settings):
        """Test that a callable function works as callback."""
        from tests.apps.testapp.views import custom_test_callback

        settings.DJANGO_ATHM_CALLBACK_VIEW = custom_test_callback

        from django_athm.conf import Settings

        test_settings = Settings()
        callback = test_settings.get_setting("CALLBACK_VIEW")
        assert callback is custom_test_callback

    def test_callback_receives_request(self, settings, rf):
        """Test that custom callback receives the request object."""
        received = {"request": None}

        def tracking_callback(request):
            received["request"] = request
            from django.http import HttpResponse

            return HttpResponse(status=200)

        settings.DJANGO_ATHM_CALLBACK_VIEW = tracking_callback

        from django_athm.conf import Settings

        test_settings = Settings()
        callback = test_settings.get_setting("CALLBACK_VIEW")

        request = rf.post("/callback/", data={"referenceNumber": "test", "total": "10"})
        callback(request)

        assert received["request"] is request
