from flask import request, jsonify, make_response, send_file
from flask_restx import Resource, Namespace, fields
from werkzeug.utils import secure_filename
from bson.json_util import dumps
from fpdf import FPDF
import datetime
import io
import os

# Importing database functions
from app.services.analytics_service import get_performance_distribution
from app.services.analytics_service import get_revenue_summary
from app.services.database_service import (
    get_all_bundles,
    get_collections_by_target,
    create_bundle,
    delete_bundle,
    get_ad_report_data,
    toggle_ad_status,
    delete_ad_from_db,
    create_ad_record
)
from app.utils.logger import debug_logger
from app.extensions import require_admin

# Configuration
UPLOAD_FOLDER = '/workspaces/lonaapi/static/ads'

# Helper function for file validation
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# Admin namespace
admin_ns = Namespace("admin", description="Administrative operations")

# Models
bundle_model = admin_ns.model("Bundle", {
    "name": fields.String(required=True, description="Bundle name"),
    "quotaAmount": fields.String(required=True, description="Bundle quotaAmount"),
    "price": fields.Float(required=True, description="Bundle price"),
    "bandwidth": fields.String(required=False, description="Data bandwidth"),
    "activePeriod": fields.String(required=True, description="activePeriod")
})

@admin_ns.route("/bundles")
class BundleResource(Resource):
    @require_admin
    def get(self):
        """Get all bundles for admin management"""
        try:
            bundles = get_all_bundles()
            for b in bundles:
                b['_id'] = str(b['_id'])
            return jsonify({"status": "success", "bundles": bundles})
        except Exception as e:
            return make_response(jsonify({"status": "error", "message": "Failed to fetch bundles"}), 500)

    #@require_admin
    @admin_ns.expect(bundle_model)
    def post(self):
        """Create a new bundle"""
        try:
            data = request.get_json()
            bundle_data = {
                "name": data.get("name"),
                "price": float(data.get("price")),
                "data_limit": data.get("data_limit", "100Mb"),
                "bandwidth": data.get("bandwidth", "2Mbps"),
                "isVoucherAccepted": data.get("isVoucherAccepted", True),
                "quotaAmount": data.get("quotaAmount", "1 day"),
                "activePeriod": data.get("activePeriod", "1h")
            }
            result = create_bundle(bundle_data)
            return jsonify({"status": "success", "bundle_id": str(result.inserted_id)})
        except Exception as e:
            return make_response(jsonify({"status": "error", "message": "Failed to create bundle"}), 500)

@admin_ns.route("/bundles/<string:bundle_id>")
class BundleDetailResource(Resource):
    @require_admin
    def delete(self, bundle_id):
        """Delete a bundle"""
        try:
            delete_bundle(bundle_id)
            return jsonify({"status": "success", "message": "Bundle deleted"})
        except Exception as e:
            return make_response(jsonify({"status": "error", "message": "Failed to delete bundle"}), 500)

@admin_ns.route("/ads/manage/<string:ad_id>")
class AdManageResource(Resource):
    @require_admin
    def patch(self, ad_id):
        data = request.get_json()
        toggle_ad_status(ad_id, data.get('active'))
        return {"status": "updated"}, 200

    @require_admin
    def delete(self, ad_id):
        delete_ad_from_db(ad_id)
        return {"status": "deleted"}, 200

@admin_ns.route("/ads/create")
class AdCreateResource(Resource):
    @require_admin
    def post(self):
        """Upload image and create Ad record in one go"""
        # 1. Check for file
        if 'file' not in request.files:
            return {"status": "error", "message": "No file part"}, 400

        file = request.files['file']
        ad_id = request.form.get('ad_id') # Name of the campaign
        target_url = request.form.get('target_url', '#')

        if not ad_id or file.filename == '':
            return {"status": "error", "message": "Ad ID and File are required"}, 400

        if file and allowed_file(file.filename):
            # 2. Save File
            filename = secure_filename(f"{ad_id}_{file.filename}")
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            # 3. Create DB Record
            image_url = f"https://api.oxeansa.co.za/static/ads/{filename}"
            ad_data = {
                "ad_id": ad_id,
                "image_url": image_url,
                "target_url": target_url,
                "active": True
            }

            db_id = create_ad_record(ad_data)

            if db_id:
                return {
                    "status": "success",
                    "ad_id": ad_id,
                    "db_id": db_id,
                    "url": image_url
                }, 201

        return {"status": "error", "message": "Upload failed"}, 400

@admin_ns.route("/ads/report")
class AdReportResource(Resource):
    @require_admin
    def get(self):
        """Generates a PDF report of ad performance"""
        ads = get_ad_report_data()

        # Create PDF logic
        pdf = FPDF()
        pdf.add_page()

        # Header
        pdf.set_font("Arial", "B", 20)
        pdf.cell(0, 10, "Asher-Link Hotspot Ad Report", ln=True, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 10, f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
        pdf.ln(10)

        # Table Header
        pdf.set_fill_color(200, 220, 255)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(80, 10, "Campaign Name", 1, 0, "C", True)
        pdf.cell(40, 10, "Status", 1, 0, "C", True)
        pdf.cell(60, 10, "Total Impressions", 1, 0, "C", True)
        pdf.cell(60, 10, "Impressions", 1, 0, "C", True)
        pdf.cell(40, 10, "Value (ZAR)", 1, 1, "C", True)

        # Table Body
        pdf.set_font("Arial", "", 12)
        total_views = 0
        total_revenue = 0
        for ad in ads:
            status = "Active" if ad.get("active") else "Inactive"
            views = ad.get("impressions", 0)
            cpm = ad.get("cpm_rate", 50.00) # Fallback to 50
            earnings = (views / 1000) * cpm
            total_revenue += earnings
            total_views += views

            pdf.cell(80, 10, str(ad.get("ad_id")), 1)
            pdf.cell(40, 10, status, 1, 0, "C")
            pdf.cell(60, 10, f"{views:,}", 1, 0, "R")
            pdf.cell(40, 10, f"R {earnings:,.2f}", 1, 1, "R")

        # Summary
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(120, 10, "Total Network Impressions:", 0)
        pdf.cell(60, 10, f"{total_views:,}", 0, 1, "R")
        pdf.cell(120, 10, "Total Estimated Billing:", 0)
        pdf.cell(60, 10, f"R {total_revenue:,.2f}", 0, 1, "R")

        # Output to buffer
        response_data = io.BytesIO()
        pdf_output = pdf.output(dest='S').encode('latin-1')
        response_data.write(pdf_output)
        response_data.seek(0)

        return send_file(
            response_data,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Ad_Report_{datetime.date.today()}.pdf"
        )

@admin_ns.route("/login")
class AdminLoginResource(Resource):
    def post(self):
        """Admin authentication"""
        data = request.get_json()
        password = data.get('password')
        
        # Simple password check - in production, use proper authentication
        if password == "admin123":  # Change this to a secure password
            from flask_jwt_extended import create_access_token
            token = create_access_token(identity="admin")
            return jsonify({"token": token, "status": "success"})
        return {"status": "error", "message": "Invalid credentials"}, 401

@admin_ns.route("/analytics/summary")
class AdminAnalyticsSummary(Resource):
    @require_admin
    def get(self):
        """Fetch high-level financial summary for the dashboard cards"""
        
        return jsonify(get_revenue_summary())

@admin_ns.route("/analytics/distribution")
class AdminAnalyticsDistribution(Resource):
    @require_admin
    def get(self):
        """Fetch distribution data for Chart.js Doughnut charts"""
        
        return jsonify(get_performance_distribution())
    
@admin_ns.route("/health")
class SystemHealthResource(Resource):
    @require_admin
    def get(self):
        """System health check"""
        try:
            cols = get_collections_by_target("asherlink")
            # Check database connectivity
            db_status = "healthy"
            try:
                cols.advertisements.count_documents({})
            except:
                db_status = "unhealthy"
            
            import time
            uptime = time.time() - getattr(self, '_start_time', time.time())
            
            return {
                "status": "healthy",
                "uptime": f"{int(uptime)}s",
                "database": db_status
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}, 500

@admin_ns.route("/backup")
class DatabaseBackupResource(Resource):
    @require_admin
    def post(self):
        """Create database backup"""
        try:
            import datetime
            cols = get_collections_by_target("asherlink")
            
            # Simple backup - in production, implement proper backup logic
            backup_data = {
                "timestamp": datetime.datetime.now(),
                "collections": {}
            }
            
            # Backup each collection
            for collection_name in ["advertisements", "bundles", "vouchers", "sessions"]:
                try:
                    collection = getattr(cols, collection_name)
                    backup_data["collections"][collection_name] = list(collection.find({}))
                except:
                    backup_data["collections"][collection_name] = []
            
            # Save backup info (in production, save to file or cloud storage)
            backup_collection = cols.backups
            backup_collection.insert_one(backup_data)
            
            return {"success": True, "message": "Backup completed successfully"}
        except Exception as e:
            return {"success": False, "message": f"Backup failed: {str(e)}"}, 500

