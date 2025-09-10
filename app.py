import os
import requests
import pandas as pd
from flask import Flask, request, render_template, send_file, Response, stream_with_context, jsonify

# ---------- Flask Setup ----------
app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

API_SINGLE = "https://mail7.net/api/validate-single"

# ---------- Validate Single Email ----------
def validate_email(email: str):
    """Call Mail7 single email validation API"""
    try:
        response = requests.post(
            API_SINGLE,
            headers={"Content-Type": "application/json"},
            json={"email": email},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            print(f"[{email}] - Valid: {data.get('valid')}, SMTP: {data.get('smtpValid')}")
            status = "Valid" if data.get("valid") else "Invalid"
            return {"email": email, "status": status}
        else:
            return {"email": email, "status": f"HTTP {response.status_code}"}
    except Exception:
        return {"email": email, "status": "Invalid"}

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/validate-single", methods=["POST"])
def validate_single_route():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return {"error": "No email provided"}, 400

    result = validate_email(email)
    return jsonify(result)

@app.route("/validate-bulk", methods=["POST"])
def validate_bulk_route():
    file = request.files.get("file")
    if not file:
        return "No file uploaded", 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    # Read CSV or Excel
    if file.filename.endswith(".csv"):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    emails = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
    output_file = os.path.join(RESULT_FOLDER, f"validated_{file.filename}.csv")

    def generate():
        results = []
        for email in emails:
            res = validate_email(email)
            results.append(res)
            yield f"{res['email']} - {res['status']}\n"

        # Save results to CSV
        pd.DataFrame(results).to_csv(output_file, index=False)
        yield f"\n✅ Bulk validation completed.\nDownload CSV: /download/{os.path.basename(output_file)}\n"

    return Response(stream_with_context(generate()), mimetype="text/plain")

@app.route("/download/<path:filename>")
def download(filename):
    safe_path = os.path.join(RESULT_FOLDER, os.path.basename(filename))
    return send_file(safe_path, as_attachment=True)

# ---------- Run App ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render gives PORT env
    app.run(host="0.0.0.0", port=port, debug=True)
