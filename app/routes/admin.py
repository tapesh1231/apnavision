import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort, session
from app.models import User, Scooter, Order
from app import db
from flask_login import login_required, current_user
from functools import wraps
admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def get_google_client_config():
    return {
        "web": {
            "client_id": current_app.config.get('GOOGLE_CLIENT_ID', ''),
            "client_secret": current_app.config.get('GOOGLE_CLIENT_SECRET', ''),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [current_app.config.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/admin/oauth2callback')]
        }
    }

def is_google_drive_connected():
    return bool(current_app.config.get('GOOGLE_DRIVE_CREDENTIALS') or session.get('google_token'))

def build_google_drive_service():
    from googleapiclient.discovery import build
    from google.oauth2 import service_account
    import json
    from google.oauth2.credentials import Credentials

    if 'google_token' in session:
        creds = Credentials(
            token=session['google_token']['token'],
            refresh_token=session['google_token']['refresh_token'],
            client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
            token_uri="https://oauth2.googleapis.com/token"
        )
        return build('drive', 'v3', credentials=creds)

    creds_json = current_app.config.get('GOOGLE_DRIVE_CREDENTIALS')
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            return build('drive', 'v3', credentials=creds)
        except Exception:
            pass
    return None

@admin_bp.route('/google-login')
@admin_required
def google_login():
    from google_auth_oauthlib.flow import Flow
    import os
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    flow = Flow.from_client_config(
        get_google_client_config(),
        scopes=['https://www.googleapis.com/auth/drive.file'],
        redirect_uri=current_app.config.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/admin/oauth2callback')
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)

@admin_bp.route('/oauth2callback')
def oauth2callback():
    from google_auth_oauthlib.flow import Flow
    import os
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    flow = Flow.from_client_config(
        get_google_client_config(),
        scopes=['https://www.googleapis.com/auth/drive.file'],
        state=session.get('state'),
        redirect_uri=current_app.config.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/admin/oauth2callback')
    )
    
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['google_token'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token
    }
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/')
@admin_required
def dashboard():
    from app.models import Offer, Complaint
    orders = Order.query.order_by(Order.created_at.desc()).all()
    scooters = Scooter.query.all()
    users = User.query.all()
    offers = Offer.query.all()
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    
    total_revenue = sum(o.total_price for o in orders if o.status != 'Refunded')
    
    return render_template('admin/dashboard.html', 
                           orders=orders, 
                           scooters=scooters,
                           users=users,
                           offers=offers,
                           complaints=complaints,
                           total_revenue=total_revenue,
                           total_users=len(users))

@admin_bp.route('/order/<int:order_id>/status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    from app.models import OrderStatusHistory
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if order.status == 'Delivered':
        flash('Cannot change status of a delivered order.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    if order.status == 'Rejected & Refunded':
        flash('Cannot process a rejected order.', 'error')
        return redirect(url_for('admin.dashboard'))

    if new_status in ['Paid', 'Processing', 'Shipped', 'Delivered', 'Rejected & Refunded']:
        if order.status != new_status:
            order.status = new_status
            history = OrderStatusHistory(order_id=order.id, status=new_status)
            db.session.add(history)
            
            # Process Razorpay Refund if rejected
            if new_status == 'Rejected & Refunded' and order.razorpay_payment_id:
                try:
                    import razorpay
                    client = razorpay.Client(auth=(current_app.config['RAZORPAY_KEY_ID'], current_app.config['RAZORPAY_KEY_SECRET']))
                    refund = client.refund.create({
                        "payment_id": order.razorpay_payment_id,
                        "amount": int(order.total_price * 100)
                    })
                    order.refund_status = 'Processed'
                    order.refund_id = refund.get('id')
                    flash('Refund successfully initiated through Razorpay.', 'success')
                except Exception as e:
                    order.refund_status = 'Failed'
                    flash(f'Status updated to Rejected, but automatic Razorpay refund failed: {str(e)}', 'error')
            
            db.session.commit()
            
            from app.utils import send_email
            email_body = f"""Dear {order.customer.username},

The status of your ApnaVision Order #{order.id} has been updated to: {new_status}.

You can track your full order history on your dashboard.

Best regards,
The ApnaVision Team"""
            send_email(f"ApnaVision Order Update - #{order.id}", order.customer.email, email_body)
            
            flash(f'Order #{order.id} status updated to {new_status}.', 'success')
    else:
        flash('Invalid status provided.', 'error')
        
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/order/<int:order_id>/refund', methods=['POST'])
@admin_required
def manual_refund(order_id):
    order = Order.query.get_or_404(order_id)
    if not order.razorpay_payment_id:
        flash('Order does not have a Razorpay payment ID.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    if order.refund_status == 'Processed':
        flash('Refund has already been processed.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    try:
        import razorpay
        client = razorpay.Client(auth=(current_app.config['RAZORPAY_KEY_ID'], current_app.config['RAZORPAY_KEY_SECRET']))
        refund = client.refund.create({
            "payment_id": order.razorpay_payment_id,
            "amount": int(order.total_price * 100)
        })
        order.refund_status = 'Processed'
        order.refund_id = refund.get('id')
        db.session.commit()
        flash('Manual refund successfully initiated through Razorpay.', 'success')
    except Exception as e:
        order.refund_status = 'Failed'
        db.session.commit()
        flash(f'Manual Razorpay refund failed: {str(e)}', 'error')
        
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/scooter/<int:scooter_id>/stock', methods=['POST'])
@admin_required
def update_scooter_stock(scooter_id):
    scooter = Scooter.query.get_or_404(scooter_id)
    try:
        new_stock = int(request.form.get('stock'))
        if new_stock >= 0:
            scooter.stock_quantity = new_stock
            db.session.commit()
            flash(f'{scooter.name} stock updated to {new_stock}.', 'success')
        else:
            flash('Stock cannot be negative.', 'error')
    except (ValueError, TypeError):
        flash('Invalid stock value.', 'error')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/scooter/add', methods=['POST'])
@admin_required
def add_scooter():
    try:
        import os
        from werkzeug.utils import secure_filename
        
        image_url = request.form.get('image_url') or None
        photo = request.files.get('image_file')
        
        if photo and photo.filename:
            from PIL import Image
            import os
            from werkzeug.utils import secure_filename
            
            file_ext = os.path.splitext(photo.filename)[1]
            scooter_name = request.form.get('name', 'scooter')
            filename = secure_filename(f"{scooter_name}{file_ext}")
            
            # Compress and optimize image locally in-memory
            img = Image.open(photo)
            if img.mode != 'RGB' and file_ext.lower() in ['.jpg', '.jpeg']:
                img = img.convert('RGB')
            # Resize image to max 1200x1200 to dramatically speed up compression
            img.thumbnail((1200, 1200))
            
            import io
            from googleapiclient.http import MediaIoBaseUpload
            
            buffer = io.BytesIO()
            save_format = img.format if img.format else ('JPEG' if file_ext.lower() in ['.jpg', '.jpeg'] else 'PNG')
            img.save(buffer, format=save_format, optimize=True, quality=85)
            buffer.seek(0)
            
            # Setup Google Drive
            drive_service = build_google_drive_service()
            if not drive_service:
                raise Exception("Google Drive is not configured. Please add Google Drive credentials or connect via Google Drive.")
            
            scooter_name = request.form.get('name', 'scooter')
            custom_filename = secure_filename(f"{scooter_name}{file_ext}")
            file_metadata = {'name': custom_filename}
            
            folder_id = current_app.config.get('GOOGLE_DRIVE_FOLDER_ID')
            if folder_id:
                file_metadata['parents'] = [folder_id]
                
            media = MediaIoBaseUpload(buffer, mimetype=photo.mimetype, resumable=True)
            uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
            file_id = uploaded_file.get('id')
            
            drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}, supportsAllDrives=True).execute()
            image_url = f"https://drive.google.com/uc?id={file_id}"


        new_scooter = Scooter(
            name=request.form.get('name'),
            category=request.form.get('category', 'Standard'),
            description=request.form.get('description'),
            price=float(request.form.get('price')),
            top_speed=int(request.form.get('top_speed')),
            range=int(request.form.get('range')),
            battery_life=request.form.get('battery_life'),
            image_url=image_url,
            stock_quantity=int(request.form.get('stock_quantity', 0))
        )
        db.session.add(new_scooter)
        db.session.commit()
        flash('Product successfully added!', 'success')
    except Exception as e:
        flash(f'Failed to add product: {str(e)}', 'error')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/scooter/<int:scooter_id>/delete', methods=['POST'])
@admin_required
def delete_scooter(scooter_id):
    scooter = Scooter.query.get_or_404(scooter_id)
    try:
        from app.models import Review, Offer, Order, OrderStatusHistory, Complaint
        
        # 1. Delete associated Offers
        Offer.query.filter_by(target_scooter_id=scooter.id).delete()
        
        # 2. Delete associated Reviews
        Review.query.filter_by(scooter_id=scooter.id).delete()
        
        # 3. Delete associated Orders and their child records
        for order in scooter.orders:
            OrderStatusHistory.query.filter_by(order_id=order.id).delete()
            Complaint.query.filter_by(order_id=order.id).delete()
            db.session.delete(order)
            
        # 4. Finally delete the scooter
        db.session.delete(scooter)
        db.session.commit()
        flash(f'Product "{scooter.name}" and all its associated data have been permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete this product due to a database error: {str(e)}', 'error')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/scooter/<int:scooter_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_scooter(scooter_id):
    scooter = Scooter.query.get_or_404(scooter_id)
    
    if request.method == 'POST':
        try:
            import os
            from werkzeug.utils import secure_filename
            from flask import current_app
            
            scooter.name = request.form.get('name')
            scooter.category = request.form.get('category')
            scooter.description = request.form.get('description')
            scooter.price = float(request.form.get('price'))
            scooter.top_speed = int(request.form.get('top_speed'))
            scooter.range = int(request.form.get('range'))
            scooter.battery_life = request.form.get('battery_life')
            scooter.stock_quantity = int(request.form.get('stock_quantity', scooter.stock_quantity))
            
            image_url = request.form.get('image_url')
            photo = request.files.get('image_file')
            
            if photo and photo.filename:
                from PIL import Image
                import os
                from werkzeug.utils import secure_filename
                
                file_ext = os.path.splitext(photo.filename)[1]
                scooter_name = request.form.get('name', scooter.name)
                filename = secure_filename(f"{scooter_name}{file_ext}")
                
                # Compress and optimize image locally in-memory
                img = Image.open(photo)
                if img.mode != 'RGB' and file_ext.lower() in ['.jpg', '.jpeg']:
                    img = img.convert('RGB')
                # Resize image to max 1200x1200 to dramatically speed up compression
                img.thumbnail((1200, 1200))
                
                import io
                from googleapiclient.http import MediaIoBaseUpload
                
                buffer = io.BytesIO()
                save_format = img.format if img.format else ('JPEG' if file_ext.lower() in ['.jpg', '.jpeg'] else 'PNG')
                img.save(buffer, format=save_format, optimize=True, quality=85)
                buffer.seek(0)
                
                # Setup Google Drive
                drive_service = build_google_drive_service()
                if not drive_service:
                    raise Exception("Google Drive is not configured. Please add Google Drive credentials or connect via Google Drive.")
                
                scooter_name = request.form.get('name', scooter.name)
                custom_filename = secure_filename(f"{scooter_name}{file_ext}")
                file_metadata = {'name': custom_filename}
                
                folder_id = current_app.config.get('GOOGLE_DRIVE_FOLDER_ID')
                if folder_id:
                    file_metadata['parents'] = [folder_id]
                    
                media = MediaIoBaseUpload(buffer, mimetype=photo.mimetype, resumable=True)
                uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
                file_id = uploaded_file.get('id')
                
                drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}, supportsAllDrives=True).execute()
                scooter.image_url = f"https://drive.google.com/uc?id={file_id}"
            elif image_url:
                scooter.image_url = image_url
                
            db.session.commit()
            flash('Product successfully updated!', 'success')
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            flash(f'Failed to update product: {str(e)}', 'error')
            
    return render_template('admin/edit_scooter.html', scooter=scooter)

@admin_bp.route('/offer/add', methods=['POST'])
@admin_required
def add_offer():
    from app.models import Offer
    try:
        name = request.form.get('name')
        discount_percent = float(request.form.get('discount_percent'))
        
        target_type = request.form.get('target_type')
        target_category = None
        target_scooter_id = None
        
        if target_type == 'category':
            target_category = request.form.get('target_category')
        elif target_type == 'individual':
            target_scooter_id = int(request.form.get('target_scooter_id'))
            
        valid_from_str = request.form.get('valid_from')
        valid_until_str = request.form.get('valid_until')
        from datetime import datetime
        valid_from = datetime.strptime(valid_from_str, '%Y-%m-%dT%H:%M') if valid_from_str else None
        valid_until = datetime.strptime(valid_until_str, '%Y-%m-%dT%H:%M') if valid_until_str else None
            
        new_offer = Offer(
            name=name,
            discount_percent=discount_percent,
            target_category=target_category,
            target_scooter_id=target_scooter_id,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True
        )
        db.session.add(new_offer)
        db.session.commit()
        flash(f'Offer "{name}" successfully created!', 'success')
    except Exception as e:
        flash(f'Failed to create offer: {str(e)}', 'error')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/complaint/<int:complaint_id>/resolve', methods=['POST'])
@admin_required
def resolve_complaint(complaint_id):
    from app.models import Complaint
    from app.utils import send_email
    complaint = Complaint.query.get_or_404(complaint_id)
    admin_comment = request.form.get('admin_comment', '')
    
    complaint.status = 'Resolved'
    complaint.admin_comment = admin_comment
    db.session.commit()
    
    email_body = f"""Dear {complaint.user.username},

Your complaint (Ticket #{complaint.id}) regarding Order #{complaint.order_id} has been marked as Resolved.

Resolution Note from Admin:
{admin_comment}

If you have any further issues, please reach out to our support team.

Best regards,
The ApnaVision Support Team"""
    send_email(f"Complaint Resolved - Ticket #{complaint.id}", complaint.user.email, email_body)
    
    flash('Complaint marked as resolved and comment saved!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/offer/<int:offer_id>/edit', methods=['POST'])
@admin_required
def edit_offer(offer_id):
    from app.models import Offer
    from datetime import datetime
    now = datetime.now()
    offer = Offer.query.get_or_404(offer_id)
    
    if offer.is_expired:
        flash(f'Cannot edit offer "{offer.name}" because it has already expired.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    try:
        offer.name = request.form.get('name')
        offer.discount_percent = float(request.form.get('discount_percent'))
        
        target_type = request.form.get('target_type')
        if target_type == 'category':
            offer.target_category = request.form.get('target_category')
            offer.target_scooter_id = None
        elif target_type == 'individual':
            offer.target_category = None
            offer.target_scooter_id = int(request.form.get('target_scooter_id'))
            
        valid_from_str = request.form.get('valid_from')
        valid_until_str = request.form.get('valid_until')
        
        has_started = (offer.valid_from is None) or (offer.valid_from <= now)
        if not has_started:
            offer.valid_from = datetime.strptime(valid_from_str, '%Y-%m-%dT%H:%M') if valid_from_str else None
            
        offer.valid_until = datetime.strptime(valid_until_str, '%Y-%m-%dT%H:%M') if valid_until_str else None
        
        db.session.commit()
        flash(f'Offer "{offer.name}" successfully updated!', 'success')
    except Exception as e:
        flash(f'Failed to update offer: {str(e)}', 'error')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/offer/<int:offer_id>/toggle', methods=['POST'])
@admin_required
def toggle_offer(offer_id):
    from app.models import Offer
    offer = Offer.query.get_or_404(offer_id)
    
    if offer.is_expired:
        flash(f'Cannot toggle status of "{offer.name}" because it has already expired.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    offer.is_active = not offer.is_active
    db.session.commit()
    status = "activated" if offer.is_active else "deactivated"
    flash(f'Offer "{offer.name}" {status}.', 'success')
    return redirect(url_for('admin.dashboard'))
