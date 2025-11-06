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
