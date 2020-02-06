## settings.py

The following are possible values for your Django `settings.py` and their purpose.

<!-- * `DJANGO_ATHM_CALLBACK_VIEW` -  -->
* `DJANGO_ATHM_SANDBOX_MODE` - Whether or not to use the ATH Móvil API in sandbox mode. 
    * Type: Boolean
    * Required: No
    * Default: `False`
* `DJANGO_ATHM_PUBLIC_TOKEN` - Your public token. Available in the ATH Móvil Business app.
    * Type: String
    * Required: Yes, except when `DJANGO_ATHM_SANDBOX_MODE` is `True`
    * Default: `None`
* `DJANGO_ATHM_PRIVATE_TOKEN` - Your private token. Available in the ATH Móvil Business app.
    * Type: String
    * Required: Yes, except when `DJANGO_ATHM_SANDBOX_MODE` is `True`
    * Default: `None`


## athm_button

The following are the available configuration options for controlling the behavior of the `athm_button` template tag.

* `public_token` - You can overwrite the public token when invoking the template tag. Using this, you can control which business is on the receiving end of the purchase.
    * Type: String
    * Default: `settings.DJANGO_ATHM_PUBLIC_TOKEN`

* `timeout` - Seconds before the ATH Móvil checkout process times out.
    * Type: Integer
    * Values: Integer between 120 and 600
    * Default: 600 (10 minutes)

* `theme` - Determines the theme of the ATH Móvil checkout button.
    * Type: String
    * Values: "btn", "btn-dark" or "btn-light"
    * Default: "btn" 
    
* `language` - Determines the language on the ATH Móvil checkout button.
    * Type: String
    * Values: "en" or "es"
    * Default: "en" 
    