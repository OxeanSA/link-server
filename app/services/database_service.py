import logging
import os
from datetime import datetime
from functools import wraps
from random import choice
import re
from typing import Callable, Any

from bson import ObjectId
from flask import jsonify, Response
from flask_login import current_user
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.mongo_client import MongoClient
from werkzeug.security import generate_password_hash
import secrets
import string


# MongoDB connection URI
uri = "mongodb+srv://oxeansa:oxeanpass1@cluster0.sh0vm.mongodb.net/?appName=Cluster0"

# Initialize MongoDB client
client = MongoClient(uri, connectTimeoutMS=2000, serverSelectionTimeoutMS=2000)

db_cache = {}

# Helper to get specific database collections based on target
def get_collections_by_target(target):
    # Map targets to database names
    db_map = {
        "asherlink": "linkdb",
        "lona": "lonadb",
        "all": "ogdbtest1"
    }
    
    db_name = db_map.get(target, "ogdbtest1")
    
    # Reuse the database object if it's already in the cache
    if db_name not in db_cache:
        db_cache[db_name] = client.get_database(db_name)
    
    target_db = db_cache[db_name]
    
    return {
        "messages": target_db.messages,
        "notifications": target_db.notifications,
        "bundles": target_db.bundles,
        "vouchers": target_db.vouchers,
        "logs": target_db.logs,
        "advertisements": target_db.advertisements,
        "sessions": target_db.sessions,
        "pppoe_users": target_db.pppoe_users
    }

db = client.get_database("ogdbtest1")

# User Operations
def get_user(user_id, database="test"):
    """
    Gets the data of a user from the database by unique `user_id`.
    :param user_id: User ID sent.
    :returns: User Object.
    :rtype: Dict
    """
    cols = get_collections_by_target(database)
    user_data = cols["users"].find_one({"user_id": user_id})
    return user_data if user_data else None


def get_user_by_email(user, database="test"):
    """
    Gets the data of a user from the database by unique `email`.
    :param user_id: User ID sent.
    :returns: User Object.
    :rtype: Dict
    """
    cols = get_collections_by_target(database)
    user_data = cols["users"].find_one({"email": user}, {"_id": False})
    return user_data if user_data else None


def add_user(user_to_be_added, database="test"):
    cols = get_collections_by_target(database)
    cols["users"].insert_one(user_to_be_added)


def update_user(_iid, set, database="test"):
    cols = get_collections_by_target(database)
    cols["users"].update_one({"user_id": _iid}, {"$set": set, "sync": False, "updated_at": datetime.utcnow()})


def get_user_by_id(id, database="test"):
    cols = get_collections_by_target(database)
    return cols["users"].find_one({"user_id": id})


def get_user_by_token(token, database="test"):
    cols = get_collections_by_target(database)
    return cols["users"].find_one({"access_token": token}, {"_id": False})


def get_user_by_tokens(access_token, refresh_token, database="test"):
    cols = get_collections_by_target(database)
    return cols["users"].find_one(
        {"access_token": access_token, "refresh_token": refresh_token}, {"_id": False}
    )


def create_user_account(firstname, lastname, email: str, password: str, database="test") -> Response:
    """
    Adds a user to the database.

    :param firstname: First name of the user.
    :param lastname: Last name of the user.
    :param email: Email of the user that will be created.
    :param password: Password of the user that will be created.
    :param phone: Phone number of the user.
    :param country: Country of the user.
    :param gender: Gender of the user.
    :param date_of_birth: Date of birth of the user.
    :return: Response
    """
    cols = get_collections_by_target(database)
    try:
        hashed = "bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())"
        _iid = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(36)
        )
        username = "@" + firstname.split()[0] + "" + lastname
        username = username.lower()
        # Check if the username already exists
        while cols["users"].find_one({"username": username}):
            username = (
                "@"
                + firstname.split()[0]
                + ""
                + lastname
                + str(secrets.randbelow(1000))
            )
            username = username.lower()

        cols["users"].insert_one(
            {
                "user_id": _iid,
                "first_name": firstname,
                "last_name": lastname,
                "email": email,
                "password": hashed,
                "phone": None,
                "country": "South Africa",
                "gender": "male",
                "date_of_birth": datetime.now(),
                "access_token": None,
                "refresh_token": None,
                "token_expiry": None,
                "is_email_verified": False,
                "is_phone_verified": False,
                "is_verified": False,
                "is_active": True,
                "is_online": False,
                "last_online": None,
                "is_deleted": False,
                "is_suspended": False,
                "suspended_by": None,
                "suspend_reason": None,
                "suspended_at": None,
                "suspended_until": None,
                "is_moderator": False,
                "is_premium": False,
                "is_business": False,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "profile": None,
                "username": username.lower(),
                "bio": None,
                "followers": [],
                "following": [],
            }
        )
    except DuplicateKeyError:
        return jsonify(
            {
                "status": False,
                "message": "user_id or email has already been taken! Try a different one.",
            }
        )

    return jsonify(
        {
            "status": True,
            "message": "Registration Success! Redirecting to the login page.",
        }
    )

# --- NEW DATABASE FUNCTIONS FOR ASHER-LINK & HOTSPOT LOGIC ---
def get_device_vouchers(mac, decoded_mac, encoded_mac, target="asherlink"):
    """
    Retrieves all vouchers associated with a specific MAC address 
    that still have a remaining balance greater than zero.
    
    Args:
        mac (str): The MAC address of the user's device.
        decoded_mac (str): The decoded MAC address.
        encoded_mac (str): The encoded MAC address.
        
    Returns:
        list: A list of voucher documents (dictionaries) from MongoDB.
    """
    try:
        cols = get_collections_by_target(target)
        # Updated query to account for vouchers that might not have 'remaining_value' set yet
        # but have a 'price' value.
        query = cols["vouchers"].find({
            "$or": [
                {"mac": {"$regex": f"^{re.escape(decoded_mac)}$", "$options": "i"}},
                {"mac": {"$regex": f"^{re.escape(encoded_mac)}$", "$options": "i"}},
                {"mac": {"$regex": f"^{re.escape(mac)}$", "$options": "i"}}
            ]
        })
        
        vouchers = list(query)
        return vouchers
    except Exception as e:
        logging.error(f"Error fetching device vouchers for {mac}: {e}")
        return []

def get_user_vouchers(user_id, target="asherlink"):
    """
    Retrieves all vouchers associated with a specific user_id
    that still have a remaining balance greater than zero.
    
    Args:
        user_id (str): The user ID.
        
    Returns:
        list: A list of voucher documents (dictionaries) from MongoDB.
    """
    try:
        cols = get_collections_by_target(target)
        query = cols["vouchers"].find({
            "user_id": user_id
        })
        vouchers = list(query)
        return vouchers
    except Exception as e:
        logging.error(f"Error fetching user vouchers for {user_id}: {e}")
        return []

def assign_mac_to_user_vouchers(user_id, mac, target="asherlink"):
    """
    Assigns a MAC address to all vouchers belonging to a user.
    Also updates any vouchers that have the same MAC but no user_id.
    
    Args:
        user_id (str): The user ID
        mac (str): The MAC address to assign
        
    Returns:
        bool: Success status
    """
    try:
        cols = get_collections_by_target(target)
        # Update user's vouchers with MAC
        cols["vouchers"].update_many(
            {"user_id": user_id},
            {"$set": {"mac": mac}}
        )
        
        # Update any vouchers with this MAC that don't have user_id
        cols["vouchers"].update_many(
            {"mac": mac, "user_id": {"$exists": False}},
            {"$set": {"user_id": user_id}}
        )
        
        # Update any vouchers with this MAC that have different user_id (reassignment)
        cols["vouchers"].update_many(
            {"mac": mac, "user_id": {"$ne": user_id}},
            {"$set": {"user_id": user_id}}
        )
        
        return True
    except Exception as e:
        logging.error(f"Error assigning MAC {mac} to user {user_id}: {e}")
        return False

def create_local_token(pin: str, amount: float, target="asherlink"):
    """
    Creates a local token in the database that can be redeemed later.
    The token will have no mac or user_id assigned initially.
    
    Args:
        pin (str): The token PIN (typically 6 digits)
        amount (float): The token value
        target (str): Target database
        
    Returns:
        ObjectId or None: The inserted document ID if successful, None otherwise
    """
    cols = get_collections_by_target(target)
    token_data = {
        "pin": pin,
        "amount": amount,
        "price": amount,  # Assuming price is same as amount for local tokens
        "remaining_value": amount,
        "user_id": None,
        "mac": None,
        "created_at": datetime.now(),
        "status": "available",
        "provider": "local"
    }
    try:
        result = cols["vouchers"].insert_one(token_data)
        return result.inserted_id
    except PyMongoError as e:
        logging.error(f"Failed to create local token: {e}")
        return None

def get_user_by_credentials(username, password):
    """
    Authenticates a user with username and password.
    
    Args:
        username (str): Username
        password (str): Password
        
    Returns:
        dict or None: User document if authenticated, None otherwise
    """
    try:
        # For now, using simple authentication - in production use proper hashing
        user = db.users.find_one({"username": username, "password": password})
        return user
    except Exception as e:
        logging.error(f"Error authenticating user {username}: {e}")
        return None

def update_voucher_balance(voucher_id, new_value):
    """
    Updates the remaining balance of a specific voucher document.
    
    Args:
        voucher_id (str/ObjectId): The unique ID of the voucher document.
        new_value (float): The new remaining balance (usually 0 or current - cost).
        
    Returns:
        bool: True if the update was successful, False otherwise.
    """
    try:
        cols = get_collections_by_target("asherlink")
        # Ensure the ID is a BSON ObjectId if it was passed as a string
        if isinstance(voucher_id, str):
            voucher_id = ObjectId(voucher_id)

        result = cols["vouchers"].update_one(
            {"_id": voucher_id},
            {
                "$set": {
                    "remaining_value": new_value,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating voucher balance for {voucher_id}: {e}")
        return False
        
def save_1voucher_redemption(pin: str, amount: float, user_id: str, mac: str = None, target="asherlink"):
    """
    Logs a successful 1Voucher redemption in the database.
    """
    cols = get_collections_by_target(target)
    redemption_data = {
        "pin": pin,
        "amount": amount,
        "remaining_value": amount,
        "user_id": user_id if user_id else None,
        "mac": mac,
        "redeemed_at": datetime.datetime.now(),
        "status": "active",
        "provider": "netcash"
    }
    try:
        return cols["vouchers"].insert_one(redemption_data)
    except PyMongoError as e:
        logging.error(f"Failed to log voucher: {e}")
        return None

def get_pppoe_user(username: str, target="asherlink"):
    """
    Retrieves a PPPoE/Hotspot user's local profile from MongoDB.
    """
    cols = get_collections_by_target(target)
    return cols["pppoe_users"].find_one({"username": username})

def update_data_usage(user_id: str, bytes_used: int, target="asherlink"):
    """
    Updates the accumulated data usage for a specific user.
    """
    cols = get_collections_by_target(target)
    cols["users"].update_one(
        {"user_id": user_id},
        {
            "$inc": {"total_data_usage": bytes_used},
            "$set": {"last_usage_update": datetime.now()}
        }
    )

# app/services/database_service.py

def get_all_bundles(target="asherlink"):
    """Fetches all available Wi-Fi bundles from the database."""
    try:
        cols = get_collections_by_target(target)
        bundles = list(cols["bundles"].find({}))
        for b in bundles:
            b['package_id'] = str(b['_id'])
        return bundles
    except Exception as e:
        logging.error(f"Error fetching bundles: {e}")
        return []

def create_bundle(bundle_data, target="asherlink"):
    """
    Creates a new Wi-Fi bundle.
    Example bundle_data: {"name": "1GB Daily", "price": 10.00, "data_limit": "1GB", "duration": "24h"}
    """
    try:
        cols = get_collections_by_target(target)
        result = cols["bundles"].insert_one(bundle_data)
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error creating bundle: {e}")
        return None

def delete_bundle(bundle_id, target="asherlink"):
    """Removes a bundle from the system."""
    try:
        cols = get_collections_by_target(target)
        cols["bundles"].delete_one({"_id": ObjectId(bundle_id)})
        return True
    except Exception as e:
        logging.error(f"Error deleting bundle: {e}")
        return False
        
def get_active_ads(target='asherlink'):
    """
    Fetches all ads from the advertisements collection where active is true.
    """
    try:
        # Query for active ads
        cols = get_collections_by_target(target)
        ads = list(cols["advertisements"].find({"active": True}))
        
        # Convert ObjectId to string for JSON serialization
        for ad in ads:
            ad['_id'] = str(ad['_id'])
            
        return ads
    except Exception as e:
        logging.error(f"Error fetching active ads: {e}")
        return []

def increment_ad_impression(ad_id, target='asherlink'):
    """
    Increments the view count for a specific ad.
    """
    try:
        cols = get_collections_by_target(target)
        cols["advertisements"].update_one(
            {"_id": ObjectId(ad_id)},
            {"$inc": {"impressions": 1}}
        )
    except Exception as e:
        logging.error(f"Error incrementing ad impression: {e}")

def update_ad_with_limit(ad_id, total_limit, daily_limit=None):
    """Sets impression caps on an advertisement"""
    cols = get_collections_by_target('asherlink')
    cols["advertisements"].update_one(
        {"_id": ObjectId(ad_id)},
        {"$set": {
            "total_limit": total_limit,
            "daily_limit": daily_limit,
            "daily_count": 0
        }}
    )

def get_filtered_active_ads():
    """Fetches active ads that haven't hit their limits yet"""
    cols = get_collections_by_target('asherlink')
    ads = list(cols["advertisements"].find({"active": True}))
    valid_ads = []
    
    for ad in ads:
        total_limit = ad.get("total_limit")
        impressions = ad.get("impressions", 0)
        
        # Check if total cap reached
        if total_limit and impressions >= total_limit:
            continue
            
        # Check if daily cap reached
        daily_limit = ad.get("daily_limit")
        daily_count = ad.get("daily_count", 0)
        if daily_limit and daily_count >= daily_limit:
            continue
            
        valid_ads.append(ad)
    return valid_ads

def get_ad_report_data():
    """Fetches all ads and their impression counts for reporting."""
    try:
        cols = get_collections_by_target('asherlink')
        return list(cols["advertisements"].find({}, {"ad_id": 1, "impressions": 1, "active": 1, "created_at": 1}))

    except Exception as e:
        logging.error(f"Error fetching report data: {e}")
        return []

def create_ad_record(ad_data):
    """
    Inserts a new advertisement document into the collection.
    """
    try:
        # Default starting stats
        ad_data["impressions"] = 0
        ad_data["created_at"] = datetime.datetime.utcnow()
        
        result = cols = get_collections_by_target('asherlink')
        cols["advertisements"].insert_one(ad_data)
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error creating ad record: {e}")
        return None

def toggle_ad_status(ad_id, active_status):
    cols = get_collections_by_target('asherlink')
    cols["advertisements"].update_one({"_id": ObjectId(ad_id)}, {"$set": {"active": active_status}})

def delete_ad_from_db(ad_id):
    cols = get_collections_by_target('asherlink')
    cols["advertisements"].delete_one({"_id": ObjectId(ad_id)})

def reset_daily_stats():
    cols = get_collections_by_target('asherlink')
    cols["advertisements"].update_many({}, {"$set": {"daily_count": 0}})

def update_ad_cpm(ad_id, cpm_rate):
    """Sets the Cost Per 1000 Views for an ad"""
    cols = get_collections_by_target('asherlink')
    cols["advertisements"].update_one(
        {"_id": ObjectId(ad_id)},
        {"$set": {"cpm_rate": float(cpm_rate)}}
    )
    
def create_hotspot_session(mac_address: str, bundle_name: str, target="asherlink"):
    """
    Records a new hotspot session when a user purchases a bundle.
    """
    cols = get_collections_by_target(target)
    session = {
        "mac": mac_address,
        "bundle": bundle_name,
        "purchase_time": datetime.datetime.now(),
        "active": True
    }
    result = cols["sessions"].insert_one(session)
    return result.inserted_id

def get_available_packages(target="asherlink"):
    """
    Fetches the wifi rates/packages defined in the database.
    (Alternative to reading the data.json file)
    """
    cols = get_collections_by_target(target)
    return list(cols["packages"].find({}))

def log_mikrotik_error(error_msg: str, context: str = None, target="asherlink"):
    """
    Logs API communication errors for troubleshooting.
    """
    cols = get_collections_by_target(target)
    cols["logs"].insert_one({
        "event": "api_error",
        "message": error_msg,
        "context": context,
        "timestamp": datetime.datetime.now()
    })

def verify_voucher_is_unique(pin: str, target="asherlink"):
    """
    Checks if a PIN has already been used in our system.
    """
    cols = get_collections_by_target(target)
    exists = cols["vouchers"].find_one({"pin": pin})
    return True if not exists else False


def db_change_email(user_id: str, new_email: str, target: str) -> Response:
    """
    Updates the user_id of the current user in the database.

    :param user_id:  current user's user_id
    :param new_email: The new email to set for the current user.
    :type new_email: str

    :returns: A Response object indicating the status of the email update.
    :rtype: Response
    """
    cols = get_collections_by_target(target)
    try:
        cols["users"].update_one(
            {"user_id": user_id}, {"$set": {"email": new_email}}
        )
    except PyMongoError:
        return jsonify(
            {
                "status": False,
                "message": "An error occurred, try again later!",
                "alertDiv": "#emailAlert",
            }
        )

    return jsonify(
        {
            "status": True,
        }
    )


def db_change_password(user_id: str, new_password: str, target: str) -> Response:
    """
    Updates the password of the current user in the database.

    :param user_id: current user's user_id
    :param new_password: user's new password

    :return: A Response object indicating the status of the password update.
    :rtype: Response
    """
    cols = get_collections_by_target(target)
    try:
        cols["users"].update_one(
            {"user_id": user_id},
            {"$set": {"password": generate_password_hash(new_password)}},
        )
    except PyMongoError:
        return jsonify(
            {
                "status": False,
                "alertDiv": "#passwordAlert",
                "message": "An error occurred, try again later!",
            }
        )

    return jsonify({"status": True})


def is_admin(chat_id: int, user_id: str, target: str) -> int:
    """
    Checks if the user is admin.

    :param chat_id: chat's id.
    :param user_id: current user's user_id.
    :return: Boolean state of 0 or 1 (True or False)
    """
    cols = get_collections_by_target(target)
    return cols["group_chat_members"].count_documents(
        {"chat_id": chat_id, "user_id": user_id, "is_chat_admin": True}
    )


# Get operations

def save_notification(user_id, message, notification_type="info"):
    """
    Save a notification to the database.

    :param user_id: The ID of the user to whom the notification belongs.
    :param message: The notification message.
    :param notification_type: The type of notification (e.g., info, warning, error).
    :return: The saved notification document.
    """
    notification = {
        "user_id": user_id,
        "content": message,
        "type": notification_type,
        "is_read": False,
        "created_at": datetime.now(),
    }
    get_collections_by_target.insert_one(notification)
    return notification


def send_notification(soc, user_id, message, notification_type="info"):
    """
    Send a notification to the user in real-time using WebSockets.

    :param soc: The SocketIO instance.
    :param user_id: The ID of the user to whom the notification will be sent.
    :param message: The notification message.
    :param notification_type: The type of notification (e.g., info, warning, error).
    """
    notification = save_notification(user_id, message, notification_type)
    soc.emit(
        "notification",
        {
            "user_id": user_id,
            "message": notification["message"],
            "type": notification["type"],
            "created_at": notification["created_at"].isoformat(),
        },
        room=user_id,
    )


def get_user_notifications(user_id):
    """
    Retrieve all notifications for a specific user.

    :param user_id: The ID of the user.
    :return: A list of notifications.
    """
    return list(
        get_collections_by_target.find({"user_id": user_id}).sort("created_at", -1)
    )


def mark_notification_as_read(notification_id):
    """
    Mark a specific notification as read.

    :param notification_id: The ID of the notification to mark as read.
    """
    get_collections_by_target.update_one(
        {"_id": notification_id}, {"$set": {"is_read": True}}
    )


def get_allowed_ips() -> list:
    """
    Fetches the list of allowed IPs for the proxy.

    :return: A list of allowed IPs.
    """
    return list(db.allowed_ips.find({}, {"_id": False, "ip": True}))


def add_allowed_ip(ip: str) -> Response:
    """
    Adds a new IP to the allowed IPs list for the proxy.

    :param ip: The IP address to be added.
    :return: A Response object indicating the status of the operation.
    """
    try:
        db.allowed_ips.insert_one({"ip": ip, "added_at": datetime.now()})
    except DuplicateKeyError:
        return jsonify(
            {"status": False, "message": "This IP is already in the allowed list!"}
        )
    except PyMongoError:
        return jsonify(
            {
                "status": False,
                "message": "An error occurred while adding the IP. Try again later!",
            }
        )

    return jsonify({"status": True, "message": "IP added successfully!"})


def remove_allowed_ip(ip: str) -> Response:
    """
    Removes an IP from the allowed IPs list for the proxy.

    :param ip: The IP address to be removed.
    :return: A Response object indicating the status of the operation.
    """
    try:
        result = db.allowed_ips.delete_one({"ip": ip})
        if result.deleted_count == 0:
            return jsonify(
                {"status": False, "message": "IP not found in the allowed list!"}
            )
    except PyMongoError:
        return jsonify(
            {
                "status": False,
                "message": "An error occurred while removing the IP. Try again later!",
            }
        )

    return jsonify({"status": True, "message": "IP removed successfully!"})

def get_user_analytics(user_id):
    """
    Aggregates statistics for a specific user including posts, 
    total likes across posts, views, and social connections.
    """
    try:
        # 1. Count total posts
        posts_count = db.posts.count_documents({"user_id": user_id})

        # 2. Sum likes and views across all user posts
        # We use an aggregation pipeline for efficiency
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_likes": {"$sum": {"$size": {"$ifNull": ["$likes", []]}}},
                "total_views": {"$sum": {"$size": {"$ifNull": ["$views", []]}}}
            }}
        ]
        
        stats = list(db.posts.aggregate(pipeline))
        total_likes = stats[0].get("total_likes", 0) if stats else 0
        total_views = stats[0].get("total_views", 0) if stats else 0

        # 3. Get follower/following counts from the user document
        user_doc = db.users.find_one({"user_id": user_id}, {"followers": 1, "following": 1})
        
        followers_count = len(user_doc.get("followers", [])) if user_doc else 0
        following_count = len(user_doc.get("following", [])) if user_doc else 0

        return {
            "total_posts": posts_count,
            "total_likes": total_likes,
            "total_views": total_views,
            "followers_count": followers_count,
            "following_count": following_count
        }
    except Exception as e:
        print(f"Error fetching user analytics: {e}")
        return {}

def get_recent_activity(user_id, limit=10):
    """
    Retrieves the most recent actions related to the user 
    (e.g., new followers, mentions, or interactions).
    """
    try:
        # Fetch from an 'activity' or 'notifications' collection
        activities = db.activity.find(
            {"recipient_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)

        data = []
        for act in activities:
            data.append({
                "activity_id": str(act.get("_id", "")),
                "type": act.get("type"), # e.g., 'like', 'follow', 'comment'
                "actor_id": act.get("actor_id"),
                "actor_username": act.get("actor_username"),
                "actor_profile": act.get("actor_profile"),
                "target_id": act.get("target_id"), # ID of post/story
                "content": act.get("content", ""), # e.g., snippet of a comment
                "created_at": act.get("created_at")
            })
            
        return data
    except Exception as e:
        print(f"Error fetching recent activity: {e}")
        return []

def save_chat(chat_name: str, created_by: str) -> int:
    """
    Allows a user to create a chat; giving them admin access,
    and automatically adding them to the chat.

    :param chat_name: The name of the chat to be created.
    :param created_by: The user_id of the user who is creating the chat.
    :type chat_name: str,
    :type created_by: str

    :return: Created chat's ID.
    """
    chat_id = "chat_id"
    get_collections_by_target.insert_one(
        {
            "chat_id": chat_id,
            "name": chat_name,
            "created_by": created_by,
            "created_at": datetime.now(),
        }
    )

    add_chat_member(
        chat_id,
        chat_name=chat_name,
        user_id=created_by,
        added_by=created_by,
        is_chat_admin=True,
    )
    return chat_id


def add_chat_member(
    chat_id: int, chat_name: str, user_id: str, added_by, is_chat_admin=False
):
    """
    Add a member to a chat with `chat_id`.

    :param chat_id: The id of the chat to which the member will be added.
    :param chat_name: The name of the chat.
    :param user_id: The user_id of the member to be added.
    :param added_by: The user_id of the user who is adding the member.
    :param is_chat_admin: Whether the member should have admin privileges in the chat.
    :return:
    """
    get_collections_by_target.insert_one(
        {
            "chat_id": chat_id,
            "user_id": user_id,
            "chat_name": chat_name,
            "added_by": added_by,
            "added_at": datetime.now(),
            "is_chat_admin": is_chat_admin,
        }
    )


def join_chat_member(
    chat_id: int, chat_name: str, user_id: str, added_by="Himself", is_chat_admin=False
) -> Response:
    """
    Responsible for joining a chat by chat_id, handling this operation on the join chat modal.

    :param chat_id: The id of the chat to join.
    :param chat_name: The name of the chat.
    :param user_id: The user_id of the user joining the chat.
    :param added_by: The user_id of the user who is added the member.
    :param is_chat_admin: Whether the member should have admin privileges in the chat.
    :return: Response
    """
    get_collections_by_target.insert_one(
        {
            "chat_id": chat_id,
            "user_id": user_id,
            "chat_name": chat_name,
            "added_by": added_by,
            "added_at": datetime.now(),
            "is_chat_admin": is_chat_admin,
        }
    )
    chat_members = get_collections_by_target.find({"chat_id": chat_id})
    chat_members = [member["user_id"] for member in chat_members]
    if current_user.user_id in chat_members:
        return jsonify(
            {
                "status": True,
                "message": "Joined chat Successfully",
            }
        )

    return jsonify({"status": False, "message": "An error occurred, try again later!"})


def db_change_chat_name(chat_id: int, new_chat_name: str) -> Response:
    """
    Change chat's name in the database.
    :param chat_id: chat's id.
    :param new_chat_name: new chat name to be set.
    :return: Response
    """
    try:
        # chats collection
        get_collections_by_target.find_one_and_update(
            {"chat_id": chat_id}, {"$set": {"name": new_chat_name}}
        )

        # chat members collection
        get_collections_by_target.update_many(
            {"chat_id": chat_id}, {"$set": {"chat_name": new_chat_name}}
        )
    except PyMongoError:
        return jsonify({"status": False, "message": "Failed to change chat name!"})

    return jsonify(
        {
            "status": True,
            "message": "Changed chat name successfully!",
        }
    )


# Messages


def get_messages(user1_id: str, user2_id: str) -> list:
    """
    Returns a list of messages exchanged between two users, including the other user's details.

    :param user1_id: The id of the logged-in user.
    :param user2_id: The id of the other user.
    :return: A list of messages with sender details and the other user's details.
    """
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"sender": user1_id, "recipient": user2_id},
                    {"sender": user2_id, "recipient": user1_id},
                ]
            }
        },
        {"$sort": {"created_at": 1}},  # Sort by time ascending
        {
            "$lookup": {
                "from": "users",
                "localField": "sender",
                "foreignField": "user_id",
                "as": "sender_details",
            }
        },
        {"$unwind": {"path": "$sender_details", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"other_user_id": user2_id if user1_id else user1_id}},
        {
            "$lookup": {
                "from": "users",
                "localField": "other_user_id",
                "foreignField": "user_id",
                "as": "other_user_details",
            }
        },
        {
            "$unwind": {
                "path": "$other_user_details",
                "preserveNullAndEmptyArrays": True,
            }
        },
        {
            "$project": {
                "_id": 0,
                "sender": 1,
                "recipient": 1,
                "message": 1,
                "created_at": 1,
                "image_url": 1,
                "sender_details": 1,
                "other_user_details": 1,
            }
        },
    ]

    return list(get_collections_by_target.aggregate(pipeline))


def get_user_chats(user_id: str) -> list:
    """
    Fetch the most recent message sent or received for each chat and return only the details of the other user.

    :param user_id: The ID of the logged-in user.
    :return: A list of chats with the latest message and details of the other user.
    """
    pipeline = [
        {"$match": {"$or": [{"sender": user_id}, {"recipient": user_id}]}},
        {"$sort": {"created_at": -1}},
        {
            "$addFields": {
                "other_user_id": {
                    "$cond": [{"$eq": ["$sender", user_id]}, "$recipient", "$sender"]
                }
            }
        },
        {"$group": {"_id": "$other_user_id", "latest_message": {"$first": "$$ROOT"}}},
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "other_user_details",
            }
        },
        {
            "$unwind": {
                "path": "$other_user_details",
                "preserveNullAndEmptyArrays": True,
            }
        },
        {
            "$project": {
                "_id": 0,
                "other_user_id": "$_id",
                "other_user_details": 1,
                "message": "$latest_message.message",
                "time": "$latest_message.created_at",
            }
        },
        {"$sort": {"time": -1}},
    ]

    return list(get_collections_by_target.aggregate(pipeline))


def save_message(sender: str, recipient: str, text: str) -> None:
    """
    Save a message to the database.

    :param sender: The user_id of the message sender.
    :param recipient: The user_id of the message recipient.
    :param text: The content of the message.
    :return: None
    """
    get_collections_by_target.insert_one(
        {
            "sender": sender,
            "recipient": recipient,
            "text": text,
            "created_at": datetime.now(),
        }
    )
