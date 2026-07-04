import os
from datetime import datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(80), default='General')
    difficulty = db.Column(db.String(40), default='Medium')


class InterviewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic = db.Column(db.String(120), nullable=False, default='General Interview')
    score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    duration = db.Column(db.Integer, default=0)
    transcript = db.Column(db.Text, default='')
    feedback = db.Column(db.Text, default='')


class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey('interview_session.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    transcript = db.Column(db.Text, default='')
    grammar_score = db.Column(db.Integer, default=0)
    technical_score = db.Column(db.Integer, default=0)
    communication_score = db.Column(db.Integer, default=0)
    confidence_score = db.Column(db.Integer, default=0)
    overall_score = db.Column(db.Integer, default=0)
    feedback = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def seed_questions():
    if Question.query.count() == 0:
        sample_questions = [
            ('Tell me about yourself and your professional background.', 'Intro', 'Easy'),
            ('How would you build a Flask application for a mock interview platform?', 'Technical', 'Medium'),
            ('Describe a challenge you faced and how you solved it.', 'Behavioral', 'Medium'),
        ]
        for question_text, category, difficulty in sample_questions:
            db.session.add(Question(question=question_text, category=category, difficulty=difficulty))
        db.session.commit()


def ensure_interview_schema():
    inspector = inspect(db.engine)
    interview_columns = {column['name'] for column in inspector.get_columns('interview_session')}
    answer_columns = {column['name'] for column in inspector.get_columns('answer')}
    user_columns = {column['name'] for column in inspector.get_columns('user')}

    with db.engine.begin() as connection:
        if 'created_at' not in interview_columns:
            connection.execute(text("ALTER TABLE interview_session ADD COLUMN created_at DATETIME"))
        if 'duration' not in interview_columns:
            connection.execute(text("ALTER TABLE interview_session ADD COLUMN duration INTEGER DEFAULT 0"))
        if 'transcript' not in interview_columns:
            connection.execute(text("ALTER TABLE interview_session ADD COLUMN transcript TEXT DEFAULT ''"))
        if 'feedback' not in interview_columns:
            connection.execute(text("ALTER TABLE interview_session ADD COLUMN feedback TEXT DEFAULT ''"))

        if 'created_at' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN created_at DATETIME"))
        if 'transcript' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN transcript TEXT DEFAULT ''"))
        if 'grammar_score' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN grammar_score INTEGER DEFAULT 0"))
        if 'technical_score' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN technical_score INTEGER DEFAULT 0"))
        if 'communication_score' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN communication_score INTEGER DEFAULT 0"))
        if 'confidence_score' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN confidence_score INTEGER DEFAULT 0"))
        if 'overall_score' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN overall_score INTEGER DEFAULT 0"))
        if 'feedback' not in answer_columns:
            connection.execute(text("ALTER TABLE answer ADD COLUMN feedback TEXT DEFAULT ''"))

        if 'role' not in user_columns:
            connection.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))


def evaluate_answer(answer_text: str, transcript: str) -> dict:
    combined = f"{answer_text} {transcript}".lower()
    keywords = ['python', 'flask', 'sql', 'api', 'team', 'project', 'database', 'experience']
    keyword_hits = sum(1 for keyword in keywords if keyword in combined)

    grammar_score = min(100, 70 + keyword_hits * 3 + (len(answer_text.split()) >= 8) * 5)
    technical_score = min(100, 72 + keyword_hits * 4 + (len(answer_text.split()) >= 10) * 3)
    communication_score = min(100, 74 + (len(answer_text.split()) >= 10) * 5 + (len(answer_text.split()) >= 16) * 2)
    confidence_score = min(100, 75 + (len(answer_text.split()) >= 8) * 4 + (len(answer_text.split()) >= 12) * 2)
    overall_score = round((grammar_score + technical_score + communication_score + confidence_score) / 4)

    strengths = []
    weaknesses = []
    if keyword_hits >= 2:
        strengths.append('Relevant technical vocabulary')
    else:
        weaknesses.append('Add more domain-specific detail')
    if len(answer_text.split()) >= 10:
        strengths.append('Clear structure and detail')
    else:
        weaknesses.append('Expand your response with more examples')
    if overall_score >= 85:
        feedback = 'Strong delivery with confident structure and clear reasoning.'
    elif overall_score >= 70:
        feedback = 'Solid answer with room to strengthen technical depth and clarity.'
    else:
        feedback = 'The response needs more specificity, organization, and stronger examples.'

    return {
        'grammar': grammar_score,
        'technical': technical_score,
        'communication': communication_score,
        'confidence': confidence_score,
        'overall': overall_score,
        'feedback': feedback,
        'strengths': strengths,
        'weaknesses': weaknesses,
    }


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///ai_interview.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        ensure_interview_schema()
        seed_questions()

    @app.before_request
    def load_logged_in_user():
        user_id = session.get('user_id')
        app.jinja_env.globals['current_user'] = None
        app.jinja_env.globals['current_year'] = datetime.now().year
        if user_id is None:
            return
        user = db.session.get(User, user_id)
        app.jinja_env.globals['current_user'] = user

    @app.route('/')
    def home():
        if session.get('user_id'):
            return redirect(url_for('dashboard'))
        return render_template('index.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not username or not email or not password:
                flash('Please complete every field.', 'danger')
            elif password != confirm_password:
                flash('Passwords do not match.', 'danger')
            elif User.query.filter((User.username == username) | (User.email == email)).first():
                flash('A user with that username or email already exists.', 'danger')
            else:
                user = User(username=username, email=email)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash('Welcome back! Please sign in.', 'success')
                return redirect(url_for('login'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session.clear()
                session['user_id'] = user.id
                flash('You are now signed in.', 'success')
                return redirect(url_for('dashboard'))
            flash('Invalid username or password.', 'danger')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.', 'info')
        return redirect(url_for('home'))

    @app.route('/dashboard')
    def dashboard():
        if not session.get('user_id'):
            return redirect(url_for('login'))
        sessions = InterviewSession.query.filter_by(user_id=session['user_id']).order_by(InterviewSession.created_at.desc()).all()
        total_interviews = len(sessions)
        average_score = round(sum(session.score for session in sessions) / total_interviews, 1) if total_interviews else 0
        return render_template('dashboard.html', sessions=sessions, total_interviews=total_interviews, average_score=average_score)

    @app.route('/interview')
    def interview():
        if not session.get('user_id'):
            return redirect(url_for('login'))
        questions = Question.query.order_by(Question.id).all()
        questions_payload = [{'id': question.id, 'question': question.question} for question in questions]
        return render_template('interview.html', questions=questions_payload)

    @app.route('/reports')
    def reports():
        if not session.get('user_id'):
            return redirect(url_for('login'))

        sessions = InterviewSession.query.filter_by(user_id=session['user_id']).order_by(InterviewSession.created_at.desc()).all()
        report_items = []
        for session_item in sessions:
            answers = Answer.query.filter_by(interview_id=session_item.id).order_by(Answer.id).all()
            report_items.append({
                'session': session_item,
                'answers': answers,
            })
        return render_template('reports.html', report_items=report_items)

    @app.route('/admin')
    def admin():
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return render_template('admin.html')

    @app.route('/api/interview/submit', methods=['POST'])
    def submit_interview():
        if not session.get('user_id'):
            return jsonify({'error': 'Authentication required'}), 401

        payload = request.get_json(silent=True) or {}
        answer_text = (payload.get('answer') or '').strip()
        transcript = (payload.get('transcript') or '').strip()
        question_id = payload.get('question_id', 1)

        if not answer_text and not transcript:
            return jsonify({'error': 'An answer is required'}), 400

        evaluation = evaluate_answer(answer_text, transcript)
        interview_session = InterviewSession(
            user_id=session['user_id'],
            topic='AI Mock Interview',
            score=evaluation['overall'],
            duration=payload.get('duration', 0),
            transcript=transcript,
            feedback=evaluation['feedback'],
        )
        db.session.add(interview_session)
        db.session.flush()

        db.session.add(Answer(
            interview_id=interview_session.id,
            question_id=question_id,
            answer_text=answer_text,
            transcript=transcript,
            grammar_score=evaluation['grammar'],
            technical_score=evaluation['technical'],
            communication_score=evaluation['communication'],
            confidence_score=evaluation['confidence'],
            overall_score=evaluation['overall'],
            feedback=evaluation['feedback'],
        ))
        db.session.commit()

        return jsonify({
            'message': 'Interview answer recorded',
            'overall': evaluation['overall'],
            'feedback': evaluation['feedback'],
            'strengths': evaluation['strengths'],
            'weaknesses': evaluation['weaknesses'],
        })

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)