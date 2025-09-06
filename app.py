from flask import Flask, render_template, request, redirect, flash
import os
from google.cloud import documentai_v1 as documentai
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_entity_value(entity):
    text_anchor = entity.text_anchor
    return text_anchor.content if text_anchor else None


def process_line_item(entity):
    item = {}
    for property in entity.properties:
        prop_type = property.type_
        if prop_type == "line_item/description":
            item["description"] = get_entity_value(property)
        elif prop_type == "line_item/amount":
            item["amount"] = get_entity_value(property)
        elif prop_type == "line_item/quantity":
            item["quantity"] = get_entity_value(property)
    return item


def process_basic_entity(type_name, mention_text, extracted_data):
    if type_name == "merchant_name":
        extracted_data["merchant_name"] = mention_text
    elif type_name == "receipt_date":
        extracted_data["receipt_date"] = mention_text
    elif type_name == "total_amount":
        extracted_data["total_amount"] = mention_text


def process_line_item_name(entity):
    for property in entity.properties:
        if property.type_ == "line_item/description":
            return get_entity_value(property)
    return None


def extract_entities(document):
    extracted_data = {
        "merchant_name": None,
        "receipt_date": None,
        "total_amount": None,
        "items": [],
        "raw_text": document.text,
        "confidence": document.entities[0].confidence if document.entities else 0,
    }

    for entity in document.entities:
        type_name = entity.type_
        mention_text = get_entity_value(entity)

        if type_name == "line_item":
            item_name = process_line_item_name(entity)
            if item_name:
                extracted_data["items"].append({"name": item_name, "quantity": 1})
        else:
            process_basic_entity(type_name, mention_text, extracted_data)

    return extracted_data


def process_receipt_with_documentai(file_path):
    project_id = "YOUR_PROJECT_ID"
    location = "us"
    processor_id = "YOUR_PROCESSOR_ID"

    # Initialize the Document AI client
    client = documentai.DocumentProcessorServiceClient()
    processor_name = (
        f"projects/{project_id}/locations/{location}/processors/{processor_id}"
    )

    # Read the file
    with open(file_path, "rb") as image:
        image_content = image.read()

    # Create the document object
    document = documentai.Document(
        content=image_content,
        mime_type="application/pdf" if file_path.endswith(".pdf") else "image/jpeg",
    )

    # Process the document
    request = documentai.ProcessRequest(name=processor_name, document=document)
    result = client.process_document(request=request)

    return extract_entities(result.document)


@app.route("/", methods=["GET", "POST"])
def index():
    extracted_data = None
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
                extracted_data = process_receipt_with_documentai(file_path)
            except Exception as e:
                flash(f"Error processing document: {e}")
        else:
            flash("Invalid file type. Allowed: png, jpg, jpeg, pdf")
    return render_template("app.html", receipt_data=extracted_data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
