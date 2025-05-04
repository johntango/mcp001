from typing import List, Union, Dict
import argparse
from secedgar.core.rest import (
    get_submissions,
    get_company_concepts,
    get_company_facts,
    get_xbrl_frames,
)
from secedgar.cik_lookup import CIKLookup
from fastmcp import FastMCP, Context

name = "SEClookup"

SEC_EDGAR_USER_AGENT="John Williams (jrwtango@gmail.com)"

sec_edgar_user_agent = SEC_EDGAR_USER_AGENT

# Parse command-line arguments for port (and optionally host)
parser = argparse.ArgumentParser(
    description="Start the lookup SSE server with configurable port and host"
)
parser.add_argument(
    "--port", "-p",
    type=int,
    default=8000,
    help="Port to bind the SSE server to (default: 8000)"
)
parser.add_argument(
    "--host", "-H",
    type=str,
    default="127.0.0.1",
    help="Host/interface to bind to (default: 127.0.0.1)"
)
args = parser.parse_args()
# Initialize MCP
mcp = FastMCP("SEC EDGAR MCP", dependencies=["secedgar"])


@mcp.tool("get_submissions", description="get the submissions of one or more companies")
async def get_submissions_tool(
    lookups: Union[str, List[str]],
    user_agent: str = sec_edgar_user_agent,
    recent: bool = True,
) -> Dict[str, dict]:
    """
    Retrieve submission records for specified companies using the SEC EDGAR REST API.

    Parameters:
        lookups (Union[str, List[str]]): Ticker(s) or CIK(s) of the companies.
        user_agent (str): User agent string required by the SEC.
        recent (bool): If True, retrieves at least one year of filings or the last 1000 filings. Defaults to True.

    Returns:
        Dict[str, dict]: A dictionary mapping each lookup to its submission data.
    """
    result = await get_submissions(lookups=lookups, user_agent=user_agent, recent=recent)
    return result


@mcp.tool("get_company_concepts",description="get the company concepts of one or more companies")
def get_company_concepts_tool(
    lookups: Union[str, List[str]],
    concept_name: str,
    user_agent: str = sec_edgar_user_agent,
) -> Dict[str, dict]:
    """
    Retrieve data for a specific financial concept for specified companies using the SEC EDGAR REST API.

    Parameters:
        lookups (Union[str, List[str]]): Ticker(s) or CIK(s) of the companies.
        concept_name (str): The financial concept to retrieve (e.g., "AccountsPayableCurrent").
        user_agent (str): User agent string required by the SEC.

    Returns:
        Dict[str, dict]: A dictionary mapping each lookup to its concept data.
    """
    return get_company_concepts(
        lookups=lookups,
        concept_name=concept_name,
        user_agent=user_agent,
    )


@mcp.tool("get_company_facts",description="get the facts of one or more companies")
def get_company_facts_tool(
    lookups: Union[str, List[str]], user_agent: str = sec_edgar_user_agent
) -> Dict[str, dict]:
    """
    Retrieve all standardized financial facts for specified companies using the SEC EDGAR REST API.

    Parameters:
        lookups (Union[str, List[str]]): Ticker(s) or CIK(s) of the companies.
        user_agent (str): User agent string required by the SEC.

    Returns:
        Dict[str, dict]: A dictionary mapping each lookup to its company facts data.
    """
    return get_company_facts(lookups=lookups, user_agent=user_agent)


@mcp.tool("get_xbrl_frames", description="get the xbrl frames of one or more companies")
def get_xbrl_frames_tool(
    concept_name: str,
    year: int,
    quarter: Union[int, None] = None,
    currency: str = "USD",
    instantaneous: bool = False,
    user_agent: str = sec_edgar_user_agent,
) -> dict:
    """
    Retrieve XBRL 'frames' data for a concept across companies for a specified time frame using the SEC EDGAR REST API.

    Parameters:
        concept_name (str): The financial concept to query (e.g., "Assets").
        year (int): The year for which to retrieve the data.
        quarter (Union[int, None]): The fiscal quarter (1-4) within the year. If None, data for the entire year is returned.
        currency (str): The reporting currency filter (default is "USD").
        instantaneous (bool): Whether to retrieve instantaneous values (True) or duration values (False) for the concept.
        user_agent (str): User agent string required by the SEC.

    Returns:
        dict: A dictionary containing the frame data for the specified concept and period.
    """
    return get_xbrl_frames(
        user_agent=user_agent,
        concept_name=concept_name,
        year=year,
        quarter=quarter,
        currency=currency,
        instantaneous=instantaneous,
    )

if __name__ == "__main__":
    url = f"http://{args.host}:{args.port}/sse"
    print(f"Starting SSE at {url} …")
    mcp.run(transport="sse", host=args.host, port=args.port)