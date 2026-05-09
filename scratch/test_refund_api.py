from app import create_app
import razorpay

app = create_app()

with app.app_context():
    client = razorpay.Client(auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET']))
    from app.models import Order
    order = Order.query.order_by(Order.id.desc()).first()
    if order and order.razorpay_payment_id:
        try:
            print("Trying client.refund.create...")
            refund = client.refund.create({"payment_id": order.razorpay_payment_id})
            print("Success!", refund)
        except Exception as e:
            print("Error:", e)
    else:
        print("No order with payment found")
