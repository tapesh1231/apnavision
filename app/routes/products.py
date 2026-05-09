from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from app.models import Scooter, Order
from app import db
from flask_login import login_required, current_user
import razorpay

# Define the Blueprint
products_bp = Blueprint('products', __name__)

@products_bp.route('/')
def catalog():
    """
    Product catalog page. Displays all available scooters.
    Includes basic filtering logic.
    """
    page = request.args.get('page', 1, type=int)
    min_range = request.args.get('min_range', 0, type=int)
    max_price = request.args.get('max_price', 1000000, type=int)

    # Query with filters
    query = Scooter.query.filter(
        Scooter.range >= min_range,
        Scooter.price <= max_price
    )
    
    # Pagination
    scooters = query.paginate(page=page, per_page=9, error_out=False)

    return render_template('products/catalog.html', scooters=scooters)

@products_bp.route('/<int:scooter_id>')
def detail(scooter_id):
    """
    Product detail page showing specifications and reviews.
    """
    scooter = Scooter.query.get_or_404(scooter_id)
    return render_template('products/detail.html', scooter=scooter)

@products_bp.route('/checkout/<int:scooter_id>', methods=['GET', 'POST'])
@login_required
def checkout(scooter_id):
    """
    Checkout page with Razorpay JS integration logic.
    """
    scooter = Scooter.query.get_or_404(scooter_id)
    client = razorpay.Client(auth=(current_app.config['RAZORPAY_KEY_ID'], current_app.config['RAZORPAY_KEY_SECRET']))
    
    if request.method == 'POST':
        razorpay_payment_id = request.form.get('razorpay_payment_id')
        razorpay_order_id = request.form.get('razorpay_order_id')
        razorpay_signature = request.form.get('razorpay_signature')
        
        if not razorpay_payment_id or not razorpay_signature:
            flash('Payment failed or was interrupted.', 'error')
            return redirect(url_for('products.checkout', scooter_id=scooter_id))
            
        try:
            # Verify the payment with Razorpay
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            
            # Create Order
            from app.models import OrderStatusHistory
            order = Order(
                user_id=current_user.id,
                scooter_id=scooter.id,
                status='Paid',
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                total_price=scooter.final_price
            )
            
            # Record initial status
            history = OrderStatusHistory(order=order, status='Paid')
            db.session.add(history)
            
            # Deduct inventory
            if scooter.stock_quantity > 0:
                scooter.stock_quantity -= 1
                
            db.session.add(order)
            db.session.commit()
            
            from app.utils import send_email
            email_body = f"""Dear {current_user.username},

Thank you for your purchase from ApnaVision!
Your Order ID is: #{order.id}
You have paid ₹{"%.2f" % order.total_price}.

You can track your order status directly from your dashboard.

Best regards,
The ApnaVision Team"""
            send_email(f"ApnaVision Order Confirmation - #{order.id}", current_user.email, email_body)
            
            flash(f'Successfully purchased the {scooter.name}! Your order is now processing.', 'success')
            return redirect(url_for('main.dashboard'))
        except razorpay.errors.SignatureVerificationError:
            flash('Payment signature verification failed.', 'error')
        except Exception as e:
            flash(f'Error processing payment: {str(e)}', 'error')
            
        return redirect(url_for('products.checkout', scooter_id=scooter_id))

    # GET request - Create a Razorpay Order
    try:
        razorpay_order = client.order.create({
            "amount": int(scooter.final_price * 100), # Amount in paise
            "currency": "INR",
            "receipt": f"receipt_{scooter.id}_{current_user.id}"
        })
        order_id = razorpay_order['id']
    except Exception as e:
        order_id = None
        flash(f'Warning: Razorpay is not fully configured. Error: {str(e)}', 'error')

    return render_template('products/checkout.html', 
                           scooter=scooter, 
                           razorpay_key_id=current_app.config['RAZORPAY_KEY_ID'],
                           order_id=order_id)

@products_bp.route('/<int:scooter_id>/review', methods=['POST'])
@login_required
def add_review(scooter_id):
    from app.models import Review
    scooter = Scooter.query.get_or_404(scooter_id)
    rating = request.form.get('rating', type=int)
    body = request.form.get('body')
    
    if not rating or rating < 1 or rating > 5:
        flash('Please provide a valid rating between 1 and 5.', 'error')
        return redirect(url_for('products.detail', scooter_id=scooter_id))
        
    review = Review(
        rating=rating,
        body=body,
        user_id=current_user.id,
        scooter_id=scooter.id
    )
    db.session.add(review)
    db.session.commit()
    
    flash('Your review has been successfully published!', 'success')
    return redirect(url_for('products.detail', scooter_id=scooter_id))
