from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Patient(db.Model):
    """Patient identifiers"""
    __tablename__ = "patient"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String, unique=True, nullable=False)

    variants = db.relationship("PatientVariant", back_populates="patient", cascade="all, delete-orphan")


class Variant(db.Model):
    """Variant descriptions with ClinVar annotations"""
    __tablename__ = "variant"
    id = db.Column(db.Integer, primary_key=True)
    vcf_description = db.Column(db.String, nullable=False)
    hgvsg = db.Column(db.String)
    hgvsc = db.Column(db.String)
    gene_symbol = db.Column(db.String)
    review_status_stars = db.Column(db.String)
    protein_change = db.Column(db.String)
    molecular_consequences = db.Column(db.String)
    condition_omim_id = db.Column(db.String)
    clinvar_url = db.Column(db.String)

    patient_links = db.relationship("PatientVariant", back_populates="variant", cascade="all, delete-orphan")


class PatientVariant(db.Model):
    
    __tablename__ = "patient_variant"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey("variant.id"), nullable=False)

    patient = db.relationship("Patient", back_populates="variants")
    variant = db.relationship("Variant", back_populates="patient_links")

# class Patient(db.Model):
#     """Patient identifiers"""
#     id = db.Column(db.Integer, primary_key=True)
#     patient_id = db.Column(db.String, unique=True, nullable=False)  # One row per unique patient

#     variants = db.relationship('PatientVariant', back_populates='patient', cascade='all, delete-orphan')


# class Variant(db.Model):
#     """Variant descriptions with ClinVar annotations"""
#     id = db.Column(db.Integer, primary_key=True)

#     # Variant description (one row per unique variant)
#     chrom = db.Column(db.String, nullable=False)
#     pos = db.Column(db.Integer, nullable=False)
#     ref = db.Column(db.String, nullable=False)
#     alt = db.Column(db.String, nullable=False)
#     gene_symbol = db.Column(db.String)
#     hgvs_g = db.Column(db.String)  # genomic HGVS format
#     hgvs_c = db.Column(db.String)  # cDNA HGVS format

#     # Metadata from ClinVar
#     review_status_stars = db.Column(db.Integer)  # 1–4 stars
#     allele_frequency = db.Column(db.Float)
#     condition_omim_id = db.Column(db.String)
#     clinvar_link = db.Column(db.String)  # hyperlink to ClinVar record

#     patient_variants = db.relationship('PatientVariant', back_populates='variant', cascade='all, delete-orphan')

#     # Avoid duplicate variants
#     __table_args__ = (
#         db.UniqueConstraint('chrom', 'pos', 'ref', 'alt', name='unique_variant'),
#     )


# class PatientVariant(db.Model):
#     """Linking table connecting patients and their variant(s)"""
#     id = db.Column(db.Integer, primary_key=True)
#     patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
#     variant_id = db.Column(db.Integer, db.ForeignKey('variant.id'), nullable=False)
