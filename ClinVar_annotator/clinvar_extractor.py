#!/usr/bin/env python3
"""
ClinVar Variant Annotation Search Tool
Searches ClinVar using HGVS notation or genomic coordinates
"""

import requests
import json
import sys
import re
from typing import Dict, Optional, List
import time

class ClinVarSearch:
    def __init__(self):
        self.eutils_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.clinvar_api = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        self.email = "your_email@example.com"  # Replace with your email
        
    def search_by_hgvs(self, hgvs: str) -> Optional[Dict]:
        """Search ClinVar by HGVS notation"""
        print(f"Searching for HGVS: {hgvs}")
        
        # Extract the variant part without the transcript
        # Try to match common HGVS patterns
        variant_searches = []
        
        # Full HGVS
        variant_searches.append(f'"{hgvs}"')
        
        # Try without version number
        if ':' in hgvs:
            parts = hgvs.split(':')
            transcript = parts[0].split('.')[0]  # Remove version
            variant = parts[1] if len(parts) > 1 else ''
            variant_searches.append(f'{transcript}:{variant}')
            variant_searches.append(f'"{transcript}:{variant}"')
        
        # Search ClinVar
        for search_term in variant_searches:
            variant_ids = self._search_clinvar(search_term)
            if variant_ids:
                print(f"Found {len(variant_ids)} variant(s)")
                # Fetch all and find best match
                for vid in variant_ids[:5]:  # Check first 5
                    annotations = self.fetch_variant_details(vid)
                    if annotations and annotations.get('variation_name') != 'N/A':
                        return annotations
        
        print("No results found in ClinVar for HGVS notation")
        return None
    
    def search_by_coordinates(self, chrom: str, pos: int, ref: str, alt: str) -> Optional[Dict]:
        """Search ClinVar by genomic coordinates"""
        print(f"Searching for variant: {chrom}:{pos} {ref}>{alt}")
        
        chrom_num = chrom.replace("chr", "")
        search_term = f"{chrom_num}[Chromosome] AND {pos}[Base Position]"
        
        variant_ids = self._search_clinvar(search_term, retmax=20)
        
        if not variant_ids:
            print("No results found in ClinVar")
            return None
        
        print(f"Found {len(variant_ids)} variant(s) at this position")
        
        # Try to find exact match
        for vid in variant_ids:
            annotations = self.fetch_variant_details(vid)
            if annotations and annotations.get('variation_name') != 'N/A':
                # Check if ref/alt match
                genomic_locs = annotations.get('genomic_locations', [])
                for loc in genomic_locs:
                    if (loc.get('reference_allele') == ref and 
                        loc.get('alternate_allele') == alt):
                        return annotations
        
        # If no exact match, return first valid result
        for vid in variant_ids:
            annotations = self.fetch_variant_details(vid)
            if annotations and annotations.get('variation_name') != 'N/A':
                return annotations
        
        return None
    
    def _search_clinvar(self, search_term: str, retmax: int = 10) -> List[str]:
        """Search ClinVar and return variant IDs"""
        search_url = f"{self.eutils_base}/esearch.fcgi"
        params = {
            "db": "clinvar",
            "term": search_term,
            "retmode": "json",
            "email": self.email,
            "retmax": retmax
        }
        
        try:
            response = requests.get(search_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if "esearchresult" in data:
                    return data["esearchresult"].get("idlist", [])
        except Exception as e:
            print(f"Search error: {e}")
        
        return []
    
    def fetch_variant_details(self, variant_id: str) -> Dict:
        """Fetch comprehensive variant details using esummary"""
        print(f"Fetching annotations for ClinVar ID: {variant_id}")
        
        params = {
            "db": "clinvar",
            "id": variant_id,
            "retmode": "json",
            "email": self.email
        }
        
        time.sleep(0.34)  # Rate limiting
        
        try:
            response = requests.get(self.clinvar_api, params=params, timeout=30)
            if response.status_code != 200:
                return {}
            
            data = response.json()
            
            if "result" not in data or variant_id not in data["result"]:
                return {}
            
            result = data["result"][variant_id]
            
            # Parse the comprehensive data
            annotations = self._parse_variant_summary(result, variant_id)
            
            return annotations
            
        except Exception as e:
            print(f"Error fetching variant details: {e}")
            return {}
    
    def _parse_variant_summary(self, result: Dict, variant_id: str) -> Dict:
        """Parse ClinVar esummary result"""
        
        
        
        annotations = {
            "clinvar_id": variant_id,
            "accession": result.get("accession", result.get("variant_vcv", "N/A")),
            "variation_id": str(result.get("variation_id", result.get("var_id", variant_id))),
            "variation_name": result.get("title", "N/A"),
            "variation_type": result.get("variation_type", "N/A"),
            "protein_change": result.get("protein_change", "N/A"),
            "genes": [],
            "clinical_significance": "N/A",
            "review_status": "N/A",
            "last_evaluated": "N/A",
            "conditions": [],
            "molecular_consequences": [],
            "hgvs_expressions": [],
            "genomic_locations": [],
            "allele_id": str(result.get("allele_id", result.get("alleleid", "N/A"))),
            "canonical_spdi": result.get("canonical_spdi", "N/A"),
            "germline_classification": result.get("germline_classification", {}),
            "somatic_classification": result.get("somatic_classification", {}),
            "oncogenicity_classification": result.get("oncogenicity_classification", {})
        }
        
        # Get variation type from variation_set
        if "variation_set" in result and isinstance(result["variation_set"], list):
            if len(result["variation_set"]) > 0:
                var_set = result["variation_set"][0]
                annotations["variation_type"] = var_set.get("variation_type", "N/A")
        
        # Get genes
        if "genes" in result and isinstance(result["genes"], list):
            for gene in result["genes"]:
                gene_info = {
                    "symbol": gene.get("symbol", "N/A"),
                    "id": str(gene.get("geneid", gene.get("gene_id", "N/A"))),
                    "relationship_type": gene.get("relationship_type", "N/A")
                }
                annotations["genes"].append(gene_info)
        
        # Get clinical significance - try multiple possible structures
        if "clinical_significance" in result:
            clin_sig = result["clinical_significance"]
            if isinstance(clin_sig, dict):
                annotations["clinical_significance"] = clin_sig.get("description", "N/A")
                annotations["review_status"] = clin_sig.get("review_status", "N/A")
                annotations["last_evaluated"] = clin_sig.get("last_evaluated", "N/A")
        
        # Try germline classification if clinical_significance is empty
        if annotations["clinical_significance"] == "N/A" and "germline_classification" in result:
            germ_class = result["germline_classification"]
            if isinstance(germ_class, dict):
                annotations["clinical_significance"] = germ_class.get("description", "N/A")
                annotations["review_status"] = germ_class.get("review_status", "N/A")
                annotations["last_evaluated"] = germ_class.get("date_last_evaluated", "N/A")
        
        # Get conditions
        if "trait_set" in result and isinstance(result["trait_set"], list):
            for trait in result["trait_set"]:
                if isinstance(trait, dict):
                    trait_name = trait.get("trait_name", "N/A")
                    if trait_name != "N/A":
                        condition_info = {
                            "name": trait_name,
                            "medgen_id": trait.get("medgen_id", "N/A"),
                            "trait_type": trait.get("trait_type", "N/A")
                        }
                        annotations["conditions"].append(condition_info)
        
        # Get genomic locations from variation_set
        if "variation_set" in result and isinstance(result["variation_set"], list):
            for var_set in result["variation_set"]:
                if "variation_loc" in var_set and isinstance(var_set["variation_loc"], list):
                    for loc in var_set["variation_loc"]:
                        if isinstance(loc, dict):
                            loc_info = {
                                "assembly": loc.get("assembly_name", "N/A"),
                                "chr": loc.get("chr", "N/A"),
                                "start": str(loc.get("start", "N/A")),
                                "stop": str(loc.get("stop", "N/A")),
                                "accession": loc.get("accession", "N/A"),
                                "reference_allele": loc.get("ref", loc.get("reference_allele", "N/A")),
                                "alternate_allele": loc.get("alt", loc.get("alternate_allele", "N/A"))
                            }
                            annotations["genomic_locations"].append(loc_info)
        
        # Get molecular consequences from supporting_submissions
        if "supporting_submissions" in result and isinstance(result["supporting_submissions"], dict):
            scv_list = result["supporting_submissions"].get("scv", [])
            if isinstance(scv_list, list):
                consequences_seen = set()
                for scv in scv_list:
                    if isinstance(scv, dict) and "molecular_consequence_list" in scv:
                        mol_cons = scv["molecular_consequence_list"]
                        if isinstance(mol_cons, list):
                            for cons in mol_cons:
                                if isinstance(cons, dict):
                                    cons_type = cons.get("type", "N/A")
                                    if cons_type != "N/A" and cons_type not in consequences_seen:
                                        consequences_seen.add(cons_type)
                                        annotations["molecular_consequences"].append({
                                            "type": cons_type,
                                            "soid": cons.get("soid", "N/A")
                                        })
        
        # Debug print the full result to see structure
        if annotations["clinical_significance"] == "N/A":
            print(f"\nDEBUG - Full result structure sample:")
            debug_keys = ["clinical_significance", "germline_classification", "variation_id", 
                         "allele_id", "var_id", "alleleid", "variation_set"]
            for key in debug_keys:
                if key in result:
                    print(f"  {key}: {result[key]}")
        
        return annotations
    
    def display_annotations(self, annotations: Dict):
        """Display annotations in a readable format"""
        if not annotations or annotations.get('variation_name') == 'N/A':
            print("\nNo annotations to display")
            return
            
        print("\n" + "="*80)
        print("CLINVAR VARIANT ANNOTATIONS")
        print("="*80)
        
        print(f"\n[IDENTIFIERS]")
        print(f"ClinVar ID: {annotations['clinvar_id']}")
        print(f"Accession: {annotations['accession']}")
        print(f"Variation ID: {annotations['variation_id']}")
        print(f"Allele ID: {annotations['allele_id']}")
        
        print(f"\n[VARIANT]")
        print(f"Name: {annotations['variation_name']}")
        print(f"Type: {annotations['variation_type']}")
        if annotations['protein_change'] != "N/A":
            print(f"Protein Change: {annotations['protein_change']}")
        if annotations['canonical_spdi'] != "N/A":
            print(f"Canonical SPDI: {annotations['canonical_spdi']}")
        
        if annotations['genomic_locations']:
            print(f"\n[GENOMIC LOCATIONS]")
            for loc in annotations['genomic_locations']:
                print(f"  Assembly: {loc['assembly']}")
                print(f"  Chromosome: {loc['chr']}")
                print(f"  Position: {loc['start']}-{loc['stop']}")
                print(f"  Accession: {loc['accession']}")
                print(f"  Reference: {loc['reference_allele']} → Alternate: {loc['alternate_allele']}")
                print()
        
        print(f"[CLINICAL SIGNIFICANCE]")
        print(f"  {annotations['clinical_significance']}")
        if annotations['last_evaluated'] != "N/A":
            print(f"  Last Evaluated: {annotations['last_evaluated']}")
        
        print(f"\n[REVIEW STATUS]")
        print(f"  {annotations['review_status']}")
        
        if annotations['genes']:
            print(f"\n[GENES]")
            for gene in annotations['genes']:
                rel = f" ({gene['relationship_type']})" if gene['relationship_type'] != "N/A" else ""
                print(f"  {gene['symbol']} (Gene ID: {gene['id']}){rel}")
        
        if annotations['molecular_consequences']:
            print(f"\n[MOLECULAR CONSEQUENCES]")
            for cons in annotations['molecular_consequences']:
                so_info = f" (SO:{cons['soid']})" if cons['soid'] != "N/A" else ""
                print(f"  - {cons['type']}{so_info}")
        
        if annotations['conditions']:
            print(f"\n[CONDITIONS/PHENOTYPES]")
            for cond in annotations['conditions']:
                medgen = f" (MedGen: {cond.get('medgen_id')})" if cond.get('medgen_id') != "N/A" else ""
                print(f"  - {cond['name']}{medgen}")
        
        print(f"\n[LINKS]")
        print(f"ClinVar: https://www.ncbi.nlm.nih.gov/clinvar/variation/{annotations['variation_id']}/")
        if annotations['genes']:
            gene_id = annotations['genes'][0]['id']
            if gene_id != "N/A":
                print(f"Gene: https://www.ncbi.nlm.nih.gov/gene/{gene_id}")
        
        print("="*80)

def parse_coordinate_input(coord_str: str) -> Optional[tuple]:
    """Parse genomic coordinate string"""
    # Format: chr7:117559590 G>A
    match = re.match(r'(chr)?(\d+|X|Y|MT):(\d+)\s+([ACGT]+)>([ACGT]+)', coord_str, re.IGNORECASE)
    if match:
        chrom = f"chr{match.group(2)}"
        pos = int(match.group(3))
        ref = match.group(4).upper()
        alt = match.group(5).upper()
        return chrom, pos, ref, alt
    
    # Format: 7:117559590:G:A
    match = re.match(r'(chr)?(\d+|X|Y|MT):(\d+):([ACGT]+):([ACGT]+)', coord_str, re.IGNORECASE)
    if match:
        chrom = f"chr{match.group(2)}"
        pos = int(match.group(3))
        ref = match.group(4).upper()
        alt = match.group(5).upper()
        return chrom, pos, ref, alt
    
    return None

def main():
    print("ClinVar Variant Annotation Search Tool")
    print("="*80)
    
    searcher = ClinVarSearch()
    
    # Get user input
    print("\nEnter variant information:")
    print("  Format 1 (HGVS): NM_000277.1:c.1521_1523delCTT")
    print("  Format 2 (HGVS): NM_007294.4:c.68_69delAG")
    print("  Format 3 (Coordinates): chr7:117559590 G>A")
    print("  Format 4 (Coordinates): 7:117559590:G:A")
    
    variant_input = input("\nVariant: ").strip()
    
    if not variant_input:
        print("Error: No input provided")
        return
    
    # Try to parse as coordinates first
    coord_data = parse_coordinate_input(variant_input)
    
    if coord_data:
        chrom, pos, ref, alt = coord_data
        annotations = searcher.search_by_coordinates(chrom, pos, ref, alt)
    else:
        # Assume HGVS notation
        annotations = searcher.search_by_hgvs(variant_input)
    
    if annotations:
        searcher.display_annotations(annotations)
        
        # Option to save as JSON
        save = input("\nSave annotations to JSON file? (y/n): ").strip().lower()
        if save == 'y':
            filename = f"clinvar_{annotations['variation_id']}.json"
            with open(filename, 'w') as f:
                json.dump(annotations, f, indent=2)
            print(f"Annotations saved to {filename}")
    else:
        print("\nNo variant found or unable to retrieve annotations.")

if __name__ == "__main__":
    main()