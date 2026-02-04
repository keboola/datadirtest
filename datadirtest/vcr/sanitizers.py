"""
Sanitizers for VCR cassettes.

This module provides pluggable sanitization classes that can be used to
redact sensitive information from recorded HTTP interactions.
"""

import re
from abc import ABC
from typing import Any, Dict, List, Optional


class BaseSanitizer(ABC):
    """
    Base class for request/response sanitization.

    Subclass this to create custom sanitizers that can modify
    requests and responses before they are recorded to cassettes.
    """

    def before_record_request(self, request: Any) -> Any:
        """
        Sanitize request before recording. Override in subclass.

        Args:
            request: The vcrpy request object

        Returns:
            The sanitized request object
        """
        return request

    def before_record_response(self, response: Dict) -> Dict:
        """
        Sanitize response before recording. Override in subclass.

        Args:
            response: The vcrpy response dictionary

        Returns:
            The sanitized response dictionary
        """
        return response


class TokenSanitizer(BaseSanitizer):
    """
    Replaces auth tokens and secrets with placeholders.

    Searches through request URIs, headers, and body for the specified
    tokens and replaces them with the replacement string.
    """

    def __init__(self, tokens: List[str], replacement: str = "REDACTED"):
        """
        Args:
            tokens: List of token values to sanitize
            replacement: Replacement string for tokens
        """
        self.tokens = [t for t in tokens if t]  # Filter out empty strings
        self.replacement = replacement

    def _sanitize_string(self, value: str) -> str:
        """Replace all tokens in a string."""
        result = value
        for token in self.tokens:
            if token and token in result:
                result = result.replace(token, self.replacement)
        return result

    def _sanitize_dict(self, d: Dict) -> Dict:
        """Recursively sanitize all string values in a dictionary."""
        result = {}
        for key, value in d.items():
            if isinstance(value, str):
                result[key] = self._sanitize_string(value)
            elif isinstance(value, dict):
                result[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = self._sanitize_list(value)
            else:
                result[key] = value
        return result

    def _sanitize_list(self, lst: List) -> List:
        """Recursively sanitize all items in a list."""
        result = []
        for item in lst:
            if isinstance(item, str):
                result.append(self._sanitize_string(item))
            elif isinstance(item, dict):
                result.append(self._sanitize_dict(item))
            elif isinstance(item, list):
                result.append(self._sanitize_list(item))
            else:
                result.append(item)
        return result

    def before_record_request(self, request: Any) -> Any:
        """Sanitize tokens in request URI, headers, and body."""
        # Sanitize URI
        if hasattr(request, "uri"):
            request.uri = self._sanitize_string(request.uri)

        # Sanitize headers
        if hasattr(request, "headers"):
            for header_name in list(request.headers.keys()):
                values = request.headers.get(header_name, [])
                if isinstance(values, list):
                    request.headers[header_name] = [
                        self._sanitize_string(v) if isinstance(v, str) else v for v in values
                    ]
                elif isinstance(values, str):
                    request.headers[header_name] = self._sanitize_string(values)

        # Sanitize body
        if hasattr(request, "body") and request.body:
            if isinstance(request.body, str):
                request.body = self._sanitize_string(request.body)
            elif isinstance(request.body, bytes):
                body_str = request.body.decode("utf-8", errors="ignore")
                sanitized = self._sanitize_string(body_str)
                request.body = sanitized.encode("utf-8")

        return request

    def before_record_response(self, response: Dict) -> Dict:
        """Sanitize tokens in response body and headers."""
        if "body" in response:
            body = response["body"]
            if isinstance(body, dict) and "string" in body:
                if isinstance(body["string"], str):
                    body["string"] = self._sanitize_string(body["string"])
                elif isinstance(body["string"], bytes):
                    body_str = body["string"].decode("utf-8", errors="ignore")
                    body["string"] = self._sanitize_string(body_str).encode("utf-8")

        if "headers" in response:
            response["headers"] = self._sanitize_dict(response["headers"])

        return response


class HeaderSanitizer(BaseSanitizer):
    """
    Filters headers to whitelist only safe ones.

    Removes potentially sensitive headers from requests and responses,
    keeping only those in the whitelist.
    """

    # Default safe headers that don't contain sensitive info
    DEFAULT_SAFE_HEADERS = [
        "content-type",
        "content-length",
        "accept",
        "accept-encoding",
        "accept-language",
        "cache-control",
        "connection",
        "host",
        "user-agent",
        "date",
        "server",
        "transfer-encoding",
        "vary",
        "x-request-id",
        "x-correlation-id",
    ]

    def __init__(
        self,
        safe_headers: Optional[List[str]] = None,
        additional_safe_headers: Optional[List[str]] = None,
        headers_to_remove: Optional[List[str]] = None,
    ):
        """
        Args:
            safe_headers: Complete list of headers to keep (overrides defaults)
            additional_safe_headers: Headers to add to the default safe list
            headers_to_remove: Specific headers to always remove
        """
        if safe_headers is not None:
            self.safe_headers = set(h.lower() for h in safe_headers)
        else:
            self.safe_headers = set(h.lower() for h in self.DEFAULT_SAFE_HEADERS)
            if additional_safe_headers:
                self.safe_headers.update(h.lower() for h in additional_safe_headers)

        self.headers_to_remove = set(h.lower() for h in (headers_to_remove or []))

    def _filter_headers(self, headers: Dict) -> Dict:
        """Filter headers to only include safe ones."""
        result = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in self.headers_to_remove:
                continue
            if key_lower in self.safe_headers:
                result[key] = value
        return result

    def before_record_request(self, request: Any) -> Any:
        """Remove non-safe headers from request."""
        if hasattr(request, "headers"):
            request.headers = self._filter_headers(request.headers)
        return request

    def before_record_response(self, response: Dict) -> Dict:
        """Remove non-safe headers from response."""
        if "headers" in response:
            response["headers"] = self._filter_headers(response["headers"])
        return response


class UrlPatternSanitizer(BaseSanitizer):
    """
    Sanitizes URL patterns using regex replacement.

    Useful for redacting dynamic IDs, account numbers, or other
    sensitive data embedded in URLs.
    """

    def __init__(self, patterns: List[tuple]):
        """
        Args:
            patterns: List of (pattern, replacement) tuples.
                      Pattern is a regex string, replacement is the string
                      to use for matches.
        """
        self.patterns = [(re.compile(p), r) for p, r in patterns]

    def _sanitize_url(self, url: str) -> str:
        """Apply all patterns to the URL."""
        result = url
        for pattern, replacement in self.patterns:
            result = pattern.sub(replacement, result)
        return result

    def before_record_request(self, request: Any) -> Any:
        """Sanitize URL patterns in request URI."""
        if hasattr(request, "uri"):
            request.uri = self._sanitize_url(request.uri)
        return request


class BodyFieldSanitizer(BaseSanitizer):
    """
    Sanitizes specific fields in JSON request/response bodies.

    Useful for redacting specific known fields while preserving
    the overall structure of the data.
    """

    def __init__(
        self,
        fields: List[str],
        replacement: str = "REDACTED",
        nested: bool = True,
    ):
        """
        Args:
            fields: List of field names to sanitize
            replacement: Replacement value for the fields
            nested: Whether to search nested dictionaries
        """
        self.fields = set(fields)
        self.replacement = replacement
        self.nested = nested

    def _sanitize_dict(self, d: Dict) -> Dict:
        """Sanitize specified fields in a dictionary."""
        result = {}
        for key, value in d.items():
            if key in self.fields:
                result[key] = self.replacement
            elif self.nested and isinstance(value, dict):
                result[key] = self._sanitize_dict(value)
            elif self.nested and isinstance(value, list):
                result[key] = [self._sanitize_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result

    def _sanitize_body(self, body: Any) -> Any:
        """Parse and sanitize JSON body."""
        import json

        if not body:
            return body

        try:
            if isinstance(body, bytes):
                data = json.loads(body.decode("utf-8"))
                sanitized = self._sanitize_dict(data)
                return json.dumps(sanitized).encode("utf-8")
            elif isinstance(body, str):
                data = json.loads(body)
                sanitized = self._sanitize_dict(data)
                return json.dumps(sanitized)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        return body

    def before_record_request(self, request: Any) -> Any:
        """Sanitize fields in request body."""
        if hasattr(request, "body") and request.body:
            request.body = self._sanitize_body(request.body)
        return request

    def before_record_response(self, response: Dict) -> Dict:
        """Sanitize fields in response body."""
        if "body" in response:
            body = response["body"]
            if isinstance(body, dict) and "string" in body:
                body["string"] = self._sanitize_body(body["string"])
        return response


class CompositeSanitizer(BaseSanitizer):
    """
    Combines multiple sanitizers into a single sanitizer.

    Sanitizers are applied in the order they are provided.
    """

    def __init__(self, sanitizers: List[BaseSanitizer]):
        """
        Args:
            sanitizers: List of sanitizers to apply in order
        """
        self.sanitizers = sanitizers

    def before_record_request(self, request: Any) -> Any:
        """Apply all sanitizers to the request."""
        for sanitizer in self.sanitizers:
            request = sanitizer.before_record_request(request)
        return request

    def before_record_response(self, response: Dict) -> Dict:
        """Apply all sanitizers to the response."""
        for sanitizer in self.sanitizers:
            response = sanitizer.before_record_response(response)
        return response


def create_default_sanitizer(secrets: Dict[str, Any]) -> CompositeSanitizer:
    """
    Create a default sanitizer configuration.

    This creates a composite sanitizer that:
    1. Removes sensitive headers (Authorization, Cookie, etc.)
    2. Redacts any secret values found in the config

    Args:
        secrets: Dictionary of secret values to redact

    Returns:
        A CompositeSanitizer with sensible defaults
    """

    # Extract all string values from secrets recursively
    def extract_values(d: Dict, values: List[str]) -> List[str]:
        for key, value in d.items():
            if isinstance(value, str) and value:
                values.append(value)
            elif isinstance(value, dict):
                extract_values(value, values)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item:
                        values.append(item)
                    elif isinstance(item, dict):
                        extract_values(item, values)
        return values

    secret_values = extract_values(secrets, [])

    sanitizers = [
        HeaderSanitizer(
            headers_to_remove=[
                "authorization",
                "cookie",
                "set-cookie",
                "x-api-key",
                "api-key",
                "x-auth-token",
                "x-access-token",
            ]
        ),
    ]

    if secret_values:
        sanitizers.append(TokenSanitizer(tokens=secret_values))

    return CompositeSanitizer(sanitizers)
