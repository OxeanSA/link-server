from datetime import datetime, timezone
import re

from flask import request, jsonify, make_response
from flask_restx import Resource, Namespace, fields
from bson.json_util import dumps
import urllib

# Importing the exact database functions as requested
from app.services.database_service import (
    get_all_bundles,
    get_collections_by_target,
    save_1voucher_redemption,
    get_pppoe_user,
    update_data_usage,
    create_hotspot_session,
    verify_voucher_is_unique, 
    increment_ad_impression,
    get_filtered_active_ads,
    get_device_vouchers,
    update_voucher_balance,
    get_user_vouchers,
    assign_mac_to_user_vouchers,
    get_user_by_credentials,
    create_local_token
)
from app.utils.logger import debug_logger
from app.exts import authenticate, require_admin

import requests

# --- CONFIGURATION ---
NETCASH_API = "https://api.netcash.co.za/1voucher/redeem"

# Namespaces
device_ns = Namespace("device", description="Voucher and Balance management")
hotspot_ns = Namespace("hotspot", description="Session and Package management")
system_ns = Namespace("system", description="User, Logs, and Ad Server")

# Models
redeem_model = device_ns.model("Redeem", {
    "pin": fields.String(required=True, description="16-digit 1Voucher PIN"),
    "mac": fields.String(required=False, description="Device MAC Address"),
    "user_id": fields.String(required=False, description="User ID (if authenticated)"),
    "amount": fields.String(required=False, description="Token Amount (if specified)")
})

token_model = device_ns.model("Redeem", {
    "pin": fields.String(required=True, description="Internal Voucher PIN"),
    "amount": fields.Float(required=True, description="Token Amount (if specified)")
})

login_model = device_ns.model("Login", {
    "username": fields.String(required=True, description="Username"),
    "password": fields.String(required=True, description="Password"),
    "mac": fields.String(required=True, description="Device MAC Address")
})

purchase_model = device_ns.model("Purchase", {
    "mac": fields.String(required=False, description="Device MAC Address"),
    "user_id": fields.String(required=False, description="User ID (if authenticated)"),
    "price": fields.Float(required=True),
    "bundle_name": fields.String(required=True)
})

usage_model = hotspot_ns.model("Usage", {
    "username": fields.String(required=True),
    "bytes": fields.Integer(required=True)
})
# --- DEVICE NAMESPACE (Vouchers & Balance) ---

@device_ns.route("/login")
class LoginResource(Resource):
    @device_ns.expect(login_model)
    def post(self):
        """Authenticate user with username and password"""
        try:
            req = request.get_json()
            username = req.get("username")
            password = req.get("password")
            mac = req.get("mac")

            user = get_user_by_credentials(username, password)
            if user:
                # Assign MAC to user's vouchers
                assign_mac_to_user_vouchers(str(user['user_id']), mac)
                
                return jsonify({
                    "status": "success", 
                    "user_id": str(user['user_id']),
                    "username": user.get('username'),
                    "message": "Login successful"
                })
            else:
                return make_response(jsonify({"status": "error", "message": "Invalid credentials"}), 401)

        except Exception as e:
            debug_logger.error(f"Error in login: {e}")
            return make_response(jsonify({"error": "Internal server error"}), 500)

@device_ns.route("/redeem")
class RedeemResource(Resource):
    @device_ns.expect(redeem_model)
    def post(self):
        """Redeem a 1Voucher PIN or local token and log to DB"""
        try:
            req = request.get_json()
            pin = req.get("pin")
            mac = req.get("mac", None)  # Optional, but recommended for local tokens
            user_id = req.get("user_id", None)  # Optional for authenticated users

            if not pin:
                return make_response(jsonify({"status": "error", "message": "PIN required"}), 400)

            # Handle 16-digit Netcash vouchers
            if len(pin) == 16:
                # 1. Verify PIN is unique in our system first
                if not verify_voucher_is_unique(pin):
                    return make_response(jsonify({"status": "error", "message": "Voucher already used locally"}), 400)

                # 2. Validate PIN with Netcash
                nc_resp = requests.post(NETCASH_API, json={"pin": pin}, timeout=10)
                nc_data = nc_resp.json()

                if nc_data.get('status') == "success":
                    amount = float(nc_data.get('amount'))
                    
                    # 3. Save successful redemption
                    save_1voucher_redemption(pin, amount, user_id, mac)
                    
                    return make_response(jsonify({"status": "success", "amount": amount}), 200)
                
                return make_response(jsonify({"status": "error", "message": "Voucher invalid or already used at Netcash"}), 400)
            
            # Handle local tokens (less than 16 digits)
            else:
                # 1. Check if token exists in database and is available
                cols = get_collections_by_target("asherlink")
                
                # Note: Using a single $and with your specific $or conditions
                token_doc = cols['vouchers'].find_one({
                    "pin": pin,
                    "$and": [
                        {
                            "$or": [
                                {"mac": {"$exists": False}},
                                {"mac": None},
                                {"mac": ""}
                            ]
                        },
                        {
                            "$or": [
                                {"user_id": {"$exists": False}},
                                {"user_id": None},
                                {"user_id": ""}
                            ]
                        }
                    ]
                })
                
                if not token_doc:
                    debug_logger.info(f"Token {pin} not found or already assigned")
                    return make_response(jsonify({"status": "invalid", "message": "Token not found or already assigned"}), 400)
                
                # Get the value to add to balance
                amount = float(token_doc.get('remaining_value', token_doc.get('amount', 0)))
                if amount <= 0:
                    debug_logger.info(f"Token {pin} has no remaining value")
                    return make_response(jsonify({"status": "invalid", "message": "Token has no remaining value"}), 400)
                
                # 2. Assign MAC and user_id to the token in 'vouchers'
                current_time = datetime.now(timezone.utc)
                
                cols['vouchers'].update_one(
                    {"_id": token_doc["_id"]}, # Use _id for precision
                    {"$set": {
                        "mac": mac, 
                        "user_id": user_id, 
                        "status": "assigned",
                        "redeemed_at": current_time # Recommended for tracking
                    }}
                )
                debug_logger.info(f"Local token redeemed: pin={pin}, amount={amount}, user_id={user_id}, mac={mac}")
                return make_response(jsonify({
                    "status": "success", 
                    "amount": amount,
                    "message": f"Successfully redeemed {amount}"
                }), 200)

        except Exception as e:
            debug_logger.error("REDEEM_API_FAIL", f"pin: {pin}, error: {str(e)}")
            debug_logger.error(f"Error in redeem: {e}")
            return make_response(jsonify({"error": "Internal server error", "status": "error"}), 500)

@device_ns.route("/refresh")
class RefreshResource(Resource):
    def post(self):
        """Refresh user session and reassign MAC if needed"""
        try:
            req = request.get_json()
            user_id = req.get("user_id")
            current_mac = req.get("mac")

            if not user_id or not current_mac:
                return make_response(jsonify({"status": "error", "message": "user_id and mac required"}), 400)

            # Check if user's vouchers have a different MAC
            user_vouchers = get_user_vouchers(user_id)
            if user_vouchers:
                # Get the MAC from user's vouchers
                voucher_mac = user_vouchers[0].get('mac')
                if voucher_mac and voucher_mac != current_mac:
                    # Reassign MAC to current device
                    assign_mac_to_user_vouchers(user_id, current_mac)
                    return jsonify({
                        "status": "success", 
                        "message": "MAC reassigned",
                        "mac_reassigned": True
                    })
                else:
                    # MAC is already correct
                    assign_mac_to_user_vouchers(user_id, current_mac)  # Ensure assignment
                    return jsonify({
                        "status": "success", 
                        "message": "Session refreshed",
                        "mac_reassigned": False
                    })
            else:
                return make_response(jsonify({"status": "error", "message": "No vouchers found for user"}), 404)

        except Exception as e:
            debug_logger.error(f"Error in refresh: {e}")
            return make_response(jsonify({"error": "Internal server error"}), 500)

@device_ns.route("/balance/<string:identifier>")
class BalanceResource(Resource):
    def get(self, identifier):
        """Calculate total available balance for a specific MAC or user_id"""
        try:
            if not identifier or not isinstance(identifier, str):
                return make_response(jsonify({"status": "error", "message": "Invalid identifier"}), 400)

            # Check if identifier is a MAC address
            is_mac = ":" in identifier or len(identifier) == 17 or (len(identifier) == 12 and all(c in "0123456789ABCDEFabcdef" for c in identifier))

            if is_mac:
                decoded_mac = urllib.parse.unquote(identifier)
                encoded_mac = urllib.parse.quote(decoded_mac).upper()
                vouchers = get_device_vouchers(mac=identifier, decoded_mac=decoded_mac, encoded_mac=encoded_mac)
            else:
                vouchers = get_user_vouchers(identifier)
                # Fallback to MAC if no user-bound vouchers found
                if not vouchers:
                    vouchers = get_device_vouchers(mac=identifier, decoded_mac=decoded_mac, encoded_mac=encoded_mac)

            total_balance = 0
            for v in vouchers:
                # Based on your screenshot, the field is 'remaining_value'
                # Note: Some docs have 'amount' and some have 'remaining_value'
                val = v.get('remaining_value')
                if val is None:
                    val = v.get('amount', 0)
                
                try:
                    total_balance += float(val)
                except (ValueError, TypeError):
                    continue

            debug_logger.info(f"Balance check for identifier: {identifier}, found {len(vouchers)} vouchers, total_balance: {total_balance}")
            
            return jsonify({
                "status": "success", 
                "balance": round(total_balance, 2),
                "count": len(vouchers),
                "matched_mac": identifier
            })
            
        except Exception as e:
            debug_logger.error(f"Error fetching balance: {e}")
            return make_response(jsonify({"status": "error", "balance": 0, "message": "Failed to fetch balance"}), 500)

# --- HOTSPOT NAMESPACE (Packages & Sessions) ---

@hotspot_ns.route("/packages")
class PackageResource(Resource):
    def get(self):
        """Get all available wifi packages"""
        try:
            data = []
            packages = get_all_bundles()
            for b in packages:
                data.append({
                    "name": b.get("name"),
                    "isVoucherAccepted": b.get("isVoucherAccepted", True),
                    "quotaAmount": b.get("quota", "Uncapped"),
                    "activePeriod": b.get("activePeriod"),
                    "price": float(b.get("price")),
                    "bandwidth": b.get("bandwidth")
                })
            return jsonify({"status": "success", "packages": data})
        
        except Exception as e:
            debug_logger.error("GET_PACKAGES_FAIL", str(e))
            return make_response(jsonify({"status": "error", "message": "Could not fetch packages"}), 500)
            
@hotspot_ns.route("/bundles")
class BundleListResource(Resource):
    def get(self):
        """List all available Wi-Fi bundles for users to see"""
        try:
            bundles = get_all_bundles()
            return jsonify({"status": "success", "bundles": bundles})
        except Exception as e:
            debug_logger.error("GET_BUNDLES_FAIL", str(e))
            return make_response(jsonify({"status": "error", "message": "Could not fetch bundles"}), 500)
        
@hotspot_ns.route("/purchase")
class PurchaseResource(Resource):
    @device_ns.expect(purchase_model)
    def post(self):
        """Deduct balance and create session"""
        try:
            req = request.get_json()
            mac = req.get("mac", None)
            user_id = req.get("user_id", None)
            cost = float(req.get("price"))
            bundle = req.get("bundle_name")

            # Get vouchers based on user_id or MAC
            if user_id:
                vouchers = get_user_vouchers(user_id)
                identifier = user_id
            else:
                vouchers = get_device_vouchers(mac)
                identifier = mac

            vouchers = sorted(vouchers, key=lambda x: x['remaining_value'])

            total_available = sum(v['remaining_value'] for v in vouchers)
            if total_available < cost:
                return make_response(jsonify({"status": "error", "message": "Insufficient balance"}), 400)

            # Iterative Deduction
            remaining_to_deduct = cost
            for v in vouchers:
                if remaining_to_deduct <= 0: break
                curr_bal = v['remaining_value']
                
                if curr_bal <= remaining_to_deduct:
                    deduction = curr_bal
                    new_val = 0.0
                else:
                    deduction = remaining_to_deduct
                    new_val = curr_bal - deduction
                
                update_voucher_balance(v['user_id'], round(new_val, 2))
                remaining_to_deduct -= deduction

            # Create the hotspot session record
            session_id = create_hotspot_session(identifier, bundle)

            return jsonify({
                "status": "success", 
                "message": f"Purchased {bundle}",
                "session_id": str(session_id)
            })

        except Exception as e:
            debug_logger.error("PURCHASE_FAIL", str(e))
            return make_response(jsonify({"error": "Internal server error"}), 500)

@hotspot_ns.route("/bundles/affordable/<string:identifier>")
class AffordableBundleResource(Resource):
    def get(self, identifier):
        """Returns only bundles the user can afford with their current balance"""
        try:
            # Get vouchers based on user_id or MAC
            vouchers = get_user_vouchers(identifier)
            if not vouchers:
                vouchers = get_device_vouchers(identifier)

            user_balance = sum(v.get('remaining_value', 0) for v in vouchers)

            # 2. Fetch all bundles
            cols = get_collections_by_target("asherlink")
            all_bundles = list(cols.bundles.find({}))
            
            # 3. Filter by price
            affordable = []
            for b in all_bundles:
                if float(b['price']) <= float(user_balance):
                    b['user_id'] = str(b['user_id'])
                    affordable.append({
                        "name": b.get("name"),
                        "isVoucherAccepted": b.get("isVoucherAccepted", True),
                        "quota": b.get("quota", "Uncapped"),
                        "activePeriod": b.get("activePeriod"),
                        "price": b.get("price"),
                        "bandwidth": b.get("bandwidth")
                    })
            
            return jsonify({
                "status": "success",
                "user_balance": user_balance,
                "bundles": affordable
            })
        except Exception as e:
            debug_logger.error("AFFORDABLE_BUNDLES_FAIL", str(e))
            return make_response(jsonify({"status": "error", "message": "Could not fetch affordable bundles"}), 500)
        
@hotspot_ns.route("/session/start")
class StartSession(Resource):
    def post(self):
        """Create a new hotspot session record"""
        data = request.json
        mac = data.get("mac")
        package_id = data.get("package_id")
        
        session_id = create_hotspot_session(mac, package_id)
        return jsonify({"status": "success", "session_id": str(session_id)})

@hotspot_ns.route("/usage/update")
class UpdateUsage(Resource):
    @hotspot_ns.expect(usage_model)
    def post(self):
        """Update data usage for a specific user"""
        data = request.json
        username = data.get("username")
        bytes_used = data.get("bytes_used")
        
        try:
            update_data_usage(username, bytes_used)
            return jsonify({"status": "success"})
        except Exception as e:
            debug_logger.error("Usage Update", str(e))
            return make_response(jsonify({"status": "error", "message": "Update failed"}), 500)
          
@hotspot_ns.route("/usage")
class UsageResource(Resource):
    @hotspot_ns.expect(usage_model)
    def post(self):
        """Update user data usage"""
        data = request.get_json()
        update_data_usage(data['username'], data['bytes'])
        return jsonify({"status": "success"})

# --- SYSTEM NAMESPACE (Users & Logs) ---
@system_ns.route("/ads/active")
class ActiveAdsResource(Resource):
    def get(self):
        """Returns active ads that are within their view limits"""
        try:
            ads = get_filtered_active_ads()
            for ad in ads:
                ad['_id'] = str(ad['_id'])
            return jsonify({"status": "success", "ads": ads})
        except Exception as e:
            return make_response(jsonify({"status": "error", "message": "Failed to fetch active ads"}), 500)

@system_ns.route("/ads/log-view/<string:ad_id>")
class LogAdViewResource(Resource):
    def post(self, ad_id):
        """
        Endpoint to log that an ad was successfully displayed.
        """
        increment_ad_impression(ad_id)
        return {"status": "success"}, 200
        
@system_ns.route("/user/<string:username>")
class UserResource(Resource):
    def get(self, username):
        """Fetch PPPoE/Hotspot user details"""
        try:
            user = get_pppoe_user(username)
            if user:
                return jsonify({"status": "success", "user": user})
            return make_response(jsonify({"status": "error", "message": "User not found"}), 404)
        except Exception as e:
            return make_response(jsonify({"status": "error", "message": "Failed to fetch user"}), 500)

@system_ns.route("/tokens/create")
class CreateTokenResource(Resource):
    @system_ns.expect(token_model)
    def post(self):
        """Create a local token for redemption"""
        try:
            req = request.get_json()
            pin = req.get("pin")
            amount = float(req.get("amount"))
            
            if not pin or not amount:
                return make_response(jsonify({"status": "error", "message": "PIN and amount required"}), 400)
            
            # Validate PIN format (should be short, like 6 digits)
            if len(pin) < 3 or len(pin) > 15:
                return make_response(jsonify({"status": "error", "message": "PIN must be 3-15 characters"}), 400)
            
            token_id = create_local_token(pin, float(amount))
            if token_id:
                return jsonify({"status": "success", "token_id": str(token_id), "message": "Token created successfully"})
            else:
                return make_response(jsonify({"status": "error", "message": "Failed to create token"}), 500)
                
        except Exception as e:
            debug_logger.error(f"Error creating token: {e}")
            return make_response(jsonify({"error": "Internal server error"}), 500)

