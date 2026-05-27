from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def append_query_params(base_url: str, **params: str) -> str:
    """Append query parameters to a URL, correctly handling existing query strings.

    Args:
        base_url: The base URL to append parameters to
        **params: Keyword arguments representing query parameters to add

    Returns:
        The URL with all parameters appended as a query string
    """
    parsed = urlparse(base_url)
    qs: dict[str, list[str]] = parse_qs(parsed.query, keep_blank_values=True)
    qs.update({k: [v] for k, v in params.items()})
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
