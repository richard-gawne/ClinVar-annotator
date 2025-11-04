from flask import Flask, render_template, request
# from clinvar_anno_app.vcf_tools import vcf_to_clinvar_json  # Commented out for now

app = Flask(__name__)
app.secret_key = "supersecretkey"

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        files = request.files.getlist('vcf_files')
        patient_variants = []

        # Placeholder JSON for testing
        patient_variants_json = {
            "patient_1": [
                {"chrom": "1", "pos": 12345, "ref": "A", "alt": "T", "clinvar": {"significance": "Pathogenic"}},
                {"chrom": "2", "pos": 54321, "ref": "G", "alt": "C", "clinvar": {"significance": "Likely benign"}}
            ],
            "patient_2": [
                {"chrom": "X", "pos": 99999, "ref": "T", "alt": "G", "clinvar": {"significance": "Uncertain"}}
            ]
        }

        for file in files:
            if file.filename.endswith('.vcf'):
                # Normally you would call:
                # patient_variants_json = vcf_to_clinvar_json(file)

                # Flatten JSON to a list for display
                for patient_id, variants in patient_variants_json.items():
                    for var in variants:
                        patient_variants.append({
                            'patient_id': patient_id,
                            'chrom': var['chrom'],
                            'pos': var['pos'],
                            'ref': var['ref'],
                            'alt': var['alt'],
                            'clinvar': var['clinvar']
                        })
        return render_template('variant_table.html', patient_variants=patient_variants)

    return render_template('home.html')
