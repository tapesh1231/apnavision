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

def auto_decorate_filter(text):
    if not text:
        return ""
    import re
    from markupsafe import Markup

    # Escape HTML to prevent XSS
    text = str(Markup.escape(text))

    # Bold labels like "Feature:" or "Speed:" at the start of lines
    text = re.sub(r'^([A-Za-z0-9\t ]+):', r'<strong class="text-gray-900">\1:</strong>', text, flags=re.MULTILINE)

    lines = text.split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<br>')
            continue
            
        if line.startswith('- ') or line.startswith('* '):
            if not in_list:
                html_lines.append('<ul class="list-disc pl-5 my-3 space-y-2 marker:text-volt-500">')
                in_list = True
            html_lines.append(f'<li>{line[2:]}</li>')
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<p class="mb-3 leading-relaxed">{line}</p>')
            
    if in_list:
        html_lines.append('</ul>')

    return Markup('\n'.join(html_lines))
