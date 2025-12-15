"""Flask application for ClinVar Annotator."""

import os
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request

from clinvar_anno_app.models import db, Patient, Variant, PatientVariant
from clinvar_anno_core.main import VariantAnnotationPipeline
from clinvar_anno_core.utils.logger import logger


app = Flask(__name__)
app.secret_key = "supersecretkey"

# SQLite database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, "clinvar_annotator.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure upload folder for temporary VCF storage
UPLOAD_FOLDER = "temp_uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db.init_app(app)

# Create the database if it doesn't exist
with app.app_context():
    db.create_all()
    logger.info("Database initialised (or it already existed).")

# Initialise the ClinVar annotation pipeline
annotation_pipeline = VariantAnnotationPipeline()


@app.route("/", methods=["GET", "POST"])
def home():
    """
    Handler for ClinVar Annotator application home page display, VCF upload, 
    variant annotation (calling on functionality from clinvar_anno_core), and 
    display of annotated data in a table.

    Args:
        None (uses Flask `request` object)

    Returns:
        Flask Response: Renders either the VCF upload form (GET) or
        the annotated variant table (POST)

    Raises:
        Logs exceptions internally; errors in processing do not propagate.
    """
    if request.method == "POST":
        files = request.files.getlist("vcf_files")
        filenames = [f.filename for f in files]
        logger.info(f"Received POST request with {len(files)} VCF file(s): {filenames}")

        # Process each uploaded VCF file
        for file in files:
            if not file or not file.filename.endswith(".vcf"):
                logger.warning(
                    f"Skipped invalid or non-VCF file(s): {file.filename if file else 'None'}"
                )
                continue

            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            logger.info(f"Saved uploaded VCF file temporarily: {filepath}")

            try:
                # Extract patient ID from filename
                patient_id = os.path.splitext(filename)[0]
                logger.debug(f"Processed patient ID from filename: {patient_id}")

                # Run annotation pipeline on the saved file
                annotated_variants = annotation_pipeline.process_vcf(Path(filepath))
                logger.info(
                    f"Annotation pipeline completed for {filename} with {len(annotated_variants)} variants."
                )

                if not annotated_variants:
                    logger.warning(f"No variants in {filename}.")
                    continue

                # Check if patient exists in the database, and if not, add a new record
                patient_obj = Patient.query.filter_by(patient_id=patient_id).first()
                if not patient_obj:
                    patient_obj = Patient(patient_id=patient_id)
                    db.session.add(patient_obj)
                    db.session.commit()
                    logger.debug(
                        f"Added new patient record to the database: {patient_id}"
                    )
                else:
                    logger.debug(
                        f"Existing patient record found in the database: {patient_id}"
                    )

                # Loop through variants and their annotations
                for variant_key, annotation_data in annotated_variants.items():
                    try:
                        # Parse variant info into VCF description format
                        # parts = variant_key.split(':')
                        # chrom, pos, ref, alt = parts
                        # formatted_variant = f"GRCh38:{chrom}:{pos}:{ref}:{alt}"
                        formatted_variant = variant_key

                        # Extract gene symbol
                        gene_symbol = None
                        if annotation_data.get("genes"):
                            gene_symbol = annotation_data["genes"][0].get("symbol")

                        # Extract only the first protein change (MANE Select)
                        protein_change_raw = annotation_data.get("protein_change", "")
                        protein_change = (
                            protein_change_raw.split(",")[0].strip()
                            if "," in protein_change_raw
                            else protein_change_raw
                        )

                        # Extract only the first molecular consequence (MANE Select)
                        molecular_consequences_list = annotation_data.get(
                            "molecular_consequences", []
                        )
                        molecular_consequence = (
                            molecular_consequences_list[0]
                            if molecular_consequences_list
                            else ""
                        )

                        # Map review status to star ratings
                        review_status = annotation_data.get("review_status", "")
                        review_status_stars = ""
                        if "practice guideline" in review_status.lower():
                            review_status_stars = 4 * "★"
                        elif "reviewed by expert panel" in review_status.lower():
                            review_status_stars = 3 * "★"
                        elif "multiple submitters" in review_status.lower():
                            review_status_stars = 2 * "★"
                        elif "single submitter" in review_status.lower():
                            review_status_stars = 1 * "★"

                        # Check if variant already exists
                        variant_obj = Variant.query.filter_by(
                            vcf_description=formatted_variant
                        ).first()
                        # If it doesn't already exist, add it to the database
                        if not variant_obj:
                            variant_obj = Variant(
                                vcf_description=f"GRCh38:{formatted_variant}",
                                hgvsg=annotation_data.get("genomic_hgvs"),
                                hgvsc=annotation_data.get("transcript_hgvs"),
                                gene_symbol=gene_symbol,
                                hgnc_id=annotation_data["genes"][0].get("hgnc_id"),
                                consensus_classification=annotation_data.get(
                                    "clinical_significance", "N/A"
                                ),
                                review_status_stars=review_status_stars,
                                gnomad_af=annotation_data.get("gnomad_total_af"),
                                protein_change=protein_change,
                                molecular_consequences=molecular_consequence,
                                condition=annotation_data.get("trait_name", "N/A"),
                                condition_omim_id=annotation_data.get("trait_omim"),
                                clinvar_url=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{annotation_data.get('variation_id', '')}",
                            )
                            db.session.add(variant_obj)
                            db.session.commit()
                            logger.debug(
                                f"Added new variant to the database: {formatted_variant}"
                            )
                        else:
                            logger.debug(
                                f"Existing variant found in the database: {formatted_variant}"
                            )

                        # Link patient and variant (if link record doesn't already exist)
                        link = PatientVariant.query.filter_by(
                            patient_id=patient_obj.id, variant_id=variant_obj.id
                        ).first()
                        if not link:
                            link = PatientVariant(
                                patient=patient_obj, variant=variant_obj
                            )
                            db.session.add(link)
                            db.session.commit()
                            logger.debug(
                                f"Linked patient {patient_obj.patient_id} with variant {formatted_variant}."
                            )
                        else:
                            logger.debug(
                                f"Patient {patient_obj.patient_id} already linked to variant {formatted_variant}."
                            )

                    except Exception as e:
                        logger.exception(
                            f"Error processing variant {variant_key} for patient {patient_id}: {e}"
                        )

            except Exception as e:
                logger.exception(f"Error processing file {filename}: {e}")

            finally:
                # Clean up temporary file
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug(f"Temporarily saved VCF file now removed: {filepath}")

        logger.info("Rendering variant table page (POST).")

        # Fetch all patient-variant links from DB (so previous uploads persist)
        all_patient_variants = (
            db.session.query(PatientVariant, Patient, Variant)
            .join(Patient, PatientVariant.patient_id == Patient.id)
            .join(Variant, PatientVariant.variant_id == Variant.id)
            .all()
        )

        # Format data for table display
        patient_variants_to_display = []
        for link, patient, variant in all_patient_variants:
            patient_variants_to_display.append(
                {
                    "patient_id": patient.patient_id,
                    "variant": variant.vcf_description,
                    "hgvsg": variant.hgvsg,
                    "hgvsc": variant.hgvsc,
                    "gene_symbol": variant.gene_symbol,
                    "hgnc_id": getattr(variant, "hgnc_id"),
                    "consensus_classification": getattr(
                        variant, "consensus_classification", "N/A"
                    ),
                    "review_status_stars": variant.review_status_stars,
                    "protein_change": getattr(variant, "protein_change", "N/A"),
                    "gnomad_af": getattr(variant, "gnomad_af"),
                    "molecular_consequences": getattr(
                        variant, "molecular_consequences", "N/A"
                    ),
                    "condition": getattr(variant, "condition", "N/A"),
                    "condition_omim_id": getattr(variant, "condition_omim_id", "N/A"),
                    "clinvar_url": variant.clinvar_url,
                    "review_status": getattr(variant, "review_status", "N/A"),
                }
            )

        return render_template(
            "variant_table.html",
            patient_variants=patient_variants_to_display,
            filenames=filenames,
        )

    logger.info("Rendering home page (GET).")
    return render_template("home.html")


if __name__ == "__main__":
    logger.info("Starting Flask application.")
    app.run(debug=True)
