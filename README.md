# Link Server / Lona API

## Overview

`link-server` is a Flask-based API service for managing hotspot vouchers, user sessions, device balances, and administrative advertisement bundles. It is built with Flask, Flask-RESTX, MongoDB integration, JWT authentication, and a reverse-proxy middleware layer.

## Project Structure

- `main.py` - Application entry point exposing the Flask `app` object.
- `config.py` - Configuration classes for `ProductionConfig` and `DevelopmentConfig`.
- `gunicorn_conf.py` - Gunicorn server configuration.
- `requirements.txt` - Python dependency list.
- `service.toml` - Example systemd unit file for service deployment.
- `setup.md` - Deployment guide for systemd/Gunicorn.
- `testsetup.md` - Additional test environment notes.

### App package

- `app/__init__.py` - Creates and configures the Flask app, API namespaces, JWT, CORS, and proxy middleware.
- `app/extensions.py` - Helper functions, authentication decorators, template rendering, and MongoDB utility support.
- `app/routes/link.py` - Primary device, hotspot, and system API endpoints for voucher redemption, login, balance, and session management.
- `app/routes/admin.py` - Administrative endpoints for bundle management, ads, and reporting.
- `app/routes/errors.py` - Custom HTTP exception classes used across the API.
- `app/services/database_service.py` - MongoDB data access layer, user handling, voucher queries, and admin record helpers.
- `app/services/analytics_service.py` - Analytics and reporting helpers.
- `app/services/mail_service.py` - Email and notification helpers.
- `app/utils/logger.py` - Logging configuration helpers.
- `app/utils/proxy.py` - Reverse proxy middleware with IP whitelist enforcement.

## Running the Server

### Prerequisites

- Python 3.12
- MongoDB connectivity available via the configured MongoDB URI
- Required packages installed from `requirements.txt`

### Install dependencies

```bash
cd /workspaces/link-server
python3 -m pip install -r requirements.txt
```

### Start the application

```bash
cd /workspaces/link-server
python3 -m gunicorn -c gunicorn_conf.py main:app
```

### Validation

- The app starts Gunicorn and listens on `http://0.0.0.0:8000`
- A socket bind on port `8000` was confirmed
- A request from the allowed source IP returned `HTTP/1.1 200 OK`

## Configuration

The project reads configuration from `config.ProductionConfig` by default.

Environment variables:

- `SECRET_KEY` - Flask secret key
- `JWT_SECRET_KEY` - JWT signing key

## Security Notes

- Requests are filtered by `app/utils/proxy.py` using an IP whitelist.
- The allowed IP list is configured in `app/__init__.py`.
- The proxy middleware currently blocks `127.0.0.1` unless explicitly added.
- `admin/login` currently uses a hardcoded password placeholder; this should be replaced with secure authentication in production.

## API Endpoints

### Device Namespace (`/asherlink/device`)

- `POST /asherlink/device/login` - Authenticate a user and associate a device MAC.
- `POST /asherlink/device/redeem` - Redeem a voucher PIN or local token.
- `POST /asherlink/device/refresh` - Refresh a session and reassign MAC if needed.
- `GET /asherlink/device/balance/<identifier>` - Get balance by MAC or user ID.

### Admin Namespace (`/asherlink/admin`)

- `GET /asherlink/admin/bundles` - List bundles.
- `POST /asherlink/admin/bundles` - Create a new bundle.
- `DELETE /asherlink/admin/bundles/<bundle_id>` - Delete a bundle.
- `PATCH /asherlink/admin/ads/manage/<ad_id>` - Toggle ad active status.
- `DELETE /asherlink/admin/ads/manage/<ad_id>` - Delete an ad.
- `POST /asherlink/admin/ads/create` - Upload ad images and create an ad record.
- `GET /asherlink/admin/ads/report` - Generate a PDF ad performance report.
- `POST /asherlink/admin/login` - Admin authentication endpoint.

## Deployment

Use the provided `gunicorn_conf.py` in production to run the app with Tornado workers.

Example service unit:

- `service.toml` includes a sample systemd configuration with `ExecStart` pointing to a virtual environment gunicorn binary.

## Notes

- The application is designed to use MongoDB collections for users, vouchers, bundles, logs, advertisements, and sessions.
- The codebase currently mixes MongoDB logic with authentication and session management; further separation is recommended for production hardening.

## Troubleshooting

- If the app rejects requests from local clients, verify `app/__init__.py` allowed IPs and the proxy whitelist in `app/utils/proxy.py`.
- If the server fails to start, ensure all packages are installed and the correct Python interpreter is used.
- Use `journalctl -u <service-name> -f` when running via systemd.
