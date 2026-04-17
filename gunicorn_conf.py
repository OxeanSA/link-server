# gunicorn_conf.py
bind = "0.0.0.0:8000"
workers = 3
worker_class = "tornado"
loglevel = "info"
accesslog = "-"
errorlog = "-"
