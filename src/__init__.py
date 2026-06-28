"""Package init.

We inject the operating system's trust store into Python's TLS layer here, before
any HTTP/WebSocket client is used. On managed laptops behind a corporate
TLS-inspection proxy, the proxy re-signs HTTPS traffic with a company root CA that
macOS trusts but Python's bundled `certifi` does not. Without this, calls to
api.twilio.com / api.openai.com fail with "self-signed certificate in certificate
chain". `truststore` makes Python validate against the OS trust store instead, which
includes that corporate CA.

This runs on `import src` (which every entrypoint does early), so it takes effect
before the first network call. It is a best-effort no-op if truststore is missing.
"""
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass
