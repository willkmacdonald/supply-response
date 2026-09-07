class WorkIQError(RuntimeError):
    """Base error for bounded Work IQ failures."""


class WorkIQProtocolError(WorkIQError):
    """Work IQ returned an invalid or incomplete protocol response."""


class WorkIQResponseLimitError(WorkIQProtocolError):
    """Work IQ returned content outside the adapter's safety bounds."""
