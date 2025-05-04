from typing import Union, List, Dict, Any
from edgar import set_identity, Company, get_filings

# Define your SEC‑compliant identity
IDENTITY: str = "John Williams (jrwtango@gmail.com)"

def get_submissions_tool(
    lookups: Union[str, List[str]],
    identity: str = IDENTITY,
    recent: bool = True
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch SEC submissions for a given ticker or CIK (or multiple).

    Parameters
    ----------
    lookups : Union[str, List[str]]
        Single ticker/CIK or list of them.
    identity : str
        Your SEC‑compliant user identity (name/email).
    recent : bool
        If True, fetch filings for the current year and quarter;
        if False, fetch all available filings.

    Returns
    -------
    Dict[str, List[Dict[str, Any]]]
        Mapping each lookup to a list of dicts with keys:
        - accession_number
        - filing_date
        - form_type
        - url
    """
    # Register your identity with edgartools
    set_identity(identity)  # :contentReference[oaicite:0]{index=0}

    # Normalize to list
    tickers = [lookups] if isinstance(lookups, str) else lookups
    result: Dict[str, List[Dict[str, Any]]] = {}

    for lookup in tickers:
        # Instantiate a Company (auto‑lookup if ticker)
        company = Company(lookup)  # :contentReference[oaicite:1]{index=1}

        # Retrieve filings
        if recent:
            filings = company.get_filings()        # current year/quarter :contentReference[oaicite:2]{index=2}
        else:
            filings = company.get_filings(year=None)  # all filings (no filter)

        # Extract key metadata
        submissions = []
        for filing in filings:
            submissions.append({
                "accession_number": filing.accession_number,
                "filing_date":      filing.filing_date,
                "form":             filing.form,
                "url":              filing.url
            })

        result[lookup] = submissions

    return result


if __name__ == "__main__":
    params = {
        "lookups": ["MIT"],    # or CIK: ["0000789019"]
        "identity": IDENTITY,
        "recent": True          # only current year/quarter
    }

    submissions = get_submissions_tool(**params)

    for symbol, subs in submissions.items():
        print(f"\nSubmissions for {symbol}:")
        for s in subs:
            print(
                f"  • {s['form']} on {s['filing_date']} "
                f"(Accession: {s['accession_number']})\n"
                f"    URL: {s['url']}"
            )
