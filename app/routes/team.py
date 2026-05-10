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
    user_id = request.form.get('user_id')
    department_id = request.form.get('department_id')
    role = request.form.get('role', 'Member')
    
    if not user_id or not department_id:
        flash('User and Department are required.', 'error')
        return redirect(url_for('team.dashboard'))
        
    if TeamMember.query.filter_by(user_id=user_id).first():
        flash('User is already a team member.', 'error')
    else:
        member = TeamMember(user_id=user_id, department_id=department_id, role=role)
        db.session.add(member)
        db.session.commit()
        flash('Team member added successfully.', 'success')
        
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
