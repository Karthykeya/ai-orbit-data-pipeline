import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

mcp = json.load(open("data/mcp_servers.json"))
companies = json.load(open("data/companies.json"))
rels = json.load(open("data/relationships.json"))

wb = Workbook()

# ---------- Sheet 1: MCP Servers (main dataset) ----------
ws = wb.active
ws.title = "MCP Servers"
headers = ["id", "entity_type", "name", "description", "official_url", "logo_url",
           "categories", "vendor", "server_url", "auth_type", "transport",
           "installation", "source_name", "source_url"]
ws.append(headers)
for rec in mcp:
    ws.append([
        rec["id"], rec["entity_type"], rec["name"], rec["description"],
        rec["url"], rec["logo_url"], ", ".join(rec["categories"]),
        rec["metadata"]["vendor"], rec["metadata"]["server_url"],
        rec["metadata"]["auth_type"], rec["metadata"]["transport"],
        rec["metadata"]["installation"], rec["source"]["name"], rec["source"]["url"],
    ])

# ---------- Sheet 2: Companies ----------
ws2 = wb.create_sheet("Companies")
headers2 = ["id", "entity_type", "name", "description", "official_url",
            "categories", "industry_sector", "source_name", "source_url"]
ws2.append(headers2)
for rec in companies:
    ws2.append([
        rec["id"], rec["entity_type"], rec["name"], rec["description"], rec["url"],
        ", ".join(rec["categories"]), rec["industry_sector"],
        rec["source"]["name"], rec["source"]["url"],
    ])

# ---------- Sheet 3: Relationships ----------
ws3 = wb.create_sheet("Relationships")
headers3 = ["id", "type", "source_id", "source_type", "target_id", "target_type", "note"]
ws3.append(headers3)
for rec in rels:
    ws3.append([
        rec["id"], rec["type"], rec["source_id"], rec["source_type"],
        rec["target_id"], rec["target_type"], rec.get("note", ""),
    ])

# ---------- Sheet 4: README ----------
ws4 = wb.create_sheet("README", 0)
readme_lines = [
    ("AI Orbit Data Ingestion — MCP Servers Module", True),
    ("", False),
    ("Scope: 75 official, first-party MCP (Model Context Protocol) servers,", False),
    ("verified against each vendor's own documentation (see source_url per row).", False),
    ("", False),
    ("Sheets:", True),
    ("  MCP Servers    - main dataset (75 records)", False),
    ("  Companies      - derived vendor/company entities (69 records)", False),
    ("  Relationships  - Company-develops-MCP and MCP-integrates_with-Tool edges (150)", False),
    ("", False),
    ("Data quality notes:", True),
    ("  - url = official documentation page for each server (not a 3rd-party directory)", False),
    ("  - logo_url = Clearbit Logo API keyed to the vendor's own verified apex domain", False),
    ("  - descriptions were written by an LLM (Claude) after cleaning/verification", False),
    ("  - ids are deterministic UUIDv5s so re-running the pipeline is idempotent", False),
    ("", False),
    ("Pipeline & code: see the accompanying GitHub repository.", False),
]
for i, (text, bold) in enumerate(readme_lines, start=1):
    cell = ws4.cell(row=i, column=1, value=text)
    cell.font = Font(name="Arial", bold=bold, size=13 if bold and i == 1 else 11)

# ---------- Formatting ----------
header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
header_font = Font(name="Arial", bold=True, color="FFFFFF")
for sheet in (ws, ws2, ws3):
    for cell in sheet[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    sheet.freeze_panes = "A2"
    for col_cells in sheet.columns:
        col_letter = get_column_letter(col_cells[0].column)
        max_len = max((len(str(c.value)) for c in col_cells if c.value is not None), default=10)
        sheet.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 60)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial", size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=False)

ws4.column_dimensions["A"].width = 90

wb.save("data/AI_Orbit_MCP_Dataset.xlsx")
print("saved")
