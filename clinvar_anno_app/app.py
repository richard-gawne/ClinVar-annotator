from flask import Flask, render_template, request
from clinvar_anno_app.models import db, Patient, Variant, PatientVariant
from clinvar_anno_core.main import run_annotation_pipeline
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

# SQLite database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clinvar_annotator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure upload folder for temporary VCF storage
UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

# Create the database if it doesn't exist
with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def home():
    """
    Home page view for the ClinVar Annotator app.

    - Displays the VCF upload form (GET request).
    - Receives one or more uploaded VCF files (POST request).
    - Calls ClinVar annotation functionality to annotate variants.
    - Saves patient and variant info to the database.
    - Renders a template to display annotated variants in a table.
    """
    if request.method == 'POST':
        files = request.files.getlist('vcf_files')
        filenames = [f.filename for f in files]
        
        patient_variants_to_display = []

        # Process each uploaded VCF file
        for file in files:
            if file and file.filename.endswith('.vcf'):
                # Save uploaded file temporarily
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                try:
                    # Run annotation pipeline on the saved file
                    # Extract patient ID from filename (e.g., "patient123.vcf" -> "patient123")
                    patient_id = os.path.splitext(filename)[0]
                    
                    # Get annotations from pipeline
                    annotated_variants = run_annotation_pipeline(filepath, genome_build="GRCh38")
                    
                    if not annotated_variants:
                        print(f"No variants found in {filename}")
                        continue
                    
                    # Check if patient exists, create if not
                    patient_obj = Patient.query.filter_by(patient_id=patient_id).first()
                    if not patient_obj:
                        patient_obj = Patient(patient_id=patient_id)
                        db.session.add(patient_obj)
                        db.session.commit()

                    # Process each annotated variant
                    for variant_key, annotation_data in annotated_variants.items():
                        # Parse variant_key (format: "chr1:7984930:A:C")
                        parts = variant_key.split(':')
                        if len(parts) == 4:
                            chrom, pos, ref, alt = parts
                            formatted_variant = f"GRCh38:{chrom}:{pos}:{ref}:{alt}"
                        else:
                            formatted_variant = f"GRCh38:{variant_key}"

                        # Check if variant already exists
                        variant_obj = Variant.query.filter_by(vcf_description=formatted_variant).first()
                        if not variant_obj:
                            # Extract gene symbol from genes array
                            gene_symbol = None
                            if annotation_data.get('genes') and len(annotation_data['genes']) > 0:
                                gene_symbol = annotation_data['genes'][0].get('symbol')

                            # Map review_status to stars (simplified mapping)
                            review_status = annotation_data.get('review_status', '')
                            review_status_stars = 0*"★"
                            if 'practice guideline' in review_status.lower():
                                review_status_stars = 4*"★"
                            elif 'reviewed by expert panel' in review_status.lower():
                                review_status_stars = 3*"★"
                            elif 'multiple submitters' in review_status.lower():
                                review_status_stars = 2*"★"
                            elif 'single submitter' in review_status.lower():
                                review_status_stars = 1*"★"
                            
                            variant_obj = Variant(
                                vcf_description=formatted_variant,
                                hgvsg=annotation_data.get('genomic_hgvs'),
                                hgvsc=annotation_data.get('transcript_hgvs'),
                                gene_symbol=gene_symbol,
                                review_status_stars=review_status_stars,
                                protein_change=annotation_data.get('protein_change'),
                                molecular_consequences=', '.join(annotation_data.get('molecular_consequences', [])),
                                condition_omim_id=annotation_data.get('trait_omim'),
                                clinvar_url=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{annotation_data.get('variation_id', '')}"
                            )
                            db.session.add(variant_obj)
                            db.session.commit()

                        # Link patient and variant
                        link = PatientVariant.query.filter_by(
                            patient_id=patient_obj.id, 
                            variant_id=variant_obj.id
                        ).first()
                        if not link:
                            link = PatientVariant(patient=patient_obj, variant=variant_obj)
                            db.session.add(link)
                            db.session.commit()

                        # Prepare data for table display
                        patient_variants_to_display.append({
                            "patient_id": patient_obj.patient_id,
                            "variant": formatted_variant,
                            "hgvsg": annotation_data.get('genomic_hgvs'),
                            "hgvsc": annotation_data.get('transcript_hgvs'),
                            "gene_symbol": gene_symbol,
                            "review_status_stars": review_status_stars,
                            "protein_change": annotation_data.get('protein_change'),
                            "molecular_consequences": ', '.join(annotation_data.get('molecular_consequences', [])),
                            "condition_omim_id": annotation_data.get('trait_omim'),
                            "clinvar_url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{annotation_data.get('variation_id', '')}",
                            "consensus_classification": annotation_data.get('clinical_significance', 'N/A'),
                            "review_status": annotation_data.get('review_status', 'N/A'),
                            "condition": annotation_data.get('trait_name', 'N/A')
                        })
                
                finally:
                    # Clean up temporary file
                    if os.path.exists(filepath):
                        os.remove(filepath)

        return render_template('variant_table.html',
                               patient_variants=patient_variants_to_display,
                               filenames=filenames)

    return render_template('home.html')


if __name__ == '__main__':
    app.run(debug=True)