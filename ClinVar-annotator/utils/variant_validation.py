import requests
import sys

def get_hgvs(variant, build="GRCh38"):
    """
    Convert genomic variant like 19:41968837:C:G to HGVS using VariantFormatter API.
    """
    url = (
        f"https://rest.variantvalidator.org/VariantFormatter/variantformatter/"
        f"{build}/{variant}/refseq/mane/True?content-type=application/json"
    )

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()

        # Data structure: data[variant][variant]['g_hgvs']
        inner = data.get(variant, {}).get(variant, {})
        g_hgvs = inner.get("g_hgvs")

        if g_hgvs:
            print({g_hgvs})
        else:
            import json
            print("Full response:\n", json.dumps(data, indent=2))

    except requests.HTTPError as e:
        print(f"HTTP error: {e}\nURL tried: {url}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    variant = sys.argv[1]  # e.g. 19:41968837:C:G
    build = sys.argv[2] if len(sys.argv) > 2 else "GRCh38"
    get_hgvs(variant, build)