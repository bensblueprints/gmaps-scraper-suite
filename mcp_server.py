"""
MCP server for the GMaps Scraper Suite — exposes scraping tools to any MCP-compatible LLM.

Prerequisites:
    pip install mcp httpx

──────────────────────────────────────────────────────────────────────────────
Quick-start
──────────────────────────────────────────────────────────────────────────────
1. Start the API server from inside the scraper app (API tab → Start Server).
2. Generate an API key (API tab → Generate Key).
3. Add to Claude Desktop config  (~/.config/claude/claude_desktop_config.json):

{
  "mcpServers": {
    "gmaps-scraper": {
      "command": "python",
      "args": ["C:/Users/YOURNAME/Desktop/gmaps-scraper-suite/mcp_server.py"],
      "env": {
        "SCRAPER_API_KEY": "sk-your-generated-key",
        "SCRAPER_API_URL": "http://localhost:7842"
      }
    }
  }
}

──────────────────────────────────────────────────────────────────────────────
Available tools exposed to the LLM
──────────────────────────────────────────────────────────────────────────────
  scrape_leads(industry, location, max_leads)   → start a scrape job, return job_id
  get_job_status(job_id)                        → poll job progress + results
  scrape_and_wait(industry, location, max_leads)→ scrape + block until done (≤50 leads)
  get_leads(industry, city, limit)              → query existing lead database
  search_industries(query)                      → find industry categories to scrape
"""
import asyncio
import json
import os
import sys

import httpx

API_URL = os.environ.get("SCRAPER_API_URL", "http://localhost:7842").rstrip("/")
API_KEY = os.environ.get("SCRAPER_API_KEY", "")


def _headers() -> dict:
    return {"x-api-key": API_KEY, "Content-Type": "application/json"}


# ── MCP server ─────────────────────────────────────────────────────────────────

try:
    from mcp.server.fastmcp import FastMCP
    _HAVE_MCP = True
except ImportError:
    _HAVE_MCP = False

if _HAVE_MCP:
    mcp = FastMCP("GMaps Scraper")

    @mcp.tool()
    async def scrape_leads(industry: str, location: str, max_leads: int = 50) -> str:
        """
        Start a Google Maps scrape for businesses in the given industry and location.
        Returns a job_id — call get_job_status(job_id) to poll for results.

        Examples:
          scrape_leads("plumbers", "Austin, TX", 30)
          scrape_leads("dentists", "New York City, NY", 100)
        """
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{API_URL}/api/scrape",
                json={"industry": industry, "location": location, "max_leads": max_leads},
                headers=_headers(),
            )
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)

    @mcp.tool()
    async def get_job_status(job_id: str) -> str:
        """
        Check the status of a scrape started with scrape_leads.
        Returns status ("running" | "done" | "error"), leads_found, recent log, and results.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{API_URL}/api/jobs/{job_id}", headers=_headers())
            r.raise_for_status()
            data = r.json()
        return json.dumps({
            "job_id":      job_id,
            "status":      data["status"],
            "leads_found": data["leads_found"],
            "recent_log":  data.get("log", [])[-5:],
            "results":     data.get("result", []),
        }, indent=2)

    @mcp.tool()
    async def scrape_and_wait(industry: str, location: str, max_leads: int = 30) -> str:
        """
        Scrape Google Maps AND wait for the results before returning.
        Best for small jobs (max_leads ≤ 50). For bigger jobs use scrape_leads + get_job_status.
        Returns the complete list of leads when finished.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{API_URL}/api/scrape",
                json={"industry": industry, "location": location, "max_leads": max_leads},
                headers=_headers(),
            )
            r.raise_for_status()
            job_id = r.json()["job_id"]

        for _ in range(180):       # wait up to 6 minutes
            await asyncio.sleep(2)
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{API_URL}/api/jobs/{job_id}", headers=_headers())
                r.raise_for_status()
                data = r.json()
            if data["status"] in ("done", "error"):
                return json.dumps({
                    "status":      data["status"],
                    "leads_found": data["leads_found"],
                    "results":     data.get("result", []),
                }, indent=2)

        return json.dumps({"error": "Timed out after 6 minutes", "job_id": job_id})

    @mcp.tool()
    async def get_leads(industry: str = "", city: str = "", limit: int = 50) -> str:
        """
        Query leads already stored in the local database.
        Filter by industry, city, or leave blank for all.
        Returns a list of business records: name, phone, email, address, website, rating.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{API_URL}/api/leads",
                params={"industry": industry, "city": city, "limit": limit},
                headers=_headers(),
            )
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)

    @mcp.tool()
    async def search_industries(query: str = "") -> str:
        """
        Search the list of ~4,000 available industry categories.
        Use this to find the exact industry name before calling scrape_leads.
        Example: search_industries("dentist") → ["dentists", "cosmetic dentists", ...]
        """
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{API_URL}/api/industries",
                params={"q": query},
                headers=_headers(),
            )
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)

    def main():
        mcp.run(transport="stdio")

else:
    def main():
        print(
            "ERROR: 'mcp' package not installed.\n"
            "Run: pip install mcp httpx",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
