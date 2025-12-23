"""Base HTTP client with retry and timeout support."""

from abc import ABC
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..exceptions import HTTPError, RateLimitError
from ..utils.logging import get_logger

logger = get_logger("clients.base")


class BaseHTTPClient(ABC):
    """Base HTTP client with retry and timeout support."""

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        """Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            backoff_factor: Backoff factor for retry delays.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a session with retry strategy."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "DELETE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _request(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Execute HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.).
            url: Request URL.
            headers: Optional request headers.
            **kwargs: Additional arguments passed to requests.

        Returns:
            Response object.

        Raises:
            HTTPError: If request fails.
            RateLimitError: If rate limit is exceeded.
        """
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )

            # Check for rate limiting
            if response.status_code == 403:
                if "rate limit" in response.text.lower():
                    logger.error(f"Rate limit exceeded for {url}")
                    raise RateLimitError(f"Rate limit exceeded for {url}")

            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
            raise HTTPError(f"Request timeout: {url}") from None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {url} - {e}")
            raise HTTPError(f"Connection error: {url}") from e
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {url} - {e}")
            raise HTTPError(f"HTTP error: {url} - {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url} - {e}")
            raise HTTPError(f"Request failed: {url}") from e

    def get(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Execute GET request."""
        return self._request("GET", url, headers=headers, **kwargs)

    def post(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Execute POST request."""
        return self._request("POST", url, headers=headers, **kwargs)

    def delete(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Execute DELETE request."""
        return self._request("DELETE", url, headers=headers, **kwargs)

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self) -> "BaseHTTPClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
