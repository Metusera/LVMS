from flask import Flask, render_template, request, redirect, url_for, session,make_response, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import os
from zoneinfo import ZoneInfo
import csv
from flask_migrate import Migrate

from flask_admin import Admin
from sqlalchemy import extract
from werkzeug.security import generate_password_hash, check_password_hash
from flask_admin.contrib.sqla import ModelView
from flask_admin.base import AdminIndexView
from io import StringIO, BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from sqlalchemy import func

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'LVMS.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)
migrate = Migrate(app, db)
# Define the Kigali time zone
kigali_tz = ZoneInfo('Africa/Kigali')

# Model for Visitor
class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    purpose = db.Column(db.String(200))
    time_in = db.Column(db.DateTime, default=lambda: datetime.now(kigali_tz))
    time_out = db.Column(db.DateTime)
    has_computer = db.Column(db.Boolean, default=False)
    computer_brand = db.Column(db.String(50))
    computer_serial = db.Column(db.String(50))
    total_visits = db.Column(db.Integer, default=1)
    disability = db.Column(db.String(50))


    def __repr__(self):
        return f'<Visitor {self.name}>'

    def check_out(self):
        self.time_out = datetime.now(kigali_tz)
        db.session.commit()
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return session.get('is_admin', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class SecureModelView(ModelView):
    def is_accessible(self):
        return session.get('is_admin', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

# Setup admin
admin = Admin(app, name='IMS Admin', index_view=MyAdminIndexView(), template_mode='bootstrap4', base_template='admin_panel.html')
admin.add_view(SecureModelView(Visitor, db.session))

admin.add_view(SecureModelView(User, db.session))

@app.route('/admin/users')
def manage_users():
    if not session.get('is_admin'):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('login'))
    
    users = User.query.all() 
    admin_view = AdminIndexView()
    return render_template('manage_users.html', users=users, admin_view=admin_view)

@app.route('/admin/create-user', methods=['GET', 'POST'])
def create_user():
    if not session.get('is_admin'):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 'is_admin' in request.form
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('create_user'))
            
        new_user = User(username=username, is_admin=is_admin)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('User created successfully', 'success')
        return redirect(url_for('manage_users'))
    
    return render_template('create_user.html', admin_view=AdminIndexView())

@app.route('/admin/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if not session.get('is_admin'):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(user_id)
    admin_view = AdminIndexView()
    
    if request.method == 'POST':
        user.username = request.form['username']
        is_admin = 'is_admin' in request.form
        user.is_admin = is_admin
        
        if request.form['password']:
            user.set_password(request.form['password'])
            
        db.session.commit()
        flash('User updated successfully', 'success')
        return redirect(url_for('manage_users'))
    
    return render_template('edit_user.html', user=user,admin_view=admin_view)

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'):
        flash('You do not have permission to perform this action', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting the main admin account
    if user.username == 'admin':
        flash('Cannot delete the primary admin account', 'error')
        return redirect(url_for('manage_users'))
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('manage_users'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.active:
                flash('This account is inactive', 'error')
                return redirect(url_for('login'))
                
            session['user'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    user = session.get('user')
    session.pop('user', None)
    flash(f" {user} ""YOU HAVE BEEN LOGGED OUT", 'success')
    return redirect(url_for('login'))
@app.route('/')
def index():
    now = datetime.now(kigali_tz)
    # Get active visitors (not checked out)
    active_visitors = Visitor.query.filter_by(time_out=None).order_by(Visitor.time_in.desc()).all()

    # Count visitors with computers currently in the library
    computer_users = Visitor.query.filter(Visitor.has_computer==True, Visitor.time_out==None).count()

    # Count visitors who checked in today
    today_count = Visitor.query.filter(
        db.func.date(Visitor.time_in) == now.date()
    ).count()

    # Count visitors who checked in yesterday for comparison
    yesterday_count = Visitor.query.filter(
        db.func.date(Visitor.time_in) == (now - timedelta(days=1)).date()
    ).count()

    # Calculate percentage change
    today_change = round(((today_count - yesterday_count) / yesterday_count * 100), 1) if yesterday_count > 0 else 0
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html',
                           active_visitors=active_visitors,
                           computer_users=computer_users,
                           today_count=today_count,
                           today_change=today_change,
                           now=now  
                           )

@app.route('/check-in', methods=['GET', 'POST'])
def check_in():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form.get('email', '').strip()
        purpose = request.form.get('purpose', '').strip()
        has_computer = 'has_computer' in request.form
        computer_brand = request.form.get('computer_brand', '').strip()
        computer_serial = request.form.get('computer_serial', '').strip()

        if not name or not phone:
            flash('Name and phone are required', 'error')
            return redirect(url_for('check_in'))

        if has_computer and (not computer_brand or not computer_serial):
            flash('Computer brand and serial are required when bringing a computer', 'error')
            return redirect(url_for('check_in'))

        new_visitor = Visitor(
            name=name,
            phone=phone,
            email=email if email else None,
            purpose=purpose if purpose else None,
            has_computer=has_computer,
            computer_brand=computer_brand if has_computer else None,
            computer_serial=computer_serial if has_computer else None
        )

        db.session.add(new_visitor)
        db.session.commit()
        flash(f'{name} checked in successfully', 'success')
        return redirect(url_for('index'))

    return render_template('check_in.html')

@app.route('/check-out/<int:visitor_id>', methods=['GET', 'POST'])
def check_out(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)

    if request.method == 'POST':
        if visitor.has_computer:
            submitted_serial = request.form.get('computer_serial', '').strip()
            if submitted_serial != visitor.computer_serial:
                flash('Computer serial number does not match!', 'error')
                return redirect(url_for('check_out', visitor_id=visitor_id))

        visitor.check_out()
        flash('Checked out successfully', 'success')
        return redirect(url_for('index'))

    return render_template('check_out.html', visitor=visitor)

@app.route('/visitor/<int:visitor_id>/details')
def visitor_details(visitor_id):
    visitor = Visitor.query.get_or_404(visitor_id)
    return jsonify({
        'id': visitor.id,
        'name': visitor.name,
        'phone': visitor.phone,
        'email': visitor.email,
        'purpose': visitor.purpose,
        'time_in': visitor.time_in.astimezone(kigali_tz).strftime('%Y-%m-%d %H:%M:%S'),
        'time_out': visitor.time_out.astimezone(kigali_tz).strftime('%Y-%m-%d %H:%M:%S') if visitor.time_out else None,
        'has_computer': visitor.has_computer,
        'computer_brand': visitor.computer_brand,
        'computer_serial': visitor.computer_serial,
        'duration': str(visitor.time_out - visitor.time_in).split('.')[0] if visitor.time_out else None
    })

@app.route('/reports')
def reports():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = Visitor.query.order_by(Visitor.time_in.desc())

    # Apply filters
    if 'start_date' in request.args and request.args['start_date']:
        start_date = datetime.strptime(request.args['start_date'], '%Y-%m-%d').date()
        query = query.filter(db.func.date(Visitor.time_in) >= start_date)

    if 'end_date' in request.args and request.args['end_date']:
        end_date = datetime.strptime(request.args['end_date'], '%Y-%m-%d').date()
        query = query.filter(db.func.date(Visitor.time_in) <= end_date)

    if 'name' in request.args and request.args['name']:
        query = query.filter(Visitor.name.ilike(f"%{request.args['name']}%"))

    if 'computer' in request.args:
        if request.args['computer'] == 'with':
            query = query.filter(Visitor.has_computer == True)
        elif request.args['computer'] == 'without':
            query = query.filter(Visitor.has_computer == False)

    if 'status' in request.args:
        if request.args['status'] == 'active':
            query = query.filter(Visitor.time_out == None)
        elif request.args['status'] == 'completed':
            query = query.filter(Visitor.time_out != None)

    visitors = query.paginate(page=page, per_page=per_page)

    # Calculate statistics
    total_visits = Visitor.query.count()
    computer_users = Visitor.query.filter_by(has_computer=True).count()
    computer_percentage = round((computer_users / total_visits * 100) if total_visits > 0 else 0, 1)
    active_visits = Visitor.query.filter_by(time_out=None).count()
    active_computers = Visitor.query.filter(Visitor.has_computer==True, Visitor.time_out==None).count()

    # Calculate durations (for visitors who have checked out)
    completed_visits = Visitor.query.filter(Visitor.time_out.isnot(None)).all()
    durations = [(v.time_out - v.time_in).total_seconds() / 60 for v in completed_visits]
    avg_duration = round(sum(durations) / len(durations)) if durations else 0
    median_duration = round(sorted(durations)[len(durations)//2]) if durations else 0

    # Calculate visits today
    visits_today = Visitor.query.filter(
        db.func.date(Visitor.time_in) == datetime.now(kigali_tz).date()
    ).count()

    # Calculate average duration change from last week
    last_week_avg = 0
    if durations:
        last_week_start = datetime.now(kigali_tz) - timedelta(days=7)
        last_week_visits = Visitor.query.filter(
            Visitor.time_in >= last_week_start,
            Visitor.time_out.isnot(None)
        ).all()
        last_week_durations = [(v.time_out - v.time_in).total_seconds() / 60 for v in last_week_visits]
        last_week_avg = sum(last_week_durations) / len(last_week_durations) if last_week_durations else 0
        avg_duration_change = round(((avg_duration - last_week_avg) / last_week_avg * 100), 1) if last_week_avg > 0 else 0
    else:
        avg_duration_change = 0

    return render_template('reports.html',
        visitors=visitors,
        stats={
            'total_visits': total_visits,
            'computer_users': computer_users,
            'computer_percentage': computer_percentage,
            'avg_duration': avg_duration,
            'median_duration': median_duration,
            'active_visits': active_visits,
            'active_computers': active_computers,
            'visits_today': visits_today,
            'avg_duration_change': avg_duration_change
        },
        kigali_tz=kigali_tz
    )

@app.route('/export/<format>')
def export_reports(format):
    query = Visitor.query.order_by(Visitor.time_in.desc())

    # Apply the same filters as in the reports route
    if 'start_date' in request.args and request.args['start_date']:
        start_date = datetime.strptime(request.args['start_date'], '%Y-%m-%d').date()
        query = query.filter(db.func.date(Visitor.time_in) >= start_date)

    if 'end_date' in request.args and request.args['end_date']:
        end_date = datetime.strptime(request.args['end_date'], '%Y-%m-%d').date()
        query = query.filter(db.func.date(Visitor.time_in) <= end_date)

    if 'name' in request.args and request.args['name']:
        query = query.filter(Visitor.name.ilike(f"%{request.args['name']}%"))

    if 'computer' in request.args:
        if request.args['computer'] == 'with':
            query = query.filter(Visitor.has_computer == True)
        elif request.args['computer'] == 'without':
            query = query.filter(Visitor.has_computer == False)

    if 'status' in request.args:
        if request.args['status'] == 'active':
            query = query.filter(Visitor.time_out == None)
        elif request.args['status'] == 'completed':
            query = query.filter(Visitor.time_out != None)

    visitors = query.all()

    if format == 'csv':
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Name', 'Phone', 'Email', 'Purpose', 'Time In (Kigali)', 'Time Out (Kigali)', 
                    'Duration (minutes)', 'Has Computer', 'Computer Brand', 'Computer Serial'])
        for visitor in visitors:
            duration = (visitor.time_out - visitor.time_in).total_seconds() / 60 if visitor.time_out else None
            cw.writerow([
                visitor.id,
                visitor.name,
                visitor.phone,
                visitor.email or '',
                visitor.purpose or '',
                visitor.time_in.astimezone(kigali_tz).strftime('%Y-%m-%d %H:%M:%S'),
                visitor.time_out.astimezone(kigali_tz).strftime('%Y-%m-%d %H:%M:%S') if visitor.time_out else '',
                round(duration) if duration else '',
                'Yes' if visitor.has_computer else 'No',
                visitor.computer_brand if visitor.has_computer else '',
                visitor.computer_serial if visitor.has_computer else ''
            ])
        output = si.getvalue().encode('utf-8')
        return send_file(BytesIO(output), download_name='visitor_report.csv', mimetype='text/csv')

    elif format == 'pdf':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Add title
        story.append(Paragraph("Visitor Report", styles['Title']))
        
        # Add filters info if any
        filter_info = []
        if 'start_date' in request.args or 'end_date' in request.args:
            date_range = []
            if 'start_date' in request.args:
                date_range.append(f"From: {request.args['start_date']}")
            if 'end_date' in request.args:
                date_range.append(f"To: {request.args['end_date']}")
            filter_info.append(f"Date Range: {' '.join(date_range)}")
        
        if 'name' in request.args:
            filter_info.append(f"Name contains: {request.args['name']}")
        
        if 'computer' in request.args:
            filter_info.append(f"Computer: {'With' if request.args['computer'] == 'with' else 'Without'}")
        
        if 'status' in request.args:
            filter_info.append(f"Status: {'Active' if request.args['status'] == 'active' else 'Completed'}")
        
        if filter_info:
            story.append(Paragraph("<br/>".join(filter_info), styles['Normal']))
        
        story.append(Spacer(1, 0.2*inch))

        # Prepare table data
        data = [['ID', 'Name', 'Phone', 'Time In', 'Time Out', 'Duration', 'Computer']]
        for visitor in visitors:
            duration = (visitor.time_out - visitor.time_in).total_seconds() / 60 if visitor.time_out else None
            data.append([
                str(visitor.id),
                visitor.name,
                visitor.phone,
                visitor.time_in.astimezone(kigali_tz).strftime('%Y-%m-%d %H:%M'),
                visitor.time_out.astimezone(kigali_tz).strftime('%Y-%m-%d %H:%M') if visitor.time_out else 'Active',
                f"{round(duration)} mins" if duration else '',
                f"{visitor.computer_brand} ({visitor.computer_serial})" if visitor.has_computer else 'None'
            ])

        # Create table
        table = Table(data)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Align ID column left
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),  # Align Name column left
        ])
        table.setStyle(style)
        story.append(table)

        # Add summary statistics
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Summary Statistics", styles['Heading2']))
        
        stats_data = [
            ['Total Visits', len(visitors)],
            ['With Computers', sum(1 for v in visitors if v.has_computer)],
            ['Active Visits', sum(1 for v in visitors if not v.time_out)],
        ]
        
        stats_table = Table(stats_data, colWidths=[2*inch, 2*inch])
        stats_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ])
        stats_table.setStyle(stats_style)
        story.append(stats_table)

        # Add footer
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            f"Generated on {datetime.now(kigali_tz).strftime('%Y-%m-%d %H:%M:%S')}",
            styles['Italic']
        ))

        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, download_name='visitor_report.pdf', mimetype='application/pdf')

    elif format == 'print':
        return redirect(url_for('reports', **request.args))

    else:
        flash('Invalid export format', 'error')
        return redirect(url_for('reports', **request.args))

@app.route('/api/visitors/chart')
def visitors_chart_data():
    # Get data for the last 7 days
    end_date = datetime.now(kigali_tz).date()
    start_date = end_date - timedelta(days=6)
    
    # Query to count visitors per day
    daily_counts = db.session.query(
        func.date(Visitor.time_in).label('date'),
        func.count().label('count')
    ).filter(
        func.date(Visitor.time_in) >= start_date,
        func.date(Visitor.time_in) <= end_date
    ).group_by(
        func.date(Visitor.time_in)
    ).all()
    
    # Query to count computer users per day
    daily_computer_counts = db.session.query(
        func.date(Visitor.time_in).label('date'),
        func.count().label('count')
    ).filter(
        func.date(Visitor.time_in) >= start_date,
        func.date(Visitor.time_in) <= end_date,
        Visitor.has_computer == True
    ).group_by(
        func.date(Visitor.time_in)
    ).all()
    
    # Create a complete date range
    date_range = [start_date + timedelta(days=i) for i in range(7)]
    
    # Create dictionaries for easy lookup
    counts_dict = {date: count for date, count in daily_counts}
    computer_dict = {date: count for date, count in daily_computer_counts}
    
    # Prepare data for chart
    labels = [date.strftime('%a %d') for date in date_range]
    visitors_data = [counts_dict.get(date, 0) for date in date_range]
    computers_data = [computer_dict.get(date, 0) for date in date_range]
    
    return jsonify({
        'labels': labels,
        'datasets': [
            {
                'label': 'Total Visitors',
                'data': visitors_data,
                'backgroundColor': 'rgba(13, 110, 253, 0.5)',
                'borderColor': 'rgba(13, 110, 253, 1)',
                'borderWidth': 1
            },
            {
                'label': 'With Computers',
                'data': computers_data,
                'backgroundColor': 'rgba(25, 135, 84, 0.5)',
                'borderColor': 'rgba(25, 135, 84, 1)',
                'borderWidth': 1
            }
        ]
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', is_admin=True)
            admin_user.set_password('admin123')  
            db.session.add(admin_user)
            db.session.commit()
            print("Initial admin user created")
    app.run(debug=True)

x = 5
y = 6
z = x + y
print(z)