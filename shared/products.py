"""
Product registry — all white-label scraper products.
Each product ships with 1 scraping node; additional nodes purchased separately.
"""

PRODUCTS = {
    "lead-scraper-pro": {
        "name":               "Lead Scraper Pro",
        "slug":               "lead-scraper-pro",
        "color":              "#4FC3F7",
        "price_monthly":      297_00,   # cents
        "price_lifetime":     997_00,
        "price_extra_node":    99_00,   # per additional node/month or one-time for lifetime
        "nodes_included":     1,
        "description":        "General-purpose Google Maps lead scraper with email & platform detection.",
        "industries":         "all",
    },
    "discovery1": {
        "name":               "Discovery1",
        "slug":               "discovery1",
        "color":              "#E67E22",
        "price_monthly":      297_00,
        "price_lifetime":     997_00,
        "price_extra_node":    99_00,
        "nodes_included":     1,
        "description":        "Home maintenance & contractor lead scraper.",
        "industries":         "maintenance",
    },
    "prospecthunter": {
        "name":               "ProspectHunter",
        "slug":               "prospecthunter",
        "color":              "#8E44AD",
        "price_monthly":      297_00,
        "price_lifetime":     997_00,
        "price_extra_node":    99_00,
        "nodes_included":     1,
        "description":        "All-industry prospect & lead generation scraper.",
        "industries":         "all",
    },
    "atomicscraper": {
        "name":               "AtomicScraper",
        "slug":               "atomicscraper",
        "color":              "#00BCD4",
        "price_monthly":      297_00,
        "price_lifetime":     997_00,
        "price_extra_node":    99_00,
        "nodes_included":     1,
        "description":        "High-velocity lead scraper — atomicscraper.com",
        "industries":         "all",
    },
    "leadsbaby": {
        "name":               "Leads.Baby",
        "slug":               "leadsbaby",
        "color":              "#FF6B9D",
        "price_monthly":      297_00,
        "price_lifetime":     997_00,
        "price_extra_node":    99_00,
        "nodes_included":     1,
        "description":        "All-industry lead scraper — leads.baby",
        "industries":         "all",
    },
}


def get_product(slug: str) -> dict | None:
    return PRODUCTS.get(slug)


def price_display(cents: int) -> str:
    return f"${cents / 100:,.0f}"
