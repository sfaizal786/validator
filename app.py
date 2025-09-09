import os
import requests
import pandas as pd
from flask import Flask, request, render_template, send_file
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- Flask Setup ----------
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# ---------- Rapid Email Verifier API ----------
API_URL = "https://rapid-email-verifier.fly.dev/api/validate/batch"

# ---------- Validate Emails ----------
def validate_batch(emails: list):
    """Send batch request to Rapid Email Verifier"""
    try:
        response = requests.post(
            API_URL,
            headers={"Content-Type": "application/json"},
            json={"emails": emails},
            timeout=30
        )
        print(f"\n📨 Batch request ({len(emails)} emails)")
        print(f"🔁 Response Code: {response.status_code}")

        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            return [{"email": e, "status": f"error {response.status_code}"} for e in emails]
    except Exception as e:
        return [{"email": e, "status": f"exception {e}"} for e in emails]


def validate_single_email(email: str):
    """Wrap one email in batch"""
    results = validate_batch([email])
    return results[0] if results else {"email": email, "status": "no result"}


# ---------- Routes ----------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/validate-single", methods=["POST"])
def validate_single():
    email = request.form.get("email")
    if not email:
        return "No email provided", 400

    result = validate_single_email(email)
    return render_template("index.html", single_result=result)


@app.route("/validate-bulk", methods=["POST"])
def validate_bulk():
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

    results = []
    chunk_size = 100  # API handles batch requests
    total_chunks = (len(emails) // chunk_size) + 1

    # Use ThreadPoolExecutor to send multiple chunks concurrently
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(validate_batch, emails[i*chunk_size:(i+1)*chunk_size]): i+1 for i in range(total_chunks)}
        for future in as_completed(futures):
            chunk_index = futures[future]
            print(f"✅ Chunk {chunk_index}/{total_chunks} done")
            results.extend(future.result())

    # Save results to file
    result_df = pd.DataFrame(results)
    output_file = os.path.join(RESULT_FOLDER, f"validated_{file.filename}.csv")
    result_df.to_csv(output_file, index=False)

    return render_template(
        "index.html",
        bulk_result_file=output_file,
        estimate_time=f"Processed {len(emails)} emails"
    )


@app.route("/download/<path:filename>")
def download(filename):
    return send_file(filename, as_attachment=True)


# ---------- Run App ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render sets the PORT environment variable
    app.run(host="0.0.0.0", port=port, debug=True)
