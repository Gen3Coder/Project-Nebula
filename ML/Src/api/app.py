"""Small HTTP service around the false-start model, for the backend (SERVER) team.

Run:   pip install -r ML/Src/api/requirements.txt
       python ML/Src/api/app.py                (development, port 8001)
       gunicorn -w 2 -b 0.0.0.0:8001 --chdir ML/Src/api app:app     (production, Linux)

Endpoints
  GET  /health   -> {"status": "ok"}
  GET  /meta     -> required inputs, valid region/window pairs, thresholds, model card
  POST /predict  -> one event (JSON object)  or  {"events": [ ... ]} for several
  POST /monitor  -> daily "Risk now" card for an onset that already happened (see ML/API_CONTRACT.md)
See ML/API_CONTRACT.md for the exact JSON.
"""
import json
import sys
from pathlib import Path

from flask import Flask, jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modeling"))
from predict import MODEL_PATH, load_bundle, predict_false_start  # noqa: E402
from predict_monitor import monitor_history, monitor_status  # noqa: E402

app = Flask(__name__)
CARD_PATH = MODEL_PATH.parent / "model_card.json"


def _clean(event):
    if not isinstance(event, dict):
        raise ValueError("each event must be a JSON object")
    for k in ("region", "window"):
        if not event.get(k):
            raise ValueError(f"'{k}' is required")
    return event


@app.get("/health")
def health():
    load_bundle()
    return jsonify(status="ok")


@app.get("/meta")
def meta():
    b = load_bundle()
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    return jsonify(required_numeric_inputs=b["numeric_features"],
                   required_text_inputs=b["categorical_features"],
                   valid_region_window=b["valid_region_windows"],
                   threshold=b["threshold"], risk_bands=b["risk_bands"], model_card=card)


@app.post("/predict")
def predict():
    body = request.get_json(silent=True)
    if body is None:
        return jsonify(error="send a JSON body"), 400
    try:
        if isinstance(body, dict) and "events" in body:
            return jsonify(results=[predict_false_start(_clean(e)) for e in body["events"]])
        return jsonify(predict_false_start(_clean(body)))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400


@app.post("/monitor")
def monitor():
    body = request.get_json(silent=True) or {}
    try:
        for k in ("region", "window", "trigger_date", "daily"):
            if not body.get(k):
                raise ValueError(f"'{k}' is required")
        fn = monitor_history if body.get("history") else monitor_status
        res = fn(body["region"], body["window"], body["trigger_date"], body["daily"])
        return jsonify(days=res) if body.get("history") else jsonify(res)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
