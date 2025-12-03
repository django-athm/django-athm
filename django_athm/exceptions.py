class ATHM_Error(Exception):
    """Common base class for django-athm exceptions"""

    pass


class ATHM_RefundError(ATHM_Error):
    pass


class ATHM_ReportError(ATHM_Error):
    pass
