"""Bound requests before JSON parsing and prevent browser cross-origin writes."""
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

MAX_BODY_BYTES = 1024 * 1024
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def origin_tuple(value):
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        if parts.path not in {"", "/"} or parts.query or parts.fragment:
            return None
        return parts.scheme, parts.hostname.lower(), parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None


class LocalRequestGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope["headers"]}
        if scope["method"] in WRITE_METHODS:
            own_origin = origin_tuple(f"{scope['scheme']}://{headers.get('host', '')}")
            supplied = headers.get("origin")
            if (headers.get("sec-fetch-site") == "cross-site" or
                    (supplied is not None and (origin_tuple(supplied) is None or origin_tuple(supplied) != own_origin))):
                return await JSONResponse({"detail": "Cross-origin writes are not allowed"}, 403)(scope, receive, send)
            if "application/json" not in headers.get("content-type", "").lower():
                return await JSONResponse({"detail": "Use application/json"}, 415)(scope, receive, send)
        # Count actual bytes too: Content-Length alone does not bound a streamed request.
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_BODY_BYTES:
                return await JSONResponse({"detail": "Request exceeds 1 MiB"}, 413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []),
                                      (b"x-content-type-options", b"nosniff"),
                                      (b"referrer-policy", b"no-referrer")]
                if scope["path"].startswith("/api"):
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        await self.app(scope, replay, safe_send)
