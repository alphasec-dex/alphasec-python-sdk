class AlphasecAPIError(Exception):
    """Raised when the AlphaSec API returns an invalid or unexpected response.

    Examples include non-JSON responses (e.g. load balancer HTML error pages)
    and JSON responses missing the expected ``result`` field.
    """
