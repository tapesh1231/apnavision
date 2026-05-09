from flask_mail import Message
from flask import current_app
from app import mail
from threading import Thread

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Error sending email: {str(e)}")

def send_email(subject, recipient, body_text):
    """
    Helper function to send emails asynchronously.
    """
    msg = Message(subject, recipients=[recipient])
    msg.body = body_text
    
    app = current_app._get_current_object()
    Thread(target=send_async_email, args=(app, msg)).start()
