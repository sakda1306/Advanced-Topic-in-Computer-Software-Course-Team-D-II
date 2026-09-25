"use client";
import Link from "next/link";
import { useApp } from "./AppProvider";
import { useRemote } from "../lib/use-remote";
import { dateTime, Match, Standing } from "../lib/types";
import { teamFromId } from "../lib/teams";
import { ErrorBox, Loading } from "./Ui";

function Crest({ id, name }: { id: number; name: string }) {
  return teamFromId(id) ? (
    <img src={"/crests/" + id + ".png"} alt="" width={52} height={52} />
  ) : (
    <span className="opponent-initials">{name.slice(0, 3)}</span>
  );
}
export function ClubOverview() {
  const { team } = useApp();
  const fixtures = useRemote<{ matches: Match[] }>(
    "/football/fixtures?team_id=" + team.teamId,
  );
  const standings = useRemote<{ rows: Standing[]; season?: string }>(
    "/football/standings",
  );
  const matches = (fixtures.data?.matches ?? []).filter(
    (m) => m.home.team_id === team.teamId || m.away.team_id === team.teamId,
  );
  const next = matches
    .filter(
      (m) =>
        m.status === "SCHEDULED" && new Date(m.kickoff).getTime() >= Date.now(),
    )
    .sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff))[0];
  const match =
    next ??
    [...matches].sort(
      (a, b) => Date.parse(b.kickoff) - Date.parse(a.kickoff),
    )[0];
  const rows = [...(standings.data?.rows ?? [])]
    .sort((a, b) => a.position - b.position)
    .slice(0, 5);
  return (
    <>
      <section className="panel match-preview companion-card">
        <h2>{next ? "NEXT MATCH" : "MATCH CENTRE"}</h2>
        <small>
          {next ? "ศึกถัดไปที่กำลังรออยู่" : "การแข่งขันล่าสุดที่มีข้อมูล"}
        </small>
        {fixtures.loading ? (
          <Loading />
        ) : fixtures.error ? (
          <ErrorBox error={fixtures.error} />
        ) : match ? (
          <Link
            className="match-pair"
            href={"/matches/" + encodeURIComponent(match.match_id)}
          >
            <span>
              <Crest id={match.home.team_id} name={match.home.name} />
              <strong>
                {teamFromId(match.home.team_id)?.shortName ?? match.home.name}
              </strong>
            </span>
            <b>
              {match.status === "FINISHED"
                ? `${match.score.home ?? "—"} : ${match.score.away ?? "—"}`
                : "VS"}
            </b>
            <span>
              <Crest id={match.away.team_id} name={match.away.name} />
              <strong>
                {teamFromId(match.away.team_id)?.shortName ?? match.away.name}
              </strong>
            </span>
          </Link>
        ) : (
          <p className="match-empty">ยังไม่มีโปรแกรมของทีมนี้</p>
        )}
        {match && <small>{dateTime(match.kickoff)}</small>}
      </section>
      <section className="panel league-preview">
        <h2>LEAGUE SNAPSHOT</h2>
        <small>พรีเมียร์ลีก {standings.data?.season ?? ""}</small>
        {standings.loading ? (
          <Loading />
        ) : standings.error ? (
          <ErrorBox error={standings.error} />
        ) : rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>ทีม</th>
                  <th>P</th>
                  <th>GD</th>
                  <th>PTS</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.team_id}
                    className={row.team_id === team.teamId ? "club-row" : ""}
                  >
                    <td>{row.position}</td>
                    <td>
                      <span className="table-club">
                        <Crest id={row.team_id} name={row.name} />
                        {teamFromId(row.team_id)?.shortName ?? row.name}
                      </span>
                    </td>
                    <td>{row.played}</td>
                    <td>{row.goal_difference}</td>
                    <td>
                      <strong>{row.points}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>ยังไม่มีตารางคะแนน</p>
        )}
        <Link className="text-link" href="/football/standings">
          ดูตารางคะแนนทั้งหมด →
        </Link>
      </section>
    </>
  );
}
