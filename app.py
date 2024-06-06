from flask import Flask, render_template, request, redirect, url_for, session
import random
import json
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for session management

# Dummy admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'password'

def load_mcqs(filename='data/mcqs_module1.json'):
    with open(filename, 'r') as file:
        return json.load(file)

def save_mcqs(mcqs, filename):
    with open(filename, 'w') as file:
        json.dump(mcqs, file)

def save_attempt(attempt):
    with open('data/attempts.json', 'r+') as file:
        data = json.load(file)
        data.append(attempt)
        file.seek(0)
        json.dump(data, file, indent=4)

def load_attempts():
    with open('data/attempts.json', 'r') as file:
        return json.load(file)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def shuffle_options(mcq):
    options = mcq['options']
    correct_answer_text = mcq['answer']  # Assuming 'answer' field in JSON is the text of the correct answer
    special_options = []
    if "All of the above" in options:
        options.remove("All of the above")
        special_options.append("All of the above")
    if "None of the above" in options:
        options.remove("None of the above")
        special_options.append("None of the above")
    random.shuffle(options)
    options.extend(special_options)
    if correct_answer_text not in options:
        raise ValueError(f"Correct answer '{correct_answer_text}' not found in options: {options}")
    correct_index = options.index(correct_answer_text)
    mcq['correct_answer_label'] = chr(65 + correct_index)  # Update the correct answer index to match shuffled options
    mcq['shuffled_options'] = list(zip(['A', 'B', 'C', 'D'][:len(options)], options))  # Handle cases with less than 4 options
    return mcq

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return 'Invalid credentials'
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def start():
    return render_template('start.html')

@app.route('/quiz', methods=['POST'])
def quiz():
    user_name = request.form['name']
    user_email = request.form['email']
    module = request.form['module']
    session['user_name'] = user_name
    session['user_email'] = user_email
    session['module'] = module

    # Load MCQs based on selected module
    if module == 'module1':
        mcqs = load_mcqs('data/mcqs_module1.json')
    else:
        mcqs = load_mcqs('data/mcqs_module2.json')

    # Randomize the questions
    randomized_mcqs = random.sample(mcqs, len(mcqs))
    for mcq in randomized_mcqs:
        shuffle_options(mcq)

    mcqs_filename = f'.cache/mcqs_{datetime.now().strftime("%Y%m%d%H%M%S")}.json'
    save_mcqs(randomized_mcqs, mcqs_filename)
    session['mcqs_file'] = mcqs_filename  # Store the filename in the session

    return render_template('quiz.html', results=randomized_mcqs, module=module, enumerate=enumerate)

@app.route('/submit', methods=['POST'])
def submit():
    user_name = session.get('user_name')
    user_email = session.get('user_email')
    module = session.get('module')
    mcqs_filename = session.get('mcqs_file')

    if not mcqs_filename or not os.path.exists(mcqs_filename):
        print("MCQs file not found.")
        return redirect(url_for('start'))

    with open(mcqs_filename, 'r') as file:
        randomized_mcqs = json.load(file)

    user_answers = [request.form.get(f'answer{i}') for i in range(len(randomized_mcqs))]
    score = 0
    results = []

    for i, mcq in enumerate(randomized_mcqs):
        correct_answer_label = mcq['correct_answer_label']
        user_answer = user_answers[i]
        user_answer_text = mcq['shuffled_options'][ord(user_answer) - 65][1]  # Get user answer text
        feedback = mcq.get('feedback', {}).get(user_answer_text, "No feedback available.")
        if user_answer == correct_answer_label:
            score += 1
        results.append({
            'question': mcq['question'],
            'correct_answer': correct_answer_label,
            'user_answer': user_answer,
            'shuffled_options': mcq['shuffled_options'],
            'feedback': feedback
        })

    total_questions = len(randomized_mcqs)
    percentage_score = round((score / total_questions) * 100, 2)

    # Save attempt
    attempt_id = len(load_attempts()) + 1
    attempt = {
        'attempt_id': attempt_id,
        'name': user_name,
        'email': user_email,
        'score': score,
        'total': total_questions,
        'percentage': percentage_score,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'module': module
    }
    save_attempt(attempt)

    # Remove the MCQs file to clean up
    os.remove(mcqs_filename)

    return render_template('result.html', name=user_name, email=user_email, score=score, total=total_questions, percentage=percentage_score, attempt_id=attempt_id, results=results, enumerate=enumerate)

@app.route('/admin')
@login_required
def admin():
    mcqs = load_mcqs()
    return render_template('admin.html', mcqs=mcqs, enumerate=enumerate)

@app.route('/attempts')
@login_required
def attempts():
    attempts = load_attempts()
    return render_template('attempts.html', attempts=attempts)

if __name__ == '__main__':
    # Initialize attempts file if it doesn't exist
    try:
        with open('data/attempts.json', 'x') as file:
            json.dump([], file)
    except FileExistsError:
        pass
    app.run(debug=True)
