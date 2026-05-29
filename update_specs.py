"""Patch all product spec files to add new hiddenimports and api pathex."""
from pathlib import Path

ROOT = Path(__file__).parent

NEW_IMPORTS = (
    "'shared.api_key_db', 'shared.phone_lookup', 'api', 'api.server', "
    "'fastapi', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops', "
    "'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', "
    "'uvicorn.protocols.http.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', "
    "'starlette', 'anyio', 'phonenumbers'"
)

specs = [
    "Discovery1.spec",
    "AtomicScraper.spec",
    "ProspectHunter.spec",
    "LeadsBaby.spec",
]

for spec_name in specs:
    path = ROOT / spec_name
    txt  = path.read_text(encoding="utf-8")

    # Insert new hidden imports before the closing bracket of the list
    if "'shared.api_key_db'" not in txt:
        txt = txt.replace(
            "'engine', 'tkinter', 'tkinter.ttk']",
            f"'engine', 'tkinter', 'tkinter.ttk', {NEW_IMPORTS}]"
        )

    # Add api to pathex
    txt = txt.replace("pathex=['.', 'scraper_node'],",
                      "pathex=['.', 'scraper_node', 'api'],")

    path.write_text(txt, encoding="utf-8")
    print(f"  Updated: {spec_name}")

print("Done.")
