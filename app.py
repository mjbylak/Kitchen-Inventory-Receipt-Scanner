from flask import Flask, render_template, request, redirect, flash
import os
from google.cloud import documentai_v1 as documentai
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for flash messages
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def process_receipt_with_documentai(file_path):
    # Set your GCP project and processor details here
    project_id = "YOUR_PROJECT_ID"
    location = "us"  # Format: 'us' or 'eu'
    processor_id = "YOUR_PROCESSOR_ID"  # Create processor in GCP Console

    client = documentai.DocumentUnderstandingServiceClient()
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    with open(file_path, "rb") as image:
        image_content = image.read()

    raw_document = documentai.RawDocument(
        content=image_content,
        mime_type="application/pdf" if file_path.endswith(".pdf") else "image/jpeg",
    )
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    result = client.process_document(request=request)
    return result.document.text


@app.route("/", methods=["GET", "POST"])
def index():
    extracted_text = None
    if request.method == "POST":
        if "receipt" not in request.files:
            flash("No file part")
            return redirect(request.url)
        file = request.files["receipt"]
        if file.filename == "":
            flash("No selected file")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)
            try:
                extracted_text = process_receipt_with_documentai(file_path)
            except Exception as e:
                flash(f"Error processing document: {e}")
        else:
            flash("Invalid file type. Allowed: png, jpg, jpeg, pdf")
    return render_template("app.html", extracted_text=extracted_text)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
