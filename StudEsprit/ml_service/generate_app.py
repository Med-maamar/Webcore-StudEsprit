"""
Small Flask wrapper to expose the plan generator via HTTP.

This is optional — the Django app can also import the generator directly. The
Flask app keeps the integration simple if the user prefers a separate process.
"""
from flask import Flask, request, jsonify
from plan_generator import generate_plan

app = Flask(__name__)


@app.route('/generate_plan', methods=['POST'])
def generate_plan_endpoint():
    payload = request.get_json() or {}
    matieres = payload.get('matieres', [])
    unavailable = payload.get('unavailable', {})
    total_hours = payload.get('total_hours_per_week', 20)
    hours_range = payload.get('hours_range', list(range(8, 21)))
    plan = generate_plan(matieres, unavailable=unavailable, total_hours_per_week=total_hours, hours_range=hours_range)
    return jsonify(plan)


if __name__ == '__main__':
    app.run(port=5001, debug=True)
