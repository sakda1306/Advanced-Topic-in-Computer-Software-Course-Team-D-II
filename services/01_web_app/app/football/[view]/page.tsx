"use client";
import Link from "next/link";
import { useState } from "react";
import { useRemote } from "../../../lib/use-remote";
import {
  dateTime,
  FootballStatus,
  Match,
  Report,
  Standing,
} from "../../../lib/types";
import { teams } from "../../../lib/teams";
import { ErrorBox, Empty, Loading, PageTitle } from "../../../components/Ui";
import { Markdown } from "../../../components/Answer";
import { ApiError } from "../../../lib/api";
const statusLabels: Record<string, string> = {
  SCHEDULED: "รอแข่งขัน",
  LIVE: "กำลังแข่งขัน",
  FINISHED: "จบการแข่งขัน",
  POSTPONED: "เลื่อนการแข่งขัน",
  CANCELLED: "ยกเลิก",
};
export default function FootballPage({ params }: { params: { view: string } }) {
  return <FootballView key={params.view} view={params.view} />;
}
function FootballView({ view }: { view: string }) {
  const [season, setSeason] = useState(""),
    [week, setWeek] = useState(""),
    [team, setTeam] = useState(""),
    [status, setStatus] = useState("");
  const [query, setQuery] = useState(""),
    [revision, setRevision] = useState(0);
  const live = useRemote<FootballStatus>("/football/status", revision);
  const titles: Record<string, string> = {
    fixtures: "ผลและโปรแกรมการแข่งขัน",
    standings: "ตารางคะแนน",
    reports: "รายงานประจำสัปดาห์",
  };
  const valid = view in titles;
  const resource = useRemote<
    {
      rows?: Standing[];
      matches?: Match[];
      fetched_at?: string;
      season?: string;
    } & Partial<Report>
  >(
    valid
      ? "/football/" + (view === "reports" ? "reports/weekly" : view) + query
      : null,
    revision,
  );
  if (!valid)
    return (
      <Empty>
        ไม่พบหน้านี้ <Link href="/">กลับหน้าแรก</Link>
      </Empty>
    );
  const emptyReport =
    resource.error instanceof ApiError &&
    resource.error.status === 404 &&
    view === "reports";
  return (
    <>
      <PageTitle eyebrow="PREMIER LEAGUE" title={titles[view]} />
      <div className="status-strip">
        <span>
          ฤดูกาล {live.data?.current_season ?? "—"} · นัดที่{" "}
          {live.data?.current_matchweek ?? "—"}
        </span>
        <span>อัปเดตล่าสุด {dateTime(live.data?.last_ingest_at)}</span>
        <button onClick={() => setRevision((value) => value + 1)}>
          รีเฟรช
        </button>
      </div>
      <ErrorBox
        error={live.error}
        retry={() => setRevision((value) => value + 1)}
      />
      <form
        className="filter-bar panel"
        onSubmit={(event) => {
          event.preventDefault();
          const search = new URLSearchParams();
          if (season) search.set("season", season);
          if (view !== "standings" && week) search.set("matchweek", week);
          if (view === "fixtures") {
            if (team) search.set("team_id", team);
            if (status) search.set("status", status);
          }
          setQuery(search.size ? "?" + search.toString() : "");
        }}
      >
        <label>
          ฤดูกาล
          <input
            placeholder={live.data?.current_season ?? "ปีเริ่มฤดูกาล"}
            value={season}
            pattern="[0-9]{4}"
            inputMode="numeric"
            maxLength={4}
            onChange={(event) => setSeason(event.target.value)}
          />
        </label>
        {view !== "standings" && (
          <label>
            แมตช์วีค
            <input
              type="number"
              min={1}
              max={38}
              placeholder="ล่าสุด / ทั้งหมด"
              value={week}
              onChange={(event) => setWeek(event.target.value)}
            />
          </label>
        )}
        {view === "fixtures" && (
          <>
            <label>
              ทีม
              <select
                value={team}
                onChange={(event) => setTeam(event.target.value)}
              >
                <option value="">ทุกทีม</option>
                {teams.map((item) => (
                  <option key={item.key} value={item.teamId}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              สถานะ
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                <option value="">ทุกสถานะ</option>
                {Object.entries(statusLabels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
        <button className="primary">แสดงข้อมูล</button>
      </form>
      {resource.loading ? (
        <Loading />
      ) : emptyReport ? (
        <Empty>ยังไม่มีรายงานที่เผยแพร่ในช่วงที่เลือก</Empty>
      ) : resource.error ? (
        <ErrorBox
          error={resource.error}
          retry={() => setRevision((value) => value + 1)}
        />
      ) : (
        <section className="panel">
          {resource.data?.fetched_at && (
            <p className="muted">
              ข้อมูล ณ {dateTime(resource.data.fetched_at)}
            </p>
          )}
          {view === "standings" &&
            (resource.data?.rows?.length ? (
              <div className="table-scroll">
                <table>
                  <caption className="sr-only">ตารางคะแนนพรีเมียร์ลีก</caption>
                  <thead>
                    <tr>
                      {[
                        "อันดับ",
                        "ทีม",
                        "แข่ง",
                        "ชนะ",
                        "เสมอ",
                        "แพ้",
                        "ได้",
                        "เสีย",
                        "+/−",
                        "คะแนน",
                        "ฟอร์ม",
                      ].map((label) => (
                        <th key={label}>{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resource.data.rows.map((row) => (
                      <tr key={row.team_id}>
                        <td>{row.position}</td>
                        <th scope="row">{row.name}</th>
                        <td>{row.played}</td>
                        <td>{row.won}</td>
                        <td>{row.draw}</td>
                        <td>{row.lost}</td>
                        <td>{row.goals_for}</td>
                        <td>{row.goals_against}</td>
                        <td>{row.goal_difference}</td>
                        <td>
                          <strong>{row.points}</strong>
                        </td>
                        <td>{row.form || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>ยังไม่มีตารางคะแนน</Empty>
            ))}
          {view === "fixtures" &&
            (resource.data?.matches?.length ? (
              <div className="match-list">
                {resource.data.matches.map((match) => (
                  <Link
                    className="match-row"
                    href={"/matches/" + match.match_id}
                    key={match.match_id}
                  >
                    <div>
                      <small>
                        {dateTime(match.kickoff)} · นัดที่ {match.matchweek}
                      </small>
                      <span>{statusLabels[match.status] ?? match.status}</span>
                    </div>
                    <strong>{match.home.name}</strong>
                    <b className="score">
                      {match.score.home ?? "—"} : {match.score.away ?? "—"}
                    </b>
                    <strong>{match.away.name}</strong>
                  </Link>
                ))}
              </div>
            ) : (
              <Empty>ไม่มีการแข่งขันตรงกับตัวกรอง</Empty>
            ))}
          {view === "reports" && resource.data?.markdown && (
            <article>
              <span className="badge">
                นัดที่ {resource.data.matchweek} · เผยแพร่แล้ว
              </span>
              <h2>{resource.data.title}</h2>
              <p className="muted">
                ข้อมูล ณ {dateTime(resource.data.data_as_of)}
              </p>
              <Markdown text={resource.data.markdown} />
            </article>
          )}
        </section>
      )}
    </>
  );
}
