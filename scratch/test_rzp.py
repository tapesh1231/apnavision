from app import create_app
from config import Config
import razorpay

app = create_app()

with app.app_context():
    client = razorpay.Client(auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET']))
    from app.models import Order
    order = Order.query.order_by(Order.id.desc()).first()
    if order and order.razorpay_payment_id:
        try:
            payment = client.payment.fetch(order.razorpay_payment_id)
            print("Payment status:", payment['status'])
            print("Captured:", payment['captured'])
        except Exception as e:
            print("Error:", e)
    else:
        print("No order with payment found")
