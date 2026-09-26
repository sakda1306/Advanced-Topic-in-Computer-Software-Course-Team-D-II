import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Team:
    team_id: int
    name: str
    short_name: str
    aliases: tuple[str, ...]


class TeamDirectory:
    def __init__(self, teams: list[Team]):
        self.teams = teams

    @classmethod
    def from_file(cls, path: Path) -> "TeamDirectory":
        return cls.from_payload(json.loads(path.read_text(encoding="utf-8-sig")))

    @classmethod
    def from_payload(cls, payload: dict) -> "TeamDirectory":
        return cls([Team(int(item["team_id"]), item["name"], item["short_name"],
                         tuple(item.get("aliases", []))) for item in payload["teams"]])

    def merged(self, live: "TeamDirectory") -> "TeamDirectory":
        by_id = {team.team_id: team for team in self.teams}
        for team in live.teams:
            previous = by_id.get(team.team_id)
            aliases = tuple(dict.fromkeys((*previous.aliases, *team.aliases))) if previous else team.aliases
            by_id[team.team_id] = Team(team.team_id, team.name, team.short_name, aliases)
        return TeamDirectory(list(by_id.values()))

    def find(self, query: str) -> list[Team]:
        found = []
        for team in self.teams:
            names = (team.short_name, team.name, *team.aliases)
            first_position = None
            for name in names:
                if not name:
                    continue
                pattern = re.escape(name)
                if name[0].isascii() and name[0].isalnum():
                    pattern = r"(?<![A-Za-z0-9])" + pattern
                if name[-1].isascii() and name[-1].isalnum():
                    pattern += r"(?![A-Za-z0-9])"
                match = re.search(pattern, query, re.IGNORECASE)
                if match and (first_position is None or match.start() < first_position):
                    first_position = match.start()
            if first_position is not None:
                found.append((first_position, team))
        return [team for _, team in sorted(found, key=lambda item: item[0])]

    def replace_aliases(self, query: str) -> str:
        replacements = []
        for team in self.teams:
            for name in (team.short_name, team.name, *team.aliases):
                if name:
                    replacements.append((name, team.short_name))
        result = query
        for name, replacement in sorted(replacements, key=lambda pair: len(pair[0]), reverse=True):
            pattern = re.escape(name)
            if name[0].isascii() and name[0].isalnum():
                pattern = r"(?<![A-Za-z0-9])" + pattern
            if name[-1].isascii() and name[-1].isalnum():
                pattern += r"(?![A-Za-z0-9])"
            result = re.sub(pattern, lambda _: replacement, result, flags=re.IGNORECASE)
        return result
