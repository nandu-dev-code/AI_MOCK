import os
import tempfile
import unittest

from app import create_app, db


class InterviewAppTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, 'test.db')
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.db_path}'})
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.tmpdir.cleanup()

    def test_home_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_registration_and_login_flow(self):
        response = self.client.post('/register', data={
            'username': 'demo',
            'email': 'demo@example.com',
            'password': 'secret123',
            'confirm_password': 'secret123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome back', response.data)

        response = self.client.post('/login', data={
            'username': 'demo',
            'password': 'secret123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

    def test_dashboard_shows_interview_summary(self):
        self.client.post('/register', data={
            'username': 'demo',
            'email': 'demo@example.com',
            'password': 'secret123',
            'confirm_password': 'secret123'
        })
        self.client.post('/login', data={
            'username': 'demo',
            'password': 'secret123'
        })

        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Total Interviews', response.data)
        self.assertIn(b'Average Score', response.data)

    def test_interview_page_contains_recording_controls(self):
        self.client.post('/register', data={
            'username': 'demo',
            'email': 'demo@example.com',
            'password': 'secret123',
            'confirm_password': 'secret123'
        })
        self.client.post('/login', data={
            'username': 'demo',
            'password': 'secret123'
        })

        response = self.client.get('/interview')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Webcam Preview', response.data)
        self.assertIn(b'Record', response.data)
        self.assertIn(b'Submit', response.data)

    def test_interview_page_initializes_webcam(self):
        self.client.post('/register', data={
            'username': 'demo',
            'email': 'demo@example.com',
            'password': 'secret123',
            'confirm_password': 'secret123'
        })
        self.client.post('/login', data={
            'username': 'demo',
            'password': 'secret123'
        })

        response = self.client.get('/interview')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'getUserMedia', response.data)

    def test_answer_submission_creates_report_data(self):
        self.client.post('/register', data={
            'username': 'demo',
            'email': 'demo@example.com',
            'password': 'secret123',
            'confirm_password': 'secret123'
        })
        self.client.post('/login', data={
            'username': 'demo',
            'password': 'secret123'
        })

        response = self.client.post('/api/interview/submit', json={
            'question_id': 1,
            'answer': 'I have experience with Python, Flask, and SQLAlchemy.',
            'transcript': 'I have experience with Python, Flask, and SQLAlchemy.'
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('overall', payload)
        self.assertIn('feedback', payload)

    def test_reports_page_shows_saved_feedback_details(self):
        self.client.post('/register', data={
            'username': 'demo',
            'email': 'demo@example.com',
            'password': 'secret123',
            'confirm_password': 'secret123'
        })
        self.client.post('/login', data={
            'username': 'demo',
            'password': 'secret123'
        })

        self.client.post('/api/interview/submit', json={
            'question_id': 1,
            'answer': 'I have experience with Python, Flask, and SQLAlchemy.',
            'transcript': 'I have experience with Python, Flask, and SQLAlchemy.'
        })

        response = self.client.get('/reports')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AI Mock Interview', response.data)
        self.assertIn(b'Solid answer', response.data)
        self.assertIn(b'Python', response.data)


if __name__ == '__main__':
    unittest.main()
