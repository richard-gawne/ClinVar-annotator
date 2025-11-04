from flask import Flask, render_template, request
# from clinvar_anno_app.vcf_tools import vcf_to_clinvar_json  # commented out for now

app = Flask(__name__)
app.secret_key = "supersecretkey"

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        files = request.files.getlist('vcf_files')
        filenames = [f.filename for f in files]
        patient_variants = []

        # Placeholder example data
        patient_variants_json = {
            "patient_1": [
                {
                    "chrom": "1", "pos": 12345, "ref": "A", "alt": "T",
                    "clinvar": {
                        "consensus_classification": "Pathogenic",
                        "review_status": "criteria provided, multiple submitters, no conflicts",
                        "condition": "Cystic fibrosis"
                    }
                },
                {
                    "chrom": "2", "pos": 54321, "ref": "G", "alt": "C",
                    "clinvar": {
                        "consensus_classification": "Likely benign",
                        "review_status": "criteria provided, single submitter",
                        "condition": "BRCA1-related breast cancer"
                    }
                }
            ],
            "patient_2": [
                {
                    "chrom": "X", "pos": 99999, "ref": "T", "alt": "G",
                    "clinvar": {
                        "consensus_classification": "Uncertain significance",
                        "review_status": "no assertion criteria provided",
                        "condition": "Duchenne muscular dystrophy"
                    }
                }
            ]
        }

        for file in files:
            if file.filename.endswith('.vcf'):
                for patient_id, variants in patient_variants_json.items():
                    for var in variants:
                        formatted_variant = f"{var['chrom']}:{var['pos']}{var['ref']}>{var['alt']}"
                        clinvar = var.get("clinvar", {})
                        patient_variants.append({
                            'patient_id': patient_id,
                            'variant': formatted_variant,
                            'consensus_classification': clinvar.get('consensus_classification', 'N/A'),
                            'review_status': clinvar.get('review_status', 'N/A'),
                            'condition': clinvar.get('condition', 'N/A')
                        })

        return render_template('variant_table.html', 
                               patient_variants=patient_variants,
                               filenames=filenames)

    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
