
import requests
from typing import Dict, Optional, List

class ClinVarSearch:
    def __init__(self):
        self.eutils_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.clinvar_api = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        
    def search_by_hgvs(self, hgvs: str) -> Optional[Dict]:
        """
        Search ClinVar for an exact HGVS variant (e.g., NM_003690.5:c.854A>G)
        and return parsed annotation data.
        """

        variant_ids = self._search_clinvar(f'"{hgvs}"')
        if not variant_ids:
            print(f"No results found in ClinVar for HGVS: {hgvs}")
            return None
        vid = variant_ids[0]
        annotations, _ = self.fetch_variant_details(vid)
        if annotations and annotations.get('variation_name') != 'N/A':
            return annotations
        print(f"No valid ClinVar summary for HGVS: {hgvs}")
        return None


    def _search_clinvar(self, search_term: str, retmax: int = 10) -> List[str]:
        """Search ClinVar and return variant IDs"""
        search_url = f"{self.eutils_base}/esearch.fcgi"
        params = {
            "db": "clinvar",
            "term": search_term,
            "retmode": "json",
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
        params = {
            "db": "clinvar",
            "id": variant_id,
            "retmode": "json",}
        try:
            response = requests.get(self.clinvar_api, params=params, timeout=30)
            if response.status_code != 200:
                return {}
            data = response.json()
            if "result" not in data or variant_id not in data["result"]:
                return {}
            result = data["result"][variant_id]
            annotations = self._parse_variant_summary(result, variant_id)  # Parse the comprehensive data
            
            return annotations, result
            
        except Exception as e:
            print(f"Error fetching variant details: {e}")
            return {}
    

    def _parse_variant_summary(self, result: Dict, variant_id: str) -> Dict:
        annotations = {
        "uid": result.get("uid", variant_id),
        "obj_type": result.get("obj_type", "N/A"),
        "variation_name": result.get("title", "N/A"),
        "protein_change": result.get("protein_change", "N/A"),
        "molecular_consequences": result.get("molecular_consequence_list", []),
        "genes": [],
        "assembly_name": "N/A",
        "chr": "N/A",
        "band": "N/A",
        "start": "N/A",
        "stop": "N/A",
        "clinical_significance": "N/A",
        "last_evaluated": "N/A",
        "review_status": "N/A",
        "trait_name": "N/A",
        "trait_omim": "N/A",
        "variation_id": str(result.get("variation_id", variant_id)),
        }

        # Genomic location (GRCh38)
        for var_set in result.get("variation_set", []):
            for loc in var_set.get("variation_loc", []):
                if loc.get("assembly_name") == "GRCh38":
                    annotations["assembly_name"] = loc.get("assembly_name", "N/A")
                    annotations["chr"] = loc.get("chr", "N/A")
                    annotations["band"] = loc.get("band", "N/A")
                    annotations["start"] = str(loc.get("start", "N/A"))
                    annotations["stop"] = str(loc.get("stop", "N/A"))
                    break

        # Genes
        for gene in result.get("genes", []):
            annotations["genes"].append({
                "symbol": gene.get("symbol", "N/A"),
                "geneid": str(gene.get("geneid", "N/A")),
                "strand": gene.get("strand", "N/A"),
            })

        # Germline classification
        germ = result.get("germline_classification", {})
        annotations["clinical_significance"] = germ.get("description", "N/A")
        annotations["last_evaluated"] = germ.get("last_evaluated", "N/A")
        annotations["review_status"] = germ.get("review_status", "N/A")

        # Trait name and OMIM ID
        for trait in germ.get("trait_set", []):
            annotations["trait_name"] = trait.get("trait_name", "N/A")
            for xref in trait.get("trait_xrefs", []):
                if xref.get("db_source") == "OMIM":
                    annotations["trait_omim"] = xref.get("db_id", "N/A")
                    break
            break

        return annotations

    
    def display_annotations(self, annotations: Dict):
        print("\n[CLINVAR VARIANT SUMMARY]")
        
        print(f"UID: {annotations['uid']}")
        print(f"Type: {annotations['obj_type']}")
        print(f"Variation: {annotations['variation_name']}")
        print(f"Protein Change: {annotations['protein_change']}")
        
        print(f"\n[GENOMIC LOCATION]")
        print(f"Assembly: {annotations['assembly_name']}")
        print(f"Chromosome: {annotations['chr']}")
        print(f"Band: {annotations['band']}")
        print(f"Coordinates: {annotations.get('start', 'N/A')}–{annotations.get('stop', 'N/A')}")


        print(f"\n[CLASSIFICATION]")
        print(f"Clinical Significance: {annotations['clinical_significance']}")
        print(f"Review Status: {annotations['review_status']}")
        print(f"Last Evaluated: {annotations['last_evaluated']}")

        print(f"\n[CONDITION]")
        print(f"Trait: {annotations['trait_name']}")
        print(f"OMIM ID: {annotations['trait_omim']}")

        print(f"\n[GENES]")
        for gene in annotations['genes']:
            print(f"  - {gene['symbol']} (GeneID: {gene['geneid']}, Strand: {gene['strand']})")

        print(f"\n[MOLECULAR CONSEQUENCES]")
        for consequence in annotations["molecular_consequences"]:
            print(f"  - {consequence}")

        print(f"\n[LINKS]")
        print(f"ClinVar: https://www.ncbi.nlm.nih.gov/clinvar/variation/{annotations['variation_id']}/")
        if annotations['genes']:
            print(f"Gene: https://www.ncbi.nlm.nih.gov/gene/{annotations['genes'][0]['geneid']}")

def main():
    searcher = ClinVarSearch()
    
    print("\nEnter variant information:")
    variant_input = input("\nVariant: ").strip()
    
    if not variant_input:
        print("Error: No input provided")
        return

    result = searcher.search_by_hgvs(variant_input)

    if result:
        annotations = result  # We ignore raw_json now
        searcher.display_annotations(annotations)
        return annotations
    else:
        print("\nNo variant found or unable to retrieve annotations.")

    

if __name__ == "__main__":
    main()