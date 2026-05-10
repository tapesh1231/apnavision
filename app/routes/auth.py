from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.models import User
from app.forms import RegistrationForm, LoginForm
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            # Protect against open redirects
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('main.index')
            flash('Successfully logged in!', 'success')
            return redirect(next_page)
        else:
            flash('Login Unsuccessful. Please check your email and password.', 'error')
            
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout endpoint."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Force password change for new team members."""
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or new_password != confirm_password:
            flash('Passwords do not match or are empty.', 'error')
        elif len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
        else:
            current_user.set_password(new_password)
            current_user.must_change_password = False
            db.session.commit()
            flash('Password successfully updated. Welcome!', 'success')
            return redirect(url_for('main.dashboard'))
            
    return render_template('auth/change_password.html')
