import os
import random

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from wordle_solver import solver_lib, hybrid_solver

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load word data
total_words = pd.read_fwf("wordle_solver/words_alpha.txt", names=["words"])
words = total_words[total_words["words"].str.len() == 5]
words_data = [tuple(ord(c) - ord('a') for c in word) for word in words["words"]]

# Game state
current_game = {
    "target_word": None,
    "guesses": [],
    "feedback": []
}

@app.route('/new-game', methods=['POST'])
def new_game():
    """Start a new Wordle game with a random target word.
    
    Returns:
        JSON response with game state
    """
    current_game["target_word"] = solver_lib.choose_target(words["words"].tolist())
    current_game["guesses"] = []
    current_game["feedback"] = []
    return jsonify(current_game)

@app.route('/solver-guess', methods=['GET'])
def get_solver_guess():
    """Get solution from the CSP-based solver.
    
    Returns:
        JSON response with guesses, feedback, and remaining word counts
    """
    response = solver_lib.solve_wordle(
        valid_words=words_data,
        target_word=current_game["target_word"],
        max_attempts=6,
        print_output=False
    )
    return jsonify({
        "guesses": response["guesses"],
        "feedback": response["feedback"],
        "nb_possible_words": response["nb_possible_words"],
    })

@app.route('/hybrid-solver', methods=['GET'])
def get_hybrid_solver_guess():
    """Get solution from the hybrid CSP+LLM solver.
    
    Returns:
        JSON response with guesses, feedback, word counts, and explanations
        
    Raises:
        500: If OpenAI API key is not configured
    """
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({
            "error": "OpenAI API key not found. Please set OPENAI_API_KEY environment variable."
        }), 500
    
    try:
        response = hybrid_solver.solve_wordle_hybrid(
            valid_words=words_data,
            target_word=current_game["target_word"],
            max_attempts=6,
            print_output=False
        )
        return jsonify({
            "guesses": response["guesses"],
            "feedback": response["feedback"],
            "nb_possible_words": response["nb_possible_words"],
            "explanations": response["explanations"]
        })
    except Exception as e:
        return jsonify({"error": f"Solver failed: {str(e)}"}), 500

@app.route('/user-guess', methods=['POST'])
def process_user_guess():
    """Process a user's guess and return feedback.
    
    Expected JSON payload:
        {"guess": "word"}
    
    Returns:
        JSON response with guess validation and feedback
        
    Raises:
        400: If guess is invalid (wrong length or not in dictionary)
    """
    data = request.json
    guess = data.get('guess', '').lower()
    
    # Validate guess
    if len(guess) != 5 or guess not in words["words"].tolist():
        return jsonify({"error": "Invalid guess. Must be a valid 5-letter word"}), 400
    
    # Generate feedback
    feedback = solver_lib.get_feedback(
        tuple(ord(c) - ord('a') for c in guess), 
        [ord(c) - ord('a') for c in current_game["target_word"]]
    )
    
    # Update game state
    current_game["guesses"].append(guess)
    current_game["feedback"].append(feedback)
    
    # Calculate remaining possibilities
    valid_words_int = words_data.copy()
    for g, f in zip(current_game["guesses"], current_game["feedback"]):
        g_int = tuple(ord(c) - ord('a') for c in g)
        valid_words_int = solver_lib.filter_valid_words(valid_words_int, g_int, f)
    
    return jsonify({
        "guess": guess,
        "feedback": feedback,
        "possible_words_count": len(valid_words_int),
        "solved": ''.join(feedback) == 'GGGGG'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)