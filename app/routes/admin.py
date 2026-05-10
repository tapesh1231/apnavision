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
            
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            filepath = os.path.join(upload_folder, filename)
            
            # Compress and save image locally
            img = Image.open(photo)
            # Convert RGBA to RGB for JPEG compatibility if needed
            if img.mode != 'RGB' and file_ext.lower() in ['.jpg', '.jpeg']:
                img = img.convert('RGB')
            img.save(filepath, optimize=True, quality=85)
            
            image_url = url_for('static', filename=f'uploads/{filename}')


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
            
            # --- REMOVE THIS BLOCK FOR RENDER.COM DEPLOYMENT ---
            # This saves files to local disk, which Render will delete on restart.
            # if photo and photo.filename:
            #     filename = secure_filename(photo.filename)
            #     upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            #     os.makedirs(upload_folder, exist_ok=True)
            #     filepath = os.path.join(upload_folder, filename)
            #     photo.save(filepath)
            #     scooter.image_url = url_for('static', filename=f'uploads/{filename}')
            # ---------------------------------------------------
            
            # --- ADD THIS NEW CODE FOR GOOGLE DRIVE INTEGRATION ON RENDER.COM ---
            # This securely uploads the image directly to Google Drive using OAuth.
            if photo and photo.filename:
                from googleapiclient.http import MediaIoBaseUpload

                drive_service = build_google_drive_service()
                if not drive_service:
                    raise Exception("Google Drive is not configured. Please add Google Drive credentials or connect via Google Drive.")

                file_ext = os.path.splitext(photo.filename)[1]
                scooter_name = request.form.get('name', scooter.name)
                custom_filename = secure_filename(f"{scooter_name}{file_ext}")
                file_metadata = {'name': custom_filename}

                folder_id = current_app.config.get('GOOGLE_DRIVE_FOLDER_ID')
                if folder_id:
                    file_metadata['parents'] = [folder_id]

                media = MediaIoBaseUpload(photo.stream, mimetype=photo.mimetype, resumable=True)
                uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
                file_id = uploaded_file.get('id')

                drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}, supportsAllDrives=True).execute()
                scooter.image_url = f"https://drive.google.com/uc?id={file_id}"
            # --------------------------------------------------------------------
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
