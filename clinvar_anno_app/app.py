"""Flask application for ClinVar Annotator."""

import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request

from clinvar_anno_app.models import db, Patient, Variant, PatientVariant
from clinvar_anno_core.main import run_annotation_pipeline
from clinvar_anno_core.utils.logger import logger

app = Flask(__name__)
app.secret_key = "supersecretkey"

# SQLite database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///clinvar_annotator.db"
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


@app.route("/", methods=["GET", "POST"])
def home():
    """
    Home page view for the ClinVar Annotator app.

    - Displays the VCF upload form (GET request).
    - Receives one or more uploaded VCF files (POST request).
    - Calls ClinVar annotation functionality to annotate variants.
    - Saves patient and variant info to the database.
    - Renders a template to display annotated variants in a table.
    """
    if request.method == "POST":
        files = request.files.getlist("vcf_files")
        filenames = [f.filename for f in files]
        logger.info(
            "Received POST request with %d VCF file(s): %s", len(files), filenames
        )

        patient_variants_to_display = []

        # Process each uploaded VCF file
        for file in files:
            if not file or not file.filename.endswith(".vcf"):
                logger.warning(
                    "Skipped invalid or non-VCF file(s): %s",
                    file.filename if file else "None",
                )
                continue

            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            logger.info("Saved uploaded VCF file temporarily: %s", filepath)

            try:
                # Extract patient ID from filename
                patient_id = os.path.splitext(filename)[0]
                logger.debug("Processed patient ID from filename: %s", patient_id)

                # Run annotation pipeline on the saved file
                annotated_variants = run_annotation_pipeline(
                    filepath, genome_build="GRCh38"
                )
                logger.info(
                    "Annotation pipeline completed for %s with %d variants.",
                    filename,
                    len(annotated_variants),
                )

                if not annotated_variants:
                    logger.warning("No variants in %s.", filename)
                    continue

                # Check if patient exists in the database, and if not, add a new record
                patient_obj = Patient.query.filter_by(patient_id=patient_id).first()
                if not patient_obj:
                    patient_obj = Patient(patient_id=patient_id)
                    db.session.add(patient_obj)
                    db.session.commit()
                    logger.debug(
                        "Added new patient record to the database: %s", patient_id
                    )
                else:
                    logger.debug(
                        "Existing patient record found in the database: %s", patient_id
                    )

                # Loop through variants and their annotations
                for variant_key, annotation_data in annotated_variants.items():
                    try:
                        # Parse variant info into VCF description format
                        parts = variant_key.split(":")
                        chrom, pos, ref, alt = parts
                        formatted_variant = f"GRCh38:{chrom}:{pos}:{ref}:{alt}"

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
                        review_status_stars = 0 * "★"
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
                                vcf_description=formatted_variant,
                                hgvsg=annotation_data.get("genomic_hgvs"),
                                hgvsc=annotation_data.get("transcript_hgvs"),
                                gene_symbol=gene_symbol,
                                review_status_stars=review_status_stars,
                                protein_change=protein_change,
                                molecular_consequences=molecular_consequence,
                                condition_omim_id=annotation_data.get("trait_omim"),
                                clinvar_url=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{annotation_data.get('variation_id', '')}",
                            )
                            db.session.add(variant_obj)
                            db.session.commit()
                            logger.debug(
                                "Added new variant to the database: %s",
                                formatted_variant,
                            )
                        else:
                            logger.debug(
                                "Existing variant found in the database: %s",
                                formatted_variant,
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
                                "Linked patient %s with variant %s.",
                                patient_obj.patient_id,
                                formatted_variant,
                            )
                        else:
                            logger.debug(
                                "Patient %s already linked to variant %s.",
                                patient_obj.patient_id,
                                formatted_variant,
                            )

                        # Prepare data for display in the table
                        patient_variants_to_display.append(
                            {
                                "patient_id": patient_obj.patient_id,
                                "variant": formatted_variant,
                                "hgvsg": annotation_data.get("genomic_hgvs"),
                                "hgvsc": annotation_data.get("transcript_hgvs"),
                                "gene_symbol": gene_symbol,
                                "review_status_stars": review_status_stars,
                                "protein_change": protein_change,
                                "molecular_consequences": molecular_consequence,
                                "condition_omim_id": annotation_data.get("trait_omim"),
                                "clinvar_url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{annotation_data.get('variation_id', '')}",
                                "consensus_classification": annotation_data.get(
                                    "clinical_significance", "N/A"
                                ),
                                "review_status": annotation_data.get(
                                    "review_status", "N/A"
                                ),
                                "condition": annotation_data.get("trait_name", "N/A"),
                            }
                        )
                    except Exception as e:
                        logger.exception(
                            "Error processing variant %s for patient %s: %s",
                            variant_key,
                            patient_id,
                            e,
                        )

            # Raise exception if the file could not be processed
            except Exception as e:
                logger.exception("Error processing file %s: %s", filename, e)

            # Clean up temporary file
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug("Temporarily saved VCF file now removed: %s", filepath)

        logger.info("Rendering variant table page (POST).")
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
