from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    """User model for customers and admins."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    must_change_password = db.Column(db.Boolean, default=False)
    profile_photo_url = db.Column(db.String(256))
    phone_number = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    reviews = db.relationship('Review', backref='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Scooter(db.Model):
    """Product model for electric scooters."""
    __tablename__ = 'scooters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(64), default='Standard')
    top_speed = db.Column(db.Integer, nullable=False) # In mph or km/h
    range = db.Column(db.Integer, nullable=False)     # In miles or km
    battery_life = db.Column(db.String(64))
    image_url = db.Column(db.String(256))
    stock_quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reviews = db.relationship('Review', backref='scooter_reviews', lazy='dynamic')
    orders = db.relationship('Order', backref='scooter', lazy='dynamic')
    
    @property
    def active_offer(self):
        from app.models import Offer
        from datetime import datetime
        now = datetime.now()
        return Offer.query.filter_by(is_active=True).filter(
            db.or_(Offer.target_scooter_id == self.id, Offer.target_category == self.category)
        ).filter(
            db.or_(Offer.valid_from == None, Offer.valid_from <= now)
        ).filter(
            db.or_(Offer.valid_until == None, Offer.valid_until >= now)
        ).order_by(Offer.discount_percent.desc()).first()
        
    @property
    def final_price(self):
        offer = self.active_offer
        if offer:
            return self.price * (1 - (offer.discount_percent / 100))
        return self.price
        
    @property
    def total_sold(self):
        from app.models import Order
        return self.orders.filter(Order.status != 'Pending', Order.status != 'Refunded').count()
        
    @property
    def total_added(self):
        return self.stock_quantity + self.total_sold

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return sum(r.rating for r in reviews) / len(reviews)
        
    @property
    def review_count(self):
        return self.reviews.count()

class Offer(db.Model):
    """Discount offers for products."""
    __tablename__ = 'offers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    discount_percent = db.Column(db.Float, nullable=False)
    
    target_category = db.Column(db.String(64), nullable=True) 
    target_scooter_id = db.Column(db.Integer, db.ForeignKey('scooters.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    target_scooter = db.relationship('Scooter', foreign_keys=[target_scooter_id])
    
    @property
    def is_currently_valid(self):
        from datetime import datetime
        if not self.is_active:
            return False
        now = datetime.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
        
    @property
    def is_expired(self):
        from datetime import datetime
        if self.valid_until and datetime.now() > self.valid_until:
            return True
        return False
        
    @property
    def is_upcoming(self):
        from datetime import datetime
        if self.valid_from and datetime.now() < self.valid_from:
            return True
        return False

class Order(db.Model):
    """Order model linking users to scooter purchases."""
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    scooter_id = db.Column(db.Integer, db.ForeignKey('scooters.id'), nullable=False)
    status = db.Column(db.String(64), default='Paid') # Paid, Processing, Shipped, Delivered, Rejected & Refunded
    razorpay_order_id = db.Column(db.String(128))
    razorpay_payment_id = db.Column(db.String(128))
    refund_status = db.Column(db.String(32), default='None') # None, Initiated, Processed, Failed
    refund_id = db.Column(db.String(128))
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    history = db.relationship('OrderStatusHistory', backref='order', lazy=True, order_by='OrderStatusHistory.created_at.desc()')

class OrderStatusHistory(db.Model):
    """Tracks order status changes over time."""
    __tablename__ = 'order_status_history'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    status = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Complaint(db.Model):
    """User complaints regarding specific orders."""
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    subject = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(512)) # Optional photo
    status = db.Column(db.String(32), default='Open') # Open, Resolved
    admin_comment = db.Column(db.Text) # Resolution notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    order = db.relationship('Order', backref='complaints')
    user = db.relationship('User', backref='complaints')

class Review(db.Model):
    """Review model for customers to rate scooters."""
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False) # 1 to 5
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    scooter_id = db.Column(db.Integer, db.ForeignKey('scooters.id'), nullable=False)

class Department(db.Model):
    """Departments for team management."""
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    members = db.relationship('TeamMember', backref='department', lazy='dynamic')

class TeamMember(db.Model):
    """Team members linking a user to a department."""
    __tablename__ = 'team_members'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    role = db.Column(db.String(64), default='Member') # e.g. Manager, Member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('team_profile', uselist=False))
    tasks = db.relationship('Task', backref='assignee', lazy='dynamic')

class Task(db.Model):
    """Tasks assigned to team members."""
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(32), default='Pending') # Pending, In Progress, Completed
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('team_members.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    
    creator = db.relationship('User', foreign_keys=[created_by_id])
