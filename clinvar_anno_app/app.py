from flask import Flask, render_template, request
from clinvar_anno_app.models import db, Patient, Variant, PatientVariant

app = Flask(__name__)
app.secret_key = "supersecretkey"

# SQLite database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clinvar_annotator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

        # --- Temporary test JSON for now ---
        patient_variants_json = {
            "patient_1": [
                {
                    "chrom": "1", "pos": 12345, "ref": "A", "alt": "T",
                    "hgvsg": "NC_000001.11:g.12345A>T",
                    "hgvsc": "NM_000000.1:c.123A>T",
                    "gene_symbol": "GENE1",
                    "review_status_stars": "★★★",
                    "protein_change": "A206S",
                    "molecular_consequences": "missense_variant",
                    "condition_omim_id": "123456",
                    "clinvar_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
                    "clinvar": {
                        "consensus_classification": "Pathogenic",
                        "review_status": "criteria provided, multiple submitters, no conflicts",
                        "condition": "Cystic fibrosis"
                    }
                }
            ],
            "patient_2": [
                {
                    "chrom": "X", "pos": 99999, "ref": "T", "alt": "G",
                    "hgvsg": "NC_000023.11:g.99999T>G",
                    "hgvsc": "NM_000000.2:c.999T>G",
                    "gene_symbol": "GENE2",
                    "review_status_stars": "★",
                    "protein_change": "B211K",
                    "molecular_consequences": "missense_variant",
                    "condition_omim_id": "654321",
                    "clinvar_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/2",
                    "clinvar": {
                        "consensus_classification": "Uncertain significance",
                        "review_status": "no assertion criteria provided",
                        "condition": "Duchenne muscular dystrophy"
                    }
                }
            ]
        }

        # Insert test data into the database
        for file in files:
            if file.filename.endswith('.vcf'):
                for patient_id, variants in patient_variants_json.items():
                    # Check if patient exists
                    patient_obj = Patient.query.filter_by(patient_id=patient_id).first()
                    if not patient_obj:
                        patient_obj = Patient(patient_id=patient_id)
                        db.session.add(patient_obj)
                        db.session.commit()

                    for var in variants:
                        formatted_variant = f"GRCh38:{var['chrom']}:{var['pos']}:{var['ref']}:{var['alt']}"

                        # Check if variant already exists
                        variant_obj = Variant.query.filter_by(vcf_description=formatted_variant).first()
                        if not variant_obj:
                            variant_obj = Variant(
                                vcf_description=formatted_variant,
                                hgvsg=var.get('hgvsg'),
                                hgvsc=var.get('hgvsc'),
                                gene_symbol=var.get('gene_symbol'),
                                review_status_stars=var.get('review_status_stars'),
                                protein_change=var.get('protien_change'),
                                molecular_consequences=var.get('molecular_consequences'),
                                condition_omim_id=var.get('condition_omim_id'),
                                clinvar_url=var.get('clinvar_url')
                            )
                            db.session.add(variant_obj)
                            db.session.commit()

                        # Link patient and variant
                        link = PatientVariant.query.filter_by(patient_id=patient_obj.id, variant_id=variant_obj.id).first()
                        if not link:
                            link = PatientVariant(patient=patient_obj, variant=variant_obj)
                            db.session.add(link)
                            db.session.commit()

                        # Prepare data for table display
                        patient_variants_to_display.append({
                            "patient_id": patient_obj.patient_id,
                            "variant": formatted_variant,
                            "hgvsg": var.get('hgvsg'),
                            "hgvsc": var.get('hgvsc'),
                            "gene_symbol": var.get('gene_symbol'),
                            "review_status_stars": var.get('review_status_stars'),
                            "protein_change": var.get('protien_change'),
                            "molecular_consequences": var.get('molecular_consequences'),
                            "condition_omim_id": var.get('condition_omim_id'),
                            "clinvar_url": var.get('clinvar_url'),
                            "consensus_classification": var['clinvar'].get('consensus_classification', 'N/A'),
                            "review_status": var['clinvar'].get('review_status', 'N/A'),
                            "condition": var['clinvar'].get('condition', 'N/A')
                        })

        return render_template('variant_table.html',
                               patient_variants=patient_variants_to_display,
                               filenames=filenames)

    return render_template('home.html')


if __name__ == '__main__':
    app.run(debug=True)

