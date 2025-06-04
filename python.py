import json
import requests
from datetime import date, timedelta, datetime
from calendar import month_name
from requests.auth import HTTPBasicAuth

class ReleaseCalendar:
    def __init__(self, start_version: str, version_count: int = 6):
        self.start_version = start_version
        self.version_count = version_count
        self.today = date.today()
        self.major, self.minor = map(int, self.start_version.split('.'))
        self.releases_json = {}

        self.tst_week_numbers = [7, 19, 31, 43]
        self.prd_week_numbers = [12, 24, 36, 48]
        self.deprecation_map = {
            12: (48, 0),
            24: (12, 1),
            36: (24, 1),
            48: (48, 1)
        }

    def get_date_from_week(self, year, week, weekday):
        return date.fromisocalendar(year, week, weekday)

    def format_release(self, label, release_date):
        return {
            "Delivery": release_date.isoformat(),
            "Day": release_date.day,
            "Month": month_name[release_date.month],
            "Week": release_date.isocalendar()[1]
        }

    def get_next_tuesday(self, start_date):
        days_ahead = (1 - start_date.weekday()) % 7
        return start_date + timedelta(days=days_ahead)

    def generate_releases(self):
        current_year = self.today.isocalendar()[0]
        current_week = self.today.isocalendar()[1]
        tst_index = 0
        prd_index = 0

        for _ in range(self.version_count):
            version_str = f"{self.major}.{self.minor}"
            self.releases_json[version_str] = {}

            while tst_index < len(self.tst_week_numbers) and self.tst_week_numbers[tst_index] < current_week:
                tst_index += 1
            if tst_index >= len(self.tst_week_numbers):
                current_year += 1
                current_week = 1
                tst_index = 0
            tst_week = self.tst_week_numbers[tst_index]

            while prd_index < len(self.prd_week_numbers) and self.prd_week_numbers[prd_index] < current_week:
                prd_index += 1
            if prd_index >= len(self.prd_week_numbers):
                current_year += 1
                current_week = 1
                prd_index = 0
            prd_week = self.prd_week_numbers[prd_index]

            tst_date = self.get_date_from_week(current_year, tst_week, 4)
            help_date = self.get_date_from_week(current_year, prd_week, 2)
            prd_date = self.get_date_from_week(current_year, prd_week, 3)

            deprec_week, year_offset = self.deprecation_map[prd_week]
            deprec_year = current_year + year_offset
            deprec_date = self.get_date_from_week(deprec_year, deprec_week, 4)

            potential_date = deprec_date + timedelta(weeks=5)
            deact_date = self.get_next_tuesday(potential_date)

            self.releases_json[version_str]["TST Release"] = self.format_release("TST", tst_date)
            self.releases_json[version_str]["Integration of help packages"] = self.format_release("Help Packages", help_date)
            self.releases_json[version_str]["PRD Release"] = self.format_release("PRD", prd_date)
            self.releases_json[version_str]["Deprecation"] = self.format_release("Deprecation", deprec_date)
            self.releases_json[version_str]["Deactivation"] = self.format_release("Deactivation", deact_date)

            self.minor += 1
            prd_index += 1
            tst_index += 1

    def to_json(self):
        return json.dumps(self.releases_json, indent=2)

class ConfluenceTableFormatter:
    def __init__(self, releases_json):
        self.releases = releases_json

    def format_ddmm(self, iso_date):
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d.%m")

    def generate_table(self):
        headers = ["", *self.releases.keys()]
        rows = {
            "Year<br>Quarter<br>Release number": [],
            "Delivery in TST": [],
            "Delivery in PRD": [],
            "Depredation": [],
            "Deactivation": [],
        }

        for version in self.releases:
            info = self.releases[version]
            prd = info["PRD Release"]
            tst = info["TST Release"]
            depr = info["Deprecation"]
            deac = info["Deactivation"]

            year = datetime.fromisoformat(prd["Delivery"]).year
            month = datetime.fromisoformat(prd["Delivery"]).month
            quarter = (month - 1) // 3 + 1

            rows["Year<br>Quarter<br>Release number"].append(f"{year}<br>Q{quarter}<br>{version}")
            rows["Delivery in TST"].append(f"Week {tst['Week']}<br>{self.format_ddmm(tst['Delivery'])}")
            rows["Delivery in PRD"].append(f"Week {prd['Week']}<br>{self.format_ddmm(prd['Delivery'])}")
            rows["Depredation"].append(f"Week {depr['Week']}<br>{self.format_ddmm(depr['Delivery'])}")
            rows["Deactivation"].append(f"Week {deac['Week']}<br>{self.format_ddmm(deac['Delivery'])}")

        table = "|| " + " || ".join(headers) + " ||\n"
        for row_label, row_data in rows.items():
            table += f"| {row_label} | " + " | ".join(row_data) + " |\n"
        return table

    def publish_to_confluence(self, confluence_url, space_key, page_title, auth_email, api_token, parent_page_id=None):
        table_content = self.generate_table()
        url = f"{confluence_url}/rest/api/content"
        headers = {"Content-Type": "application/json"}

        existing_page_req = requests.get(
            url,
            params={"title": page_title, "spaceKey": space_key, "expand": "version"},
            auth=HTTPBasicAuth(auth_email, api_token)
        )
        existing_page = existing_page_req.json().get("results")
        is_update = existing_page and len(existing_page) > 0

        body = {
            "type": "page",
            "title": page_title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": f"<p>Auto-generated release calendar:</p><pre>{table_content}</pre>",
                    "representation": "storage"
                }
            }
        }

        if is_update:
            page = existing_page[0]
            page_id = page["id"]
            current_version = page["version"]["number"]
            body["version"] = {"number": current_version + 1}
            res = requests.put(f"{url}/{page_id}", headers=headers, json=body, auth=HTTPBasicAuth(auth_email, api_token))
        else:
            if parent_page_id:
                body["ancestors"] = [{"id": parent_page_id}]
            res = requests.post(url, headers=headers, json=body, auth=HTTPBasicAuth(auth_email, api_token))

        print("✅ Published to Confluence" if res.status_code in [200, 201] else f"❌ Failed: {res.status_code}")

    def create_jira_tickets(self, jira_url, project_key, auth_email, api_token, epic_key):
        stages = {
            "TST": "TST Release",
            "PRD": "PRD Release",
            "Deprecation": "Deprecation",
            "Deactivation": "Deactivation"
        }

        headers = {"Content-Type": "application/json"}
        url = f"{jira_url}/rest/api/2/issue"

        for version, data in self.releases.items():
            for stage, key in stages.items():
                delivery_date = data[key]["Delivery"]

                issue_payload = {
                    "fields": {
                        "project": {"key": project_key},
                        "summary": f"{version} - Altea GUI {version}",
                        "issuetype": {"name": "Story"},
                        "priority": {"name": "Normal"},
                        "labels": ["sherriff"],
                        "description": f"Please deliver the {version} latest version to {stage} for all airlines",
                        "duedate": delivery_date,
                        "customfield_10008": epic_key
                    }
                }

                res = requests.post(url, headers=headers, json=issue_payload, auth=HTTPBasicAuth(auth_email, api_token))

                if res.status_code in [200, 201]:
                    print(f"✅ Created Jira ticket for {version} - {stage}")
                else:
                    print(f"❌ Failed to create ticket for {version} - {stage}: {res.status_code}")
                    print(res.text)

def auto_generate_releases(start_version: str, version_count: int = 6):
    calendar = ReleaseCalendar(start_version, version_count)
    calendar.generate_releases()
    return calendar.releases_json

if __name__ == "__main__":
    releases_data = auto_generate_releases("9.22", 6)

    with open("release_schedule.json", "w") as f:
        json.dump(releases_data, f, indent=2)
    print("✅ Saved release_schedule.json")

    with open("release_schedule.json", "r") as f:
        release_data = json.load(f)

    # Generate and print Confluence table
    formatter = ConfluenceTableFormatter(release_data)
    confluence_table = formatter.generate_table()
    print("\nConfluence Table:\n")
    print(confluence_table)

    # Generate and print Jira ticket JSONs
    epic_id = "GUI-9999"  # Replace with your actual epic ID
    jira_tickets = formatter.create_jira_tickets(epic_id)
    print("\nJira Ticket JSON Payloads:\n")
    for ticket in jira_tickets:
        print(json.dumps(ticket, indent=2))
