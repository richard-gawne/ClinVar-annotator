import requests
from typing import Dict, Optional, List

class ClinVarSearch:
    def __init__(self):
        self.eutils_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.clinvar_api = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        self.vv_base = "https://rest.variantvalidator.org"

    def variant_validator(self, variant_str: str, genome_build: str = "GRCh38"):
        """
        Use Variant Validator API to get HGVS and gnomAD-compatible ID.
        Returns: (genomic_hgvs, transcript_hgvs, gnomad_id)
        """
        url = (
            f"{self.vv_base}/VariantFormatter/variantformatter/"
            f"{genome_build}/{variant_str}/refseq/mane_select/False?content-type=application/json"
        )

        try:
            res = requests.get(url, timeout=20)
            res.raise_for_status()
            data = res.json()

            inner = data.get(variant_str, {}).get(variant_str, {})
            genomic_hgvs = inner.get("g_hgvs")

            transcript_hgvs = None
            if "hgvs_t_and_p" in inner:
                for tx_data in inner["hgvs_t_and_p"].values():
                    if tx_data.get("t_hgvs"):
                        transcript_hgvs = tx_data["t_hgvs"]
                        break

            vcf_id = inner.get("genomic_variant", {}).get("vcf", {}).get(genome_build)
            gnomad_id = vcf_id.replace("GRCh38:", "").replace(":", "-") if vcf_id else None

            return genomic_hgvs, transcript_hgvs, gnomad_id

        except Exception as e:
            print(f"[Variant Validator Error] {e}")
            return None, None, None

    def search_by_hgvs(self, hgvs: str) -> Optional[Dict]:
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
                return data.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            print(f"Search error: {e}")

        return []

    def fetch_variant_details(self, variant_id: str):
        params = {"db": "clinvar", "id": variant_id, "retmode": "json"}
        try:
            response = requests.get(self.clinvar_api, params=params, timeout=30)
            if response.status_code != 200:
                return None, None

            data = response.json()
            print("\n[RAW JSON RESPONSE]")
            print(data)

            if "result" not in data or variant_id not in data["result"]:
                return None, None

            result = data["result"][variant_id]
            annotations = self._parse_variant_summary(result, variant_id)
            return annotations, result

        except Exception as e:
            print(f"Error fetching variant details: {e}")
            return None, None

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

        # Allele frequencies
        allele_freqs = []
        for var_set in result.get("variation_set", []):
            for freq in var_set.get("allele_freq_set", []):
                allele_freqs.append({
                    "source": freq.get("source", "N/A"),
                    "value": freq.get("value", "N/A"),
                    "minor_allele": freq.get("minor_allele", "N/A")
                })
        annotations["allele_frequencies"] = allele_freqs

        # Genomic location
        for var_set in result.get("variation_set", []):
            for loc in var_set.get("variation_loc", []):
                if loc.get("assembly_name") == "GRCh38":
                    annotations["assembly_name"] = loc.get("assembly_name", "N/A")
                    annotations["chr"] = loc.get("chr", "N/A")
                    annotations["band"] = loc.get("band", "N/A")
                    annotations["start"] = str(loc.get("start", "N/A"))
                    annotations["stop"] = str(loc.get("stop", "N/A"))
                    break

        for gene in result.get("genes", []):
            annotations["genes"].append({
                "symbol": gene.get("symbol", "N/A"),
                "geneid": str(gene.get("geneid", "N/A")),
                "strand": gene.get("strand", "N/A"),
            })

        germ = result.get("germline_classification", {})
        annotations["clinical_significance"] = germ.get("description", "N/A")
        annotations["last_evaluated"] = germ.get("last_evaluated", "N/A")
        annotations["review_status"] = germ.get("review_status", "N/A")

        trait_set = germ.get("trait_set", [])
        if trait_set:
            trait = trait_set[0]
            annotations["trait_name"] = trait.get("trait_name", "N/A")
            for xref in trait.get("trait_xrefs", []):
                if xref.get("db_source") == "OMIM":
                    annotations["trait_omim"] = xref.get("db_id", "N/A")
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
        print(f"Coordinates: {annotations.get('start')}–{annotations.get('stop')}")
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

    print("\nEnter variant in format: chr:pos:ref:alt")
    user_input = input("Variant: ").strip()

    if not user_input:
        print("No input provided.")
        return

    g_hgvs, t_hgvs, gnomad_id = searcher.variant_validator(user_input)

    if not t_hgvs:
        print("Transcript HGVS not found from Variant Validator.")
        return

    print(f"\nTranscript HGVS: {t_hgvs}")
    print(f"gnomAD Format: {gnomad_id or 'Unavailable'}")

    annotations = searcher.search_by_hgvs(t_hgvs)
    if annotations:
        searcher.display_annotations(annotations)
    else:
        print("ClinVar result not found.")

if __name__ == "__main__":
    main()
