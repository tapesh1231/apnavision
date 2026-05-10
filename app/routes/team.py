from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from app import db
from app.models import User, Department, TeamMember, Task
from functools import wraps
from datetime import datetime

team_bp = Blueprint('team', __name__)

def manager_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        is_manager = current_user.team_profile and current_user.team_profile.role == 'Manager'
        if not (current_user.is_admin or is_manager):
            flash('Admin or Manager access required.', 'error')
            return redirect(url_for('team.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def team_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not (current_user.is_admin or current_user.team_profile):
            flash('Team access required.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@team_bp.route('/')
@team_or_admin_required
def dashboard():
    departments = Department.query.all()
    team_members = TeamMember.query.all()
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    users = User.query.all()
    return render_template('team/dashboard.html', departments=departments, team_members=team_members, tasks=tasks, users=users)

@team_bp.route('/department/add', methods=['POST'])
@manager_or_admin_required
def add_department():
    name = request.form.get('name')
    description = request.form.get('description')
    
    if Department.query.filter_by(name=name).first():
        flash('Department already exists.', 'error')
    else:
        dept = Department(name=name, description=description)
        db.session.add(dept)
        db.session.commit()
        flash('Department added successfully.', 'success')
        
    return redirect(url_for('team.dashboard'))

@team_bp.route('/member/add', methods=['POST'])
@manager_or_admin_required
def add_member():
    name = request.form.get('name')
    email = request.form.get('email')
    department_id = request.form.get('department_id')
    role = request.form.get('role', 'Member')
    
    if not name or not email or not department_id:
        flash('Name, Email, and Department are required.', 'error')
        return redirect(url_for('team.dashboard'))
        
    user = User.query.filter_by(email=email).first()
    if not user:
        import secrets
        import string
        from app.utils import send_email
        
        # Generate a random 10-character password
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for i in range(10))
        
        user = User(username=name, email=email, must_change_password=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush() # Get user ID
        
        email_body = f"""Hello {name},

You have been added to the team at ApnaVision!
Your login credentials are:
Email: {email}
Password: {password}

You will be required to change this password upon your first login.

Best regards,
ApnaVision Admin Team"""
        send_email("Welcome to the ApnaVision Team", email, email_body)
        
    if TeamMember.query.filter_by(user_id=user.id).first():
        flash('User is already a team member.', 'error')
    else:
        member = TeamMember(user_id=user.id, department_id=department_id, role=role)
        db.session.add(member)
        db.session.commit()
        flash('Team member added and credentials emailed successfully.', 'success')
        
    return redirect(url_for('team.dashboard'))

@team_bp.route('/task/add', methods=['POST'])
@manager_or_admin_required
def add_task():
    title = request.form.get('title')
    description = request.form.get('description')
    assigned_to_id = request.form.get('assigned_to_id')
    
    if not title:
        flash('Task title is required.', 'error')
        return redirect(url_for('team.dashboard'))
        
    due_date_str = request.form.get('due_date')
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
    
    task = Task(title=title, description=description, assigned_to_id=assigned_to_id or None,
                created_by_id=current_user.id, due_date=due_date)
    db.session.add(task)
    db.session.commit()
    flash('Task assigned successfully.', 'success')
    
    return redirect(url_for('team.dashboard'))

@team_bp.route('/task/<int:task_id>/update', methods=['POST'])
@login_required
def update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    # Only assigned member or admin can update
    if current_user.is_admin or (task.assignee and task.assignee.user_id == current_user.id):
        new_status = request.form.get('status')
        if new_status in ['Pending', 'In Progress', 'Completed']:
            task.status = new_status
            db.session.commit()
            flash('Task status updated.', 'success')
    else:
        flash('Unauthorized to update this task.', 'error')
        
    if current_user.is_admin:
        return redirect(url_for('team.dashboard'))
    return redirect(url_for('main.dashboard'))

@team_bp.route('/sales-hub')
@login_required
def sales_hub():
    """Dashboard specifically for the Sales Team to handle inquiries."""
    # Check if user is admin or in Sales
    is_sales = False
    if current_user.team_profile and current_user.team_profile.department.name.lower() == 'sales':
        is_sales = True
        
    if not (current_user.is_admin or is_sales):
        flash('Unauthorized access. Sales Team only.', 'error')
        return redirect(url_for('main.dashboard'))
        
    from app.models import Inquiry
    
    # Active inquiries: New or assigned to current user and not closed
    unassigned_inquiries = Inquiry.query.filter_by(status='New', assigned_to_id=None).order_by(Inquiry.created_at.desc()).all()
    
    if current_user.is_admin:
        my_inquiries = Inquiry.query.filter(Inquiry.assigned_to_id != None).order_by(Inquiry.updated_at.desc()).all()
    else:
        my_inquiries = Inquiry.query.filter_by(assigned_to_id=current_user.team_profile.id).order_by(Inquiry.updated_at.desc()).all()
        
    # Performance Stats
    total_handled = 0
    total_converted = 0
    if current_user.team_profile:
        total_handled = Inquiry.query.filter_by(assigned_to_id=current_user.team_profile.id).count()
        total_converted = Inquiry.query.filter_by(assigned_to_id=current_user.team_profile.id, status='Converted').count()
        
    return render_template('team/sales_hub.html', 
                          unassigned=unassigned_inquiries, 
                          my_inquiries=my_inquiries,
                          total_handled=total_handled,
                          total_converted=total_converted)

@team_bp.route('/inquiry/<int:inquiry_id>/update', methods=['POST'])
@login_required
def update_inquiry(inquiry_id):
    from app.models import Inquiry
    inquiry = Inquiry.query.get_or_404(inquiry_id)
    
    action = request.form.get('action')
    notes = request.form.get('notes')
    
    if action == 'claim':
        if not inquiry.assigned_to_id and current_user.team_profile:
            inquiry.assigned_to_id = current_user.team_profile.id
            inquiry.status = 'Contacted'
            flash('Inquiry claimed successfully. You are now the owner.', 'success')
            
    elif action == 'update':
        new_status = request.form.get('status')
        if new_status:
            inquiry.status = new_status
        if notes:
            inquiry.notes = notes
        flash('Inquiry updated successfully.', 'success')
        
    db.session.commit()
    return redirect(url_for('team.sales_hub'))
