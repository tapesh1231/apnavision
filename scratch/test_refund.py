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
            # Let's try passing empty dict first
            print("Trying full refund without amount...")
            refund = client.payment.refund(order.razorpay_payment_id)
            print("Success!", refund)
        except Exception as e:
            print("Empty refund failed:", e)
            try:
                print("Trying with dictionary...")
                refund = client.payment.refund(order.razorpay_payment_id, {"amount": int(order.total_price * 100)})
                print("Success!", refund)
            except Exception as e2:
                print("Dict refund failed:", e2)
    else:
        print("No order with payment found")
