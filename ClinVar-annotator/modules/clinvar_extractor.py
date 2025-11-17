import requests
from typing import Dict, Optional, List
import json

class ClinVarSearch:
    """
    A class to search and retrieve variant information from ClinVar.

    This class uses NCBIs E-utilities API to:
    - Search ClinVar with genomic HGVS
    - Retrieve variant summaries and details (via esummary)
    - Normalise the response into a python dictionary 
    - Log formatted annotations to the console

    Attributes:
    - eutils_base: Base URL for NCBI
    - clinvar_api: Esummary endpoint for ClinVar variant details
    """

    def __init__(self):
        """
        Initialise the ClinVarSearch object with default API endpoints
        """
        self.eutils_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.clinvar_api = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        self.gnomad_api = "https://gnomad.broadinstitute.org/api"
        
    def search_by_hgvs(self, hgvs: str) -> Optional[Dict]:
        """
        Search ClinVar using a given HGVS expression and return parsed annotations.

        Args: 
        HGVS (str): Variant string in HGVS nomenclature

        Returns:
        Dict: Parsed annotation dictionary if found, otherwise None.
        """

        search_terms = [f'"{hgvs}"', hgvs]
        variant_ids = []

        for term in search_terms:
            ids = self._search_clinvar(term)
            if ids:
                variant_ids = ids
                break 

        if not variant_ids:
            print(f"No results found in ClinVar for HGVS: {hgvs}")
            return None

        vid = variant_ids[0]
        annotations, _ = self.fetch_variant_details(vid)

    
        if annotations and annotations.get("variation_name") != "N/A":
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
    

    def fetch_variant_details(self, variant_id: str):
        """Fetch comprehensive variant details using esummary"""
        params = {"db": "clinvar", "id": variant_id, "retmode": "json"}
        try:
            response = requests.get(self.clinvar_api, params=params, timeout=30)
            if response.status_code != 200:
                return None, None

            data = response.json()
            if "result" not in data or variant_id not in data["result"]:
                return None, None

            result = data["result"][variant_id]
            # Pass safely to parser (handles missing keys)
            annotations = self._parse_variant_summary(result, variant_id)
            return annotations, result

        except Exception as e:
            print(f"Error fetching variant details: {e}")
            return None, None


    def get_hgnc_id(self, ncbi_gene_id: str) -> Optional[str]:
        """
        Get HGNC ID using NCBI Gene ID from HGNC REST API.
        """
        url = f"https://rest.genenames.org/fetch/entrez_id/{ncbi_gene_id}"
        headers = {"Accept": "application/json"}

        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            docs = data.get("response", {}).get("docs", [])
            if docs:
                return docs[0].get("hgnc_id")
        except Exception as e:
            print(f"[HGNC API Error] {e}")
        
        return None



    def _parse_variant_summary(self, result: Dict, variant_id: str) -> Dict:
        """Parse and normalize ClinVar variant summary safely"""
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

        # ---- Extract allele frequencies from variation_set ----
        allele_freqs = []
        for var_set in result.get("variation_set", []):
            freq_list = var_set.get("allele_freq_set", [])
            for freq in freq_list:
                allele_freqs.append({
                    "source": freq.get("source", "N/A"),
                    "value": freq.get("value", "N/A"),
                    "minor_allele": freq.get("minor_allele", "N/A")
                })
        annotations["allele_frequencies"] = allele_freqs


        # ---- Extract genomic location ----
        for var_set in result.get("variation_set", []):
            for loc in var_set.get("variation_loc", []):
                if loc.get("assembly_name") == "GRCh38":
                    annotations["assembly_name"] = loc.get("assembly_name", "N/A")
                    annotations["chr"] = loc.get("chr", "N/A")
                    annotations["band"] = loc.get("band", "N/A")
                    annotations["start"] = str(loc.get("start", "N/A"))
                    annotations["stop"] = str(loc.get("stop", "N/A"))
                    break


        # ---- Extract germline classification ----
        germ = result.get("germline_classification", {})
        annotations["clinical_significance"] = germ.get("description", "N/A")
        annotations["last_evaluated"] = germ.get("last_evaluated", "N/A")
        annotations["review_status"] = germ.get("review_status", "N/A")

        # ---- Extract trait and OMIM data ----
        trait_set = germ.get("trait_set", [])
        if trait_set:
            trait = trait_set[0]
            annotations["trait_name"] = trait.get("trait_name", "N/A")
            for xref in trait.get("trait_xrefs", []):
                if xref.get("db_source") == "OMIM":
                    annotations["trait_omim"] = xref.get("db_id", "N/A")
                    break

        

        for gene in result.get("genes", []):
            entrez_id = gene.get("geneid", "N/A")
            hgnc_id = self.get_hgnc_id(entrez_id) if entrez_id != "N/A" else "N/A"

            annotations["genes"].append({
                "symbol": gene.get("symbol", "N/A"),
                "geneid": str(entrez_id),
                "strand": gene.get("strand", "N/A"),
                "hgnc_id": hgnc_id or "N/A"
            })

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
            print(f"  - {gene['symbol']} (GeneID: {gene['geneid']}, Strand: {gene['strand']}, HGNC ID: {gene['hgnc_id']})")

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
        annotations = result
        searcher.display_annotations(annotations)
        return annotations
    else:
        print("\nNo variant found or unable to retrieve annotations.")

    

if __name__ == "__main__":
    main()