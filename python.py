import json
from datetime import date, timedelta
from calendar import month_name

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
        """Get date for a given ISO year, week, and weekday (1=Mon ... 7=Sun)."""
        return date.fromisocalendar(year, week, weekday)

    def format_release(self, label, release_date):
        return {
            f"Delivery in {label}": release_date.isoformat(),
            "Day": release_date.day,
            "Month": month_name[release_date.month],
            "Week": release_date.isocalendar()[1]
        }

    def get_next_tuesday(self, start_date):
        """Return the next Tuesday on or after a given date."""
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

            # Get next TST week
            while tst_index < len(self.tst_week_numbers) and self.tst_week_numbers[tst_index] < current_week:
                tst_index += 1
            if tst_index >= len(self.tst_week_numbers):
                current_year += 1
                current_week = 1
                tst_index = 0
            tst_week = self.tst_week_numbers[tst_index]

            # Get next PRD week
            while prd_index < len(self.prd_week_numbers) and self.prd_week_numbers[prd_index] < current_week:
                prd_index += 1
            if prd_index >= len(self.prd_week_numbers):
                current_year += 1
                current_week = 1
                prd_index = 0
            prd_week = self.prd_week_numbers[prd_index]

            # Calculate release dates
            tst_date = self.get_date_from_week(current_year, tst_week, 4)   # Thursday
            help_date = self.get_date_from_week(current_year, prd_week, 2)  # Tuesday
            prd_date = self.get_date_from_week(current_year, prd_week, 3)   # Wednesday

            # Deprecation
            deprec_week, year_offset = self.deprecation_map[prd_week]
            deprec_year = current_year + year_offset
            deprec_date = self.get_date_from_week(deprec_year, deprec_week, 4)  # Thursday

            # Deactivation = 5 weeks after deprecation on the next Tuesday
            potential_date = deprec_date + timedelta(weeks=5)
            deact_date = self.get_next_tuesday(potential_date)

            # Assign data
            self.releases_json[version_str]["TST Release"] = self.format_release("TST", tst_date)
            self.releases_json[version_str]["Integration of help packages"] = self.format_release("Help Packages", help_date)
            self.releases_json[version_str]["PRD Release"] = self.format_release("PRD", prd_date)
            self.releases_json[version_str]["Deprecation"] = self.format_release("Deprecation", deprec_date)
            self.releases_json[version_str]["Deactivation"] = self.format_release("Deactivation", deact_date)

            # Next version
            self.minor += 1
            prd_index += 1
            tst_index += 1

    def to_json(self):
        return json.dumps(self.releases_json, indent=2)

def auto_generate_releases(start_version: str, version_count: int = 6):
    calendar = ReleaseCalendar(start_version, version_count)
    calendar.generate_releases()
    return calendar.to_json()


if __name__ == "__main__":
    json_output = auto_generate_releases("9.22", 6)

    # Save to a JSON file
    with open("release_schedule.json", "w") as f:
        f.write(json_output)

    print("Release schedule saved to 'release_schedule.json'")
