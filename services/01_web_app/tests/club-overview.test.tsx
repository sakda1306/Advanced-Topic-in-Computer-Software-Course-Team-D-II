import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ClubOverview } from "../components/ClubOverview";
vi.mock("../components/AppProvider", () => ({
  useApp: () => ({ team: { teamId: 66 } }),
}));
it("selects the nearest upcoming match of the selected club and sorts the league by position", async () => {
  const match = (id: string, kickoff: string, homeId = 66) => ({
    match_id: id,
    kickoff,
    status: "SCHEDULED",
    home: { team_id: homeId, name: "Home" },
    away: { team_id: 61, name: "Chelsea" },
    score: { home: null, away: null },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (path: string) =>
        new Response(
          JSON.stringify(
            path.includes("fixtures")
              ? {
                  matches: [
                    match("later", "2099-08-22"),
                    match("other-club", "2099-01-01", 65),
                    match("nearest", "2099-08-01"),
                  ],
                }
              : {
                  rows: [
                    {
                      position: 2,
                      team_id: 66,
                      name: "United",
                      played: 4,
                      goal_difference: 3,
                      points: 9,
                    },
                    {
                      position: 1,
                      team_id: 65,
                      name: "City",
                      played: 4,
                      goal_difference: 5,
                      points: 12,
                    },
                  ],
                },
          ),
          { status: 200 },
        ),
    ),
  );
  render(<ClubOverview />);
  expect(await screen.findByText("NEXT MATCH")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /VS/ })).toHaveAttribute(
    "href",
    "/matches/nearest",
  );
  const rows = await screen.findAllByRole("row");
  expect(rows[1]).toHaveTextContent("Man City");
  expect(rows[2]).toHaveClass("club-row");
});
