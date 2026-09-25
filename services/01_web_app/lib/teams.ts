export const teams = [
  {
    key: "manchester-united",
    name: "Manchester United",
    shortName: "Man United",
    initials: "MU",
    teamId: 66,
    mascot: "/mascots/manchester-united.webp",
    color: "#e9474e",
    colorBright: "#fa777c",
    glow: "233, 47, 59",
    hero: "THE RED SIDE OF FOOTBALL",
  },
  {
    key: "manchester-city",
    name: "Manchester City",
    shortName: "Man City",
    initials: "MC",
    teamId: 65,
    mascot: "/mascots/manchester-city.webp",
    color: "#79c9f3",
    colorBright: "#c6ecff",
    glow: "83, 180, 231",
    hero: "PAINT THE CITY BLUE",
  },
  {
    key: "chelsea",
    name: "Chelsea",
    shortName: "Chelsea",
    initials: "CH",
    teamId: 61,
    mascot: "/mascots/chelsea.webp",
    color: "#5579ff",
    colorBright: "#9bb2ff",
    glow: "46, 91, 245",
    hero: "BLUE IS THE COLOUR",
  },
  {
    key: "liverpool",
    name: "Liverpool",
    shortName: "Liverpool",
    initials: "LIV",
    teamId: 64,
    mascot: "/mascots/liverpool.webp",
    color: "#e84a55",
    colorBright: "#ff8c91",
    glow: "204, 41, 58",
    hero: "YOU'LL NEVER WALK ALONE",
  },
  {
    key: "arsenal",
    name: "Arsenal",
    shortName: "Arsenal",
    initials: "ARS",
    teamId: 57,
    mascot: "/mascots/arsenal.webp",
    color: "#c6a365",
    colorBright: "#ffd89f",
    glow: "198, 163, 101",
    hero: "NORTH LONDON FOREVER",
  },
] as const;

export type TeamKey = (typeof teams)[number]["key"];
export type Team = (typeof teams)[number];

export function teamFromId(teamId: number | null): Team | undefined {
  return teams.find((team) => team.teamId === teamId);
}
