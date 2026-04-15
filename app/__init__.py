from flask import Flask
from flask_restx import Api
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from app.utils.logger import app_logger, proxy_logger, debug_logger
from app.utils.proxy import Proxy
from app.extensions import handle_requests, get_ip
from app.routes.link import device_ns, hotspot_ns, system_ns
from app.routes.admin import admin_ns

def create_app():
    app = Flask(__name__)
    
    app.config.from_object('config.ProductionConfig')
    
    api = Api(app, title='Lona API', version='1.0 beta', doc='/')
    
    ipv4 = get_ip()

    allowed_ips = [
        ipv4,
        '10.119.46.47',
        '192.168.1.187'
    ]

    # Log initialization messages
    app_logger.info('App logger initialized')
    proxy_logger.info('Proxy logger initialized')
    debug_logger.info('Debug logger initialized, ip: ' + ipv4)

    JWTManager(app)
    CORS(app)
    Proxy(app, allowed_ips)

    # Namespaces
    api.add_namespace(device_ns, path='/asherlink/device')
    api.add_namespace(hotspot_ns, path='/asherlink/hotspot')
    api.add_namespace(system_ns, path='/asherlink/system')
    api.add_namespace(admin_ns, path='/asherlink/admin')

    handle_requests(app)

    return app


