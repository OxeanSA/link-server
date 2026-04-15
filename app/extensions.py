from app.services.database_service import (
    get_user,
    get_user_chats,
)
from flask import make_response, request
from app.utils.logger import debug_logger
from jinja2 import Environment, FileSystemLoader
from app.routes.errors import BadTokenError
from datetime import datetime
from functools import wraps
# from app.models.models import HybridRecommender for rtx
from flask import g
import sqlite3
import timeago
import string
import socket
import random
import re
import os

_versions = [
    "1.0",
    "1.0.1",
    "1.0.2",
    "beta"
]

uri = "mongodb+srv://oxeansa:oxeanpass1@cluster0.sh0vm.mongodb.net/?appName=Cluster0"

def raw_db_con():
    db = sqlite3.connect(os.path.dirname(os.path.abspath(__file__)) + "/resources/rawdb/db1.db")
    db.row_factory = sqlite3.Row
    return db

def get_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def is_email(email):
    """
    Validates if the given string is a valid email address.
    """
    pattern = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
    return re.fullmatch(pattern, email)

def authenticate(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        req = request.get_json()
        _id = req.get('user_id')
        user = get_user(_id)
        access_token = request.headers.get('Authorization').replace('Bearer ', '')
        refresh_token = request.headers.get('X-Refresh-Token')
        public_key = request.headers.get('X-Public-Key')
        if user:
            print(public_key)
            if user['access_token'] == access_token:
                if user['refresh_token'] == refresh_token:
                    return func(*args, **kwargs)
                else:
                    print('invalid refresh token')
                    raise BadTokenError
            else:
                print('invalid token')
                raise BadTokenError
        else:
            print('user not found')
            raise BadTokenError
    return decorator

ADMIN_TOKEN = "AsherLink_Secure_2026_Admin"

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Admin-Token')
        if not token or token != ADMIN_TOKEN:
            return {"status": "error", "message": "Unauthorized access"}, 401
        return f(*args, **kwargs)
    return decorated
    
_Paths = {
    "login": "layouts/login.asp",
    "signup": "layouts/signup.asp",
    "home": "layouts/home.asp",
    "403": "v1/err_pages/403.asp",
    "404": "v1/err_pages/404.asp",
    "500": "v1/err_pages/500.asp"
}

# TODO: Separate decorator for specific layouts

def getTemplate(page, _data, version):
    data = []
    _vars = ""

    try:
        # Validate user_id
        if _data:
            user_id = _data.get('user_id')
            if not user_id:
                user_id = _data['user'].get('user_id')
                if not user_id:
                    raise ValueError("Missing or invalid user_id in _data")
        else:
            user_id = None
            _data = None

        # Handle different pages
        if page == "home":
#            user_id = "z80g82dk1qtt3nyvz2n9rv9kocbts7l5h6it"
            try:
                page = "home"
                # Create an instance of HybridRecommender and call recommend_posts
                #recommender = AdsRecommender()
                
                #recommended_ads = recommender.recommend_ads(user_id, 16)

                # Transform data into the format expected by the template
                #data = [
                    #{
                    #    "post_id": post["post_id"],
                    #    "content": post.get("content", ""),
                    #    "user": {
                    #        "user_id": post["user"].get("user_id", ""),
                    #        "username": post["user"].get("username", ""),
                    #        "first_name": post["user"].get("first_name", ""),
                    #        "last_name": post["user"].get("last_name", ""),
                    #        "profile": post["user"].get("profile", ""),
                    #        "is_verified": post["user"].get("is_verified")
                    #    },
                    #    "post_tags": post.get("post_tags", []),
                    #    "created_at": post.get("created_at", ""),
                    #   "post_url": post.get("post_url", ""),
                    #    "post_type": post.get("post_type", ""),
                    #   "likes": post.get("likes", []),
                    #    "comments": post.get("comments", []),
                    #    "priority": post.get("priority", "")
                    #}
                    #for post in recommended_posts
                #]
                # Debugging output
                #if not data:
                #    debug_logger.info(f"No data returned by recommend_posts for user_id: {user_id}")

            except Exception as e:
                debug_logger.error(f"Error in recommend_posts: {e}")
                data = []  # Fallback to empty data


        # Handle invalid version
        if version not in _versions:
            page = "404"

        # Render the template
        env = Environment(loader=FileSystemLoader(os.path.dirname(__file__) + "/templates/"))
        t = env.get_template(_Paths[page])
        return t.render(data=data, user_data=_data, pape=page, var=_vars, _ipaddr=get_ip(), helpers=PageHelpers)

    except Exception as e:
        print(f"Error in getTemplate: {e}")
        return make_response("", 404)

class PageHelpers:
    def _tags(regex, text):
        tag_list = re.findall(regex, text)
        for tag in tag_list:
            return tag

    def _random_str(length, st='chars'):
        strc = None
        if st == 'chars':
            strc = string.ascii_letters
        elif st == 'digits':
            strc = string.digits
        elif st == 'lowerdouble':
            strc = string.ascii_lowercase + string.digits
        result_str = ''.join(random.choice(strc) for i in range(length))
        return (result_str)

    def _time(created_at):
        try:
            # If created_at is a string, parse it into a datetime object
            if isinstance(created_at, str):
                try:
                    # Handle ISO 8601 format (e.g., "2025-04-23T12:00:00Z")
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    # Handle other formats if needed (e.g., "%d/%m/%Y %H:%M:%S")
                    created_at = datetime.strptime(created_at, "%d/%m/%Y %H:%M:%S")

            # Ensure created_at is a datetime object
            if not isinstance(created_at, datetime):
                debug_logger.error("created_at is not a datetime object")
                raise ValueError("Invalid datetime format")

            # Get the current time
            now = datetime.now()

            # Generate a human-readable relative time
            relative_time = timeago.format(created_at, now, 'en_short')

            # Handle cases where the time is in months or years
            if "mo" in relative_time or "yr" in relative_time:
                relative_time = created_at.strftime("%d %b %Y")  # Format as '23 Apr 2025'

            return relative_time

        except Exception as e:
            debug_logger.error(f"Error in _time: {e}")
            print(f"Error in _time: {e}")
            return "Invalid date"

    def _trim(text, length):
        if len(text) > length:
            text = text[0:+length]+".."
            return text
        else:
            return text

    def _look(intg, lst):
        try:
            if intg in lst:
                return True
            else:
                return False
        except:
            return False
        
def handle_requests(app):
    @app.after_request
    def apply_caching(response):
        # Security headers
        response.headers['Strict-Transport-Security'] = 'max-age=20; includeSubDomains; preload'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        """
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self';"
        )
        """
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = (
            "geolocation=(), microphone=(), camera=(), payment=(), fullscreen=()"
        )
        response.headers['Access-Control-Allow-Origin'] = '*'  # Adjust as needed for CORS
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = (
            'Content-Type, Authorization, X-Requested-With, X-Refresh-Token, X-Public-Key'
        )
        return response
    """
    @app.before_request
    def before_request():
        # Set a default value for g.user
        g.user = None
        
        # Check if the request has an Authorization header
        access_token = request.headers.get('Authorization')
        if access_token:
            access_token = access_token.replace('Bearer ', '')
            user = get_user_by_token(access_token)
            if user:
                g.user = user
            else:
                raise BadTokenError("Invalid access token")
    return apply_caching, before_request
    """
