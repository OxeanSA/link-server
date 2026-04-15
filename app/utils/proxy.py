import logging
from ipaddress import ip_address, ip_network

class Proxy:
    def __init__(self, app=None, allowed_ips=None):
        """
        Initialize the Proxy class.

        :param app: The Flask application instance.
        :param allowed_ips: A list of allowed IP ranges (CIDR notation) for whitelisting.
        """
        self.allowed_ips = allowed_ips or []
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        Initialize the application with the ReverseProxied middleware.

        :param app: The Flask application instance.
        """
        self.app = app
        self.app.wsgi_app = ReverseProxy(self.app.wsgi_app, self.allowed_ips)
        return self


class ReverseProxy:
    """
    Middleware to secure and configure the application for reverse proxy usage.

    Features:
    - Enforces IP whitelisting.
    - Validates and sanitizes headers.
    - Enforces HTTPS scheme.
    - Logs suspicious activity.

    :param app: The WSGI application.
    :param allowed_ips: A list of allowed IP ranges (CIDR notation) for whitelisting.
    """

    def __init__(self, app, allowed_ips):
        self.app = app
        self.allowed_ips = [ip_network(ip) for ip in allowed_ips]
        self.logger = logging.getLogger("proxy")
        logging.basicConfig(level=logging.INFO)

    def __call__(self, environ, start_response):
        # Enforce IP whitelisting
        remote_addr = environ.get('REMOTE_ADDR', '')
        if not remote_addr:
            remote_addr = environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            
        if not self._is_ip_allowed(remote_addr):
            self.logger.warning(f"Unauthorized access attempt from IP: {remote_addr}")
            start_response('403 Forbidden', [('Content-Type', 'text/plain')])
            return [b"403 Forbidden: Unauthorized IP address."]
        
        # Uncomment to enforce HTTPS scheme
        """
        ## Using http for testing purposes
        # Enforce HTTPS scheme
        scheme = environ.get('HTTP_X_SCHEME', environ.get('wsgi.url_scheme', 'http'))
        if scheme.lower() != 'https':
            self.logger.warning(f"Insecure request detected from IP: {remote_addr}")
            start_response('403 Forbidden', [('Content-Type', 'text/plain')])
            return [b"403 Forbidden: HTTPS is required."]
        """
        
        # Handle request headers
        self._handle_request_headers(environ)

        # Sanitize and validate headers
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ.get('PATH_INFO', '')
            if path_info and path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        server = environ.get('HTTP_X_FORWARDED_SERVER_CUSTOM',
                             environ.get('HTTP_X_FORWARDED_SERVER', ''))
        if server:
            environ['HTTP_HOST'] = server

        # Log suspicious headers
        self._log_suspicious_headers(environ)

        return self.app(environ, start_response)

    def _is_ip_allowed(self, ip):
        """
        Check if the given IP address is allowed based on the whitelist.

        :param ip: The IP address to check.
        :return: True if the IP is allowed, False otherwise.
        """
        try:
            ip_addr = ip_address(ip)
            return any(ip_addr in network for network in self.allowed_ips)
        except ValueError:
            self.logger.error(f"Invalid IP address format: {ip}")
            return False

    def _log_suspicious_headers(self, environ):
        """
        Log any suspicious or unexpected headers.

        :param environ: The WSGI environment dictionary.
        
        suspicious_headers = ['HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP']
        for header in suspicious_headers:
            if header in environ:
                self.logger.warning(f"Suspicious header detected: {header} = {environ[header]}")
        """

    def _handle_request_headers(self, environ):
        """
        Handle and sanitize incoming request headers.

        :param environ: The WSGI environment dictionary.
        """
        allowed_headers = [
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_REAL_IP',
            'HTTP_X_SCHEME',
            'HTTP_X_SCRIPT_NAME',
            'HTTP_AUTHORIZATION',
            'HTTP_X_REFRESH_TOKEN',
            'HTTP_X_PUBLIC_KEY'
        ]
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
        sanitized_headers = {}

        for header, value in environ.items():
            if header.startswith('HTTP_') and header not in allowed_headers:
                continue
            elif header in allowed_headers:
                # Allow specific headers without modification
                sanitized_headers[header] = value
            elif header == 'REQUEST_METHOD':
                # Allow only specific HTTP methods
                if value not in methods:
                    self.logger.warning(f"Invalid HTTP method: {value}")
                    raise ValueError("Invalid HTTP method.")
            elif header == 'PATH_INFO':
                # Sanitize PATH_INFO to prevent directory traversal attacks
                sanitized_path = value.replace('../', '').replace('..\\', '')
                sanitized_headers[header] = sanitized_path
            elif header == 'QUERY_STRING':
                # Sanitize QUERY_STRING to prevent injection attacks
                sanitized_query = value.replace(';', '').replace('&', '')
                sanitized_headers[header] = sanitized_query
            elif header == 'SCRIPT_NAME':
                # Sanitize SCRIPT_NAME to prevent directory traversal attacks
                sanitized_script_name = value.replace('../', '').replace('..\\', '')
                sanitized_headers[header] = sanitized_script_name
            
            else:
                sanitized_headers[header] = value

        # Replace the original headers with sanitized headers
        environ.update(sanitized_headers)
        