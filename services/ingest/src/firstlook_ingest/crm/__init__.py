"""CRM migration importers: Affinity, HubSpot, Salesforce, Airtable (CSV + API)."""

from .csv_import import parse_csv
from .importer import ImportResult, import_records
from .model import CrmCompany, CrmDeal, CrmNote, CrmPerson, CrmRecords

__all__ = [
    "CrmCompany",
    "CrmDeal",
    "CrmNote",
    "CrmPerson",
    "CrmRecords",
    "ImportResult",
    "import_records",
    "parse_csv",
]
