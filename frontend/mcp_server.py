from fastmcp import FastMCP

mcp = FastMCP("Supply Chain Google MCP Tools")

@mcp.tool()
def send_gmail_email(to: str, subject: str, body: str) -> str:
    return f"Email sent to {to} with subject: {subject}"

@mcp.tool()
def create_calendar_event(title: str, date: str, description: str) -> str:
    return f"Calendar event created: {title} on {date}"

@mcp.tool()
def append_google_sheet_row(spreadsheet_id: str, row: str) -> str:
    return f"Row appended to spreadsheet {spreadsheet_id}: {row}"

app = mcp.http_app(path="/mcp")
