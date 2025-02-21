from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import random
import json
import os
from datetime import datetime, timedelta

class Flashcard:
    def __init__(self, question, answer):
        self.question = question
        self.answer = answer
        self.last_reviewed = datetime.now()
        self.review_interval = 1
        self.correct_streak = 0

    def update_review_interval(self, correct):
        if correct:
            self.correct_streak += 1
            if self.correct_streak >= 2:
                self.review_interval *= 2
                self.correct_streak = 0
        else:
            self.review_interval = 1
            self.correct_streak = 0
        self.last_reviewed = datetime.now()

    def is_due_for_review(self):
        return datetime.now() >= self.last_reviewed + timedelta(days=self.review_interval)


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a real secret key in production

# File path for flashcards storage
FLASHCARDS_FILE = 'flashcards.json'

def load_flashcards():
    if os.path.exists(FLASHCARDS_FILE):
        with open(FLASHCARDS_FILE, 'r') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}

def save_flashcards(flashcards):
    with open(FLASHCARDS_FILE, 'w') as file:
        json.dump(flashcards, file, indent=4)

@app.before_request
def initialize_session():
    if 'scores' not in session:
        session['scores'] = {'right': 0, 'wrong': 0, 'not_given': 0}
    if 'index' not in session:
        session['index'] = 0
    if 'initialized' not in session:
        session['initialized'] = False

@app.route('/')
def home():
    session['scores'] = {'right': 0, 'wrong': 0, 'not_given': 0}
    session['index'] = 0
    session['initialized'] = True
    return render_template_string(home_html)

@app.route('/make_card', methods=['GET', 'POST'])
def make_card():
    flashcards = load_flashcards()
    if request.method == 'POST':
        category = request.form.get('category')
        if category:
            if category not in flashcards:
                flashcards[category] = []
                save_flashcards(flashcards)
                flash('Deck created successfully!', 'success')
            else:
                flash('Deck already exists!', 'error')
        else:
            flash('Category name is required!', 'error')
        return redirect(url_for('make_card'))
    
    return render_template_string(make_card_html, flashcards=flashcards)

@app.route('/add_card/<category>', methods=['GET', 'POST'])
def add_card(category):
    flashcards = load_flashcards()
    if request.method == 'POST':
        question = request.form['question']
        answer = request.form['answer']
        hint = request.form['hint']
        color = random.choice(['#f28b82', '#fbbc04', '#fff475', '#ccff90', '#a7ffeb', '#cbf0f8', '#aecbfa', '#d7aefb'])
        if not question or not answer or not hint:
            flash('Question, answer, and hint are mandatory!', 'error')
        else:
            flashcards[category].append({'question': question, 'answer': answer, 'hint': hint, 'color': color})
            save_flashcards(flashcards)
            flash('Flashcard added successfully!', 'success')
            return redirect(url_for('add_card', category=category))
    
    return render_template_string(add_card_html, category=category)

@app.route('/delete_deck/<deck_name>', methods=['POST'])
def delete_deck(deck_name):
    flashcards = load_flashcards()
    if deck_name in flashcards:
        del flashcards[deck_name]
        save_flashcards(flashcards)
        flash('Deck deleted successfully!', 'success')
    return redirect(url_for('make_card'))

@app.route('/exam', methods=['GET', 'POST'])
def exam():
    flashcards = load_flashcards()
    if request.method == 'GET':
        return render_template_string(exam_categories_html, categories=list(flashcards.keys()))
    
    category = request.form['category']
    if category not in flashcards or not flashcards[category]:
        return render_template_string(no_cards_exam_html)

    session['exam_category'] = category
    session['index'] = 0
    session['scores'] = {'right': 0, 'wrong': 0, 'not_given': 0}
    return redirect(url_for('exam_questions'))

@app.route('/exam_questions', methods=['GET', 'POST'])
def exam_questions():
    flashcards = load_flashcards()
    category = session.get('exam_category')
    if not category or category not in flashcards or not flashcards[category]:
        return redirect(url_for('exam'))

    cards = flashcards[category]
    index = session.get('index', 0)
    if index >= len(cards):
        session['index'] = 0  # Reset for next session or user
        return redirect(url_for('exam_results'))

    current_question = cards[index]['question']
    correct_answer = cards[index]['answer']
    hint = cards[index].get('hint', 'No hint available')
    show_answer = False
    show_hint = False

    if request.method == 'POST':
        action = request.form['action']
        if action == 'submit':
            user_answer = request.form.get('answer', '').strip()
            if user_answer.lower() == correct_answer.lower():
                session['scores']['right'] += 1
                flash('Correct answer!', 'success')
            else:
                session['scores']['wrong'] += 1
                flash(f'Wrong answer! The correct answer was: {correct_answer}', 'error')
            session['index'] += 1
            return redirect(url_for('exam_questions'))
        elif action == 'show':
            session['scores']['not_given'] += 1
            session['showing_answer'] = True
            return redirect(url_for('exam_questions'))
        elif action == 'next':
            session['index'] += 1
            session.pop('showing_answer', None)
            session.pop('showing_hint', None)
            return redirect(url_for('exam_questions'))
        elif action == 'show_hint':
            session['showing_hint'] = True
            return redirect(url_for('exam_questions'))
        elif action == 'submit_exam':
            return redirect(url_for('exam_results'))

    show_answer = session.pop('showing_answer', False)
    show_hint = session.get('showing_hint', False)
    is_last_question = index == len(cards) - 1
    return render_template_string(exam_html, question=current_question, hint=hint, scores=session['scores'], show_answer=show_answer, show_hint=show_hint, correct_answer=correct_answer, is_last_question=is_last_question)

@app.route('/exam_results')
def exam_results():
    scores = session.get('scores', {'right': 0, 'wrong': 0, 'not_given': 0})
    return render_template_string(exam_results_html, scores=scores)

@app.route('/see_all_cards', methods=['GET', 'POST'])
def see_all_cards():
    flashcards = load_flashcards()
    if request.method == 'GET':
        return render_template_string(view_categories_html, categories=list(flashcards.keys()))

    category = request.form['category']
    if category not in flashcards:
        return redirect(url_for('see_all_cards'))

    return render_template_string(see_all_cards_html, flashcards={category: flashcards[category]}, enumerate=enumerate)

@app.route('/edit_card/<category>/<int:card_id>', methods=['GET', 'POST'])
def edit_card(category, card_id):
    flashcards = load_flashcards()
    card = flashcards[category][card_id]
    if request.method == 'POST':  # Updated request method check
        question = request.form['question']
        answer = request.form['answer']
        hint = request.form['hint']
        if not question or not answer or not hint:
            flash('Question, answer, and hint are mandatory!', 'error')
        else:
            card['question'] = question
            card['answer'] = answer
            card['hint'] = hint
            save_flashcards(flashcards)
            flash('Flashcard updated successfully!', 'success')
            return redirect(url_for('see_all_cards'))
    return render_template_string(edit_card_html, card=card, category=category)

@app.route('/delete_card/<category>/<int:card_id>', methods=['POST'])
def delete_card(category, card_id):
    flashcards = load_flashcards()
    if 0 <= card_id < len(flashcards[category]):
        flashcards[category].pop(card_id)
        save_flashcards(flashcards)
        flash('Flashcard deleted successfully!', 'success')
    return redirect(url_for('see_all_cards'))

# HTML Templates
home_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flashcard App</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 110px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; text-align: center; }
        .btn { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; width: 100%; margin: 10px 0; font-size: 16px; display: block; }
        .btn:hover { background-color: #365492; }
    </style>
</head>
<body>
    <header><h1>Flashcard App</h1></header>
    <div class="container">
        <a href="{{ url_for('make_card') }}" class="btn">Create Deck</a>
        <a href="{{ url_for('exam') }}" class="btn">Take Exam</a>
        <a href="{{ url_for('see_all_cards') }}" class="btn">View All Flashcards</a>
    </div>
</body>
</html>
"""

make_card_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Create a Deck</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; position: relative; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; }
        form { display: flex; flex-direction: column; }
        form div { margin-bottom: 20px; }
        label { font-size: 16px; margin-bottom: 8px; color: #333; }
        input[type="text"] { padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; width: calc(100% - 24px); }
        button[type="submit"] { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; width: 100%; }
        button[type="submit"]:hover { background-color: #365492; }
        .message { color: green; font-size: 14px; text-align: center; margin-bottom: 20px; }
        .message.error { color: red; }
        .btn-home { position: absolute; top: 20px; left: 20px; padding: 10px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; }
        .btn-home:hover { background-color: #365492; }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; }
        .deck-item { display: flex; justify-content: space-between; align-items: center; }
        .deck-item a { text-decoration: none; color: #3b5998; }
        .deck-item button { padding: 5px 10px; background-color: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; transition: background-color 0.3s; }
        .deck-item button:hover { background-color: #e53935; }
    </style>
    <script>
        setTimeout(function() {
            var messages = document.querySelectorAll('.message');
            messages.forEach(function(message) {
                message.style.display = 'none';
            });
        }, 3000);
    </script>
</head>
<body>
    <a href="{{ url_for('home') }}" class="btn-home">Home</a>
    <header><h1>Create a Deck</h1></header>
    <div class="container">
        {% if initialized %}
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="message {{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        {% endif %}
        <form method="POST">
            <div>
                <label for="category">Deck Name:</label>
                <input type="text" id="category" name="category" required>
            </div>
            <button type="submit">Create Deck</button>
        </form>
        <h2>Existing Decks</h2>
        <ul>
            {% for deck in flashcards %}
                <li class="deck-item">
                    <a href="{{ url_for('add_card', category=deck) }}">{{ deck }}</a>
                    <form action="{{ url_for('delete_deck', deck_name=deck) }}" method="POST" style="display: inline;">
                        <button type="submit">Delete Deck</button>
                    </form>
                </li>
            {% endfor %}
        </ul>
    </div>
</body>
</html>
"""

add_card_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Add Flashcard to {{ category }}</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; position: relative; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; }
        form { display: flex; flex-direction: column; }
        form div { margin-bottom: 20px; }
        label { font-size: 16px; margin-bottom: 8px; color: #333; }
        input[type="text"] { padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; width: calc(100% - 24px); }
        button[type="submit"] { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; width: 100%; }
        button[type="submit"]:hover { background-color: #365492; }
        .message { color: green; font-size: 14px; text-align: center; margin-bottom: 20px; }
        .message.error { color: red; }
        .btn-back { position: absolute; top: 20px; left: 20px; padding: 10px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; }
        .btn-back:hover { background-color: #365492; }
    </style>
    <script>
        setTimeout(function() {
            var messages = document.querySelectorAll('.message');
            messages.forEach(function(message) {
                message.style.display = 'none';
            });
        }, 3000);
    </script>
</head>
<body>
    <a href="{{ url_for('make_card') }}" class="btn-back">Back</a>
    <header><h1>Add Flashcard to {{ category }}</h1></header>
    <div class="container">
        {% if initialized %}
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="message {{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        {% endif %}
        <form method="POST">
            <div>
                <label for="question">Question:</label>
                <input type="text" id="question" name="question" required>
            </div>
            <div>
                <label for="answer">Answer:</label>
                <input type="text" id="answer" name="answer" required>
            </div>
            <div>
                <label for="hint">Hint:</label>
                <input type="text" id="hint" name="hint" required>
            </div>
            <button type="submit">Save Flashcard</button>
        </form>
    </div>
</body>
</html>
"""

no_cards_exam_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No Flashcards</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; text-align: center; }
        .btn { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; width: 100%; margin: 10px 0; font-size: 16px; }
        .btn:hover { background-color: #365492; }
    </style>
</head>
<body>
    <header><h1>No Flashcards Available</h1></header>
    <div class="container">
        <p>No flashcards added. Please add some cards first to take the exam.</p>
        <a href="{{ url_for('make_card') }}" class="btn">Create Flashcard</a>
        <a href="{{ url_for('home') }}" class="btn">Home</a>
    </div>
</body>
</html>
"""

exam_categories_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select Deck for Exam</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; position: relative; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; }
        .btn { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; width: 100%; margin: 10px 0; font-size: 16px; display: block; }
        .btn:hover { background-color: #365492; }
        .btn-home { position: absolute; top: 20px; left: 20px; padding: 10px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; }
        .btn-home:hover { background-color: #365492; }
    </style>
</head>
<body>
    <a href="{{ url_for('home') }}" class="btn-home">Home</a>
    <header><h1>Select Deck for Exam</h1></header>
    <div class="container">
        {% for category in categories %}
            <form method="POST" action="{{ url_for('exam') }}">
                <input type="hidden" name="category" value="{{ category }}">
                <button type="submit" class="btn">{{ category }}</button>
            </form>
        {% endfor %}
    </div>
</body>
</html>
"""

exam_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=declarator-width, initial-scale=1.0">
    <title>Exam</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; position: relative; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; }
        form { display: flex; flex-direction: column; }
        form div { margin-bottom: 20px; display: flex; align-items: center; }
        label { font-size: 16px; margin-bottom: 8px; color: #333; margin-right: 10px; }
        input[type="text"] { padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; width: calc(100% - 24px); }
        .button-container { display: flex; justify-content: space-between; }
        button[type="submit"] { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; width: 48%; }
        button[type="submit"]:hover { background-color: #365492; }
        .scores { margin-top: 20px; text-align: center; }
        .answer-container { margin-top: 20px; background-color: #e8f5e9; padding: 10px; border-radius: 4px; text-align: center; }
        .hint-container { display: inline-block; position: relative; }
        .btn-back { position: absolute; top: 20px; left: 20px; padding: 10px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; }
        .btn-back:hover { background-color: #365492; }
        .hint-button { padding: 5px 10px; background-color: #ff9800; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 10px; }
        .hint-button:hover { background-color: #fb8c00; }
        .hint-text { visibility: hidden; margin-left: 10px; background-color: #fff; border: 1px solid #ccc; padding: 5px; border-radius: 4px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); white-space: nowrap; }
        .hint-container:hover .hint-text { visibility: visible; }
    </style>
</head>
<body>
    <a href="{{ url_for('exam') }}" class="btn-back">Back</a>
    <header><h1>Exam</h1></header>
    <div class="container">
        <form method="POST">
            <div>
                <label for="question">Question:</label>
                <p style="margin: 0;">{{ question }}</p>
            </div>
            {% if not show_answer %}
            <div>
                <label for="answer">Answer:</label>
                <input type="text" id="answer" name="answer">
            </div>
            {% if hint != 'No hint available' %}
            <div class="hint-container">
                <button type="button" class="hint-button">Hint</button>
                <span class="hint-text">{{ hint }}</span>
            </div>
            {% endif %}
            <div class="button-container">
                <button type="submit" name="action" value="submit">Submit Answer</button>
                <button type="submit" name="action" value="show">Show Answer</button>
            </div>
            {% else %}
            <div class="answer-container">
                <p>The correct answer is: {{ correct_answer }}</p>
            </div>
            <div class="button-container">
                {% if not is_last_question %}
                    <button type="submit" name="action" value="next">Next Question</button>
                {% else %}
                    <button type="submit" name="action" value="submit_exam">Submit Exam</button>
                {% endif %}
            </div>
            {% endif %}
        </form>
        <div class="scores">
            <p><strong>Right:</strong> {{ scores['right'] }}</p>
            <p><strong>Wrong:</strong> {{ scores['wrong'] }}</p>
            <p><strong>Not Given:</strong> {{ scores['not_given'] }}</p>
        </div>
    </div>
</body>
</html>
"""


exam_results_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exam Results</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; text-align: center; }
        .btn { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; width: 100%; margin: 10px 0; font-size: 16px; }
        .btn:hover { background-color: #365492; }
    </style>
</head>
<body>
    <div class="container">
        <header><h1>Exam Results</h1></header>
        <p><strong>Right Answers:</strong> {{ scores['right'] }}</p>
        <p><strong>Wrong Answers:</strong> {{ scores['wrong'] }}</p>
        <p><strong>Not Given:</strong> {{ scores['not_given'] }}</p>
        <a href="{{ url_for('home') }}" class="btn">Home</a>
    </div>
</body>
</html>
"""

view_categories_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select Deck to View</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; position: relative; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; }
        .btn { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; width: 100%; margin: 10px 0; font-size: 16px; display: block; }
        .btn:hover { background-color: #365492; }
        .btn-home { position: absolute; top: 20px; left: 20px; padding: 10px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; }
        .btn-home:hover { background-color: #365492; }
    </style>
</head>
<body>
    <a href="{{ url_for('home') }}" class="btn-home">Home</a>
    <header><h1>Select Deck to View</h1></header>
    <div class="container">
        {% for category in categories %}
            <form method="POST" action="{{ url_for('see_all_cards') }}">
                <input type="hidden" name="category" value="{{ category }}">
                <button type="submit" class="btn">{{ category }}</button>
            </form>
        {% endfor %}
    </div>
</body>
</html>
"""

see_all_cards_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Flashcards</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; position: relative; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 800px; margin: 40px auto; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .card { padding: 10px; border: 1px solid #ccc; border-radius: 5px; background-color: #f9f9f9; }
        .btn-back { position: absolute; top: 20px; left: 20px; padding: 10px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; }
        .btn-back:hover { background-color: #365492; }
        .no-cards-message { color: red; text-align: center; }
        .edit-btn, .delete-btn { padding: 5px 10px; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; margin-top: 10px; display: inline-block; }
        .edit-btn { background-color: #ff9800; }
        .edit-btn:hover { background-color: #fb8c00; }
        .delete-btn { background-color: #f44336; }
        .delete-btn:hover { background-color: #e53935; }
    </style>
</head>
<body>
    <a href="{{ url_for('see_all_cards') }}" class="btn-back">Back</a>
    <header><h1>All Flashcards</h1></header>
    <div class="container">
        {% for category, cards in flashcards.items() %}
            <h2>{{ category }}</h2>
            {% if cards %}
                <div class="cards">
                    {% for index, card in enumerate(cards) %}
                        <div class="card" style="background-color: {{ card.color }};">
                            <strong>Question:</strong> {{ card['question'] }}<br>
                            <strong>Answer:</strong> {{ card['answer'] }}<br>
                            <strong>Hint:</strong> {{ card['hint'] }}<br>
                            <a href="{{ url_for('edit_card', category=category, card_id=index) }}" class="edit-btn">Edit</a>
                            <form action="{{ url_for('delete_card', category=category, card_id=index) }}" method="POST" style="display: inline;">
                                <button type="submit" class="delete-btn">Delete</button>
                            </form>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <p class="no-cards-message">No cards in this deck.</p>
            {% endif %}
        {% endfor %}
    </div>
</body>
</html>
"""

edit_card_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Flashcard</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f0f5; margin: 0; padding: 0; position: relative; }
        header { background-color: #3b5998; color: white; padding: 20px; text-align: center; width: 100%; box-sizing: border-box; }
        .container { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 400px; margin: 40px auto; }
        form { display: flex; flex-direction: column; }
        form div { margin-bottom: 20px; }
        label { font-size: 16px; margin-bottom: 8px; color: #333; }
        input[type="text"] { padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; width: calc(100% - 24px); }
        button[type="submit"] { padding: 15px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; width: 100%; }
        button[type="submit"]:hover { background-color: #365492; }
        .btn-back { position: absolute; top: 20px; left: 20px; padding: 10px; background-color: #3b5998; color: white; border: none; border-radius: 4px; cursor: pointer; text-align: center; text-decoration: none; transition: background-color 0.3s; }
        .btn-back:hover { background-color: #365492; }
    </style>
</head>
<body>
    <a href="{{ url_for('see_all_cards') }}" class="btn-back">Back</a>
    <header><h1>Edit Flashcard</h1></header>
    <div class="container">
        <form method="POST">
            <div>
                <label for="question">Question:</label>
                <input type="text" id="question" name="question" value="{{ card['question'] }}" required>
            </div>
            <div>
                <label for="answer">Answer:</label>
                <input type="text" id="answer" name="answer" value="{{ card['answer'] }}" required>
            </div>
            <div>
                <label for="hint">Hint:</label>
                <input type="text" id="hint" name="hint" value="{{ card['hint'] }}" required>
            </div>
            <button type="submit">Update Flashcard</button>
        </form>
    </div>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=3000,debug=True)
