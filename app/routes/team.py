from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from app import db
from app.models import User, Department, TeamMember, Task
from functools import wraps
from datetime import datetime

team_bp = Blueprint('team', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@team_bp.route('/')
@admin_required
def dashboard():
    departments = Department.query.all()
    team_members = TeamMember.query.all()
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    users = User.query.all()
    return render_template('team/dashboard.html', departments=departments, team_members=team_members, tasks=tasks, users=users)

@team_bp.route('/department/add', methods=['POST'])
@admin_required
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
@admin_required
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
@admin_required
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
