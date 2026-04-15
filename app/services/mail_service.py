from flask import current_app
#from flask_mail import Message
from threading import Thread
from werkzeug.exceptions import InternalServerError
from app.exts import mail

def send_async_email(app, msg):
	with app.app_context():
		try:
			mail.send(msg)
		except ConnectionRefusedError:
			raise InternalServerError('[MAIL SERVER] is not working')

def send_email(subject, recipients, text_body, html_body):
	app = current_app._get_current_object()
#	msg = Message(subject, sender="dnx@ceera.com", recipients=recipients)
#	msg.body = text_body
#	msg.html = html_body
	Thread(target=send_async_email, args=(app, "msg")).start()

# ** Remove "" on msg
# ** Uncomment all