from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Order

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Landing page."""
    from app.models import Scooter
    featured_scooters = Scooter.query.order_by(Scooter.id.desc()).limit(3).all()
    return render_template('main/index.html', featured_scooters=featured_scooters)

@main_bp.route('/about')
def about():
    """About us page."""
    return render_template('main/about.html')

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page."""
    from flask import request, flash, redirect, url_for
    if request.method == 'POST':
        flash('Thank you for contacting us! Our support team will reach out within 24 hours.', 'success')
        return redirect(url_for('main.contact'))
    return render_template('main/contact.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing order history."""
    orders = current_user.orders.order_by(Order.created_at.desc()).all()
    return render_template('main/dashboard.html', orders=orders)

@main_bp.route('/complaint/add', methods=['POST'])
@login_required
def add_complaint():
    from app.models import Complaint
    from app import db
    from flask import request, flash, redirect, url_for, current_app
    import os
    from werkzeug.utils import secure_filename
    
    order_id = request.form.get('order_id')
    subject = request.form.get('subject')
    description = request.form.get('description')
    photo = request.files.get('photo')
    
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('main.dashboard'))
        
    image_url = None
    # --- REMOVE THIS BLOCK FOR RENDER.COM DEPLOYMENT ---
    # This saves files to local disk, which Render will delete on restart.
    # if photo and photo.filename:
    #     filename = secure_filename(photo.filename)
    #     upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
    #     os.makedirs(upload_folder, exist_ok=True)
    #     filepath = os.path.join(upload_folder, filename)
    #     photo.save(filepath)
    #     image_url = url_for('static', filename=f'uploads/{filename}')
    # ---------------------------------------------------
        
    # --- ADD THIS NEW CODE FOR GOOGLE DRIVE INTEGRATION ON RENDER.COM ---
    # This securely uploads the image directly to Google Drive.
    if photo and photo.filename:
        import json, os
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        
        creds_json = os.environ.get('GOOGLE_DRIVE_CREDENTIALS')
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/drive.file'])
            drive_service = build('drive', 'v3', credentials=creds)
            
            file_metadata = {'name': secure_filename(photo.filename)}
            media = MediaIoBaseUpload(photo.stream, mimetype=photo.mimetype, resumable=True)
            uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            file_id = uploaded_file.get('id')
            
            drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
            image_url = f"https://drive.google.com/uc?id={file_id}"
    # --------------------------------------------------------------------
        
    complaint = Complaint(
        user_id=current_user.id,
        order_id=order.id,
        subject=subject,
        description=description,
        image_url=image_url
    )
    db.session.add(complaint)
    db.session.commit()
    
    from app.utils import send_email
    email_body = f"""Dear {current_user.username},

We have received your complaint regarding Order #{order.id}.
Your Complaint Ticket ID is: #{complaint.id}

Subject: {subject}

Our support team will review this issue and get back to you shortly. You can track the status of this ticket on your dashboard.

Best regards,
The ApnaVision Support Team"""
    send_email(f"Complaint Received - Ticket #{complaint.id}", current_user.email, email_body)
    
    flash('Complaint successfully registered. Our team will review it shortly.', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/secret-setup-db')
def secret_setup_db():
    try:
        from app import db
        from app.models import Scooter, User
        db.drop_all()
        db.create_all()
        
        # Create admin user
        admin = User(username="Tapeshwar", email="tapeshwarkr08112002@gmail.com", is_admin=True)
        admin.set_password("Tapesh@0811")
        db.session.add(admin)
        
        db.session.commit()
        return "Database created successfully! Go to the homepage now."
    except Exception as e:
        return f"Error creating database: {str(e)}"
