"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  api,
  body,
  accountEpoch,
  invalidateAccount,
  isCancelled,
} from "../lib/api";
import { ChatEntry, ChatResult, Session, User } from "../lib/types";
import { TeamKey, teamFromId, teams } from "../lib/teams";

function useAppState() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [authError, setAuthError] = useState<Error>();
  const [teamKey, setTeamKey] = useState<TeamKey>(teams[0].key);
  const [teamBusy, setTeamBusy] = useState(false);
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<Error>();
  const [historyError, setHistoryError] = useState<Error>();
  const [draft, setDraft] = useState("");
  const [openSignal, setOpenSignal] = useState(0);
  const identity = useRef<string | null>(null);
  const busy = useRef(false);
  const preferenceBusy = useRef(false);
  const conversation = useRef(0);
  const team = teams.find((item) => item.key === teamKey) ?? teams[0];

  const clearAccount = useCallback(() => {
    invalidateAccount();
    conversation.current++;
    identity.current = null;
    busy.current = false;
    preferenceBusy.current = false;
    setUser(null);
    setEntries([]);
    setSessions([]);
    setSessionId(null);
    setPending(false);
    setHistoryLoading(false);
    setTeamBusy(false);
    setDraft("");
    setError(undefined);
    setHistoryError(undefined);
    setAuthError(undefined);
  }, []);

  const refreshSessions = useCallback(async () => {
    const epoch = accountEpoch();
    try {
      const data = await api<{ sessions: Session[] }>("/sessions");
      setSessions(data.sessions);
      setHistoryError(undefined);
    } catch (error) {
      if (epoch === accountEpoch() && !isCancelled(error))
        setHistoryError(error as Error);
    }
  }, []);

  const acceptUser = useCallback(
    (next: User) => {
      if (identity.current !== next.id) clearAccount();
      identity.current = next.id;
      setUser(next);
      const favorite = teamFromId(next.favorite_team_id);
      if (favorite) setTeamKey(favorite.key);
      setAuthError(undefined);
      setChecked(true);
      void refreshSessions();
    },
    [clearAccount, refreshSessions],
  );

  const checkAuth = useCallback(
    async (signal?: AbortSignal) => {
      setAuthError(undefined);
      try {
        const data = await api<{ user: User }>("/auth/me", { signal });
        if (!signal?.aborted) acceptUser(data.user);
      } catch (error) {
        if (!signal?.aborted && !isCancelled(error)) {
          if ((error as { status?: number }).status !== 401)
            setAuthError(error as Error);
        }
      } finally {
        if (!signal?.aborted) setChecked(true);
      }
    },
    [acceptUser],
  );

  useEffect(() => {
    const controller = new AbortController();
    const expire = () => {
      clearAccount();
      setChecked(true);
      router.replace("/login?expired=1");
    };
    window.addEventListener("pitchside:expired", expire);
    void checkAuth(controller.signal);
    return () => {
      controller.abort();
      window.removeEventListener("pitchside:expired", expire);
    };
  }, [checkAuth, clearAccount, router]);

  async function login(username: string, password: string) {
    const data = await api<{ user: User }>(
      "/auth/login",
      body({ username, password }),
    );
    acceptUser(data.user);
    router.replace("/");
  }
  async function logout() {
    clearAccount();
    try {
      await api("/auth/logout", { method: "POST" });
    } catch (error) {
      if (!isCancelled(error)) setAuthError(error as Error);
    } finally {
      router.replace("/login");
    }
  }
  function newChat() {
    conversation.current++;
    busy.current = false;
    setPending(false);
    setHistoryLoading(false);
    setEntries([]);
    setSessionId(null);
    setDraft("");
    setError(undefined);
  }
  async function selectSession(id: string) {
    const ticket = ++conversation.current;
    busy.current = false;
    setPending(false);
    setHistoryLoading(true);
    setError(undefined);
    setEntries([]);
    setDraft("");
    setSessionId(id);
    try {
      const data = await api<{
        messages: (Omit<ChatEntry, "id"> & { message_id: string })[];
      }>("/history/" + encodeURIComponent(id));
      if (ticket === conversation.current)
        setEntries(
          data.messages.map((item) => ({ ...item, id: item.message_id })),
        );
    } catch (error) {
      if (ticket === conversation.current && !isCancelled(error))
        setError(error as Error);
    } finally {
      if (ticket === conversation.current) setHistoryLoading(false);
    }
  }
  async function changeTeam(key: TeamKey) {
    const next = teams.find((item) => item.key === key)!;
    if (
      preferenceBusy.current ||
      busy.current ||
      (key === teamKey && (!user || user.favorite_team_id === next.teamId))
    )
      return;
    if (!user) {
      setTeamKey(key);
      return;
    }
    const epoch = accountEpoch();
    preferenceBusy.current = true;
    setTeamBusy(true);
    setError(undefined);
    try {
      const data = await api<{ user: User }>("/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ favorite_team_id: next.teamId }),
      });
      setUser(data.user);
      setTeamKey(key);
      newChat();
    } catch (error) {
      if (epoch === accountEpoch() && !isCancelled(error))
        setError(error as Error);
    } finally {
      if (epoch === accountEpoch()) {
        preferenceBusy.current = false;
        setTeamBusy(false);
      }
    }
  }
  async function sendQuestion(question: string) {
    const message = question.trim();
    if (
      !user ||
      busy.current ||
      preferenceBusy.current ||
      historyLoading ||
      !message ||
      message.length > 2000
    )
      return false;
    const epoch = accountEpoch(),
      ticket = conversation.current;
    busy.current = true;
    setPending(true);
    setError(undefined);
    const optimisticId = crypto.randomUUID();
    setEntries((current) => [
      ...current,
      { id: optimisticId, role: "user", content: message },
    ]);
    try {
      // New accounts may not have a favorite yet. Persist the visible team before routing a question.
      if (user.favorite_team_id !== team.teamId) {
        const preferred = await api<{ user: User }>("/me/preferences", {
          method: "PATCH",
          body: JSON.stringify({ favorite_team_id: team.teamId }),
        });
        if (epoch !== accountEpoch() || ticket !== conversation.current)
          return false;
        setUser(preferred.user);
      }
      const result = await api<ChatResult>(
        "/chat",
        body({ session_id: sessionId, message }),
      );
      if (epoch !== accountEpoch() || ticket !== conversation.current)
        return false;
      setSessionId(result.session_id);
      setEntries((current) => [
        ...current,
        {
          ...result,
          id: result.message_id,
          role: "assistant",
          content: result.answer,
        },
      ]);
      setDraft((current) => (current === question ? "" : current));
      void refreshSessions();
      return true;
    } catch (error) {
      if (
        epoch === accountEpoch() &&
        ticket === conversation.current &&
        !isCancelled(error)
      ) {
        setError(error as Error);
        setEntries((current) =>
          current.filter((item) => item.id !== optimisticId),
        );
      }
      return false;
    } finally {
      if (epoch === accountEpoch() && ticket === conversation.current) {
        busy.current = false;
        setPending(false);
      }
    }
  }
  function ask(prompt = "") {
    if (prompt) setDraft(prompt);
    setOpenSignal((current) => current + 1);
  }
  function updateRating(id: string, rating: number) {
    setEntries((current) =>
      current.map((item) => (item.id === id ? { ...item, rating } : item)),
    );
  }
  return {
    user,
    checked,
    authError,
    checkAuth,
    team,
    teamBusy,
    changeTeam,
    login,
    logout,
    entries,
    sessions,
    sessionId,
    selectSession,
    newChat,
    pending,
    historyLoading,
    error,
    historyError,
    refreshSessions,
    draft,
    setDraft,
    sendQuestion,
    openSignal,
    ask,
    updateRating,
  };
}
type AppState = ReturnType<typeof useAppState>;
const Context = createContext<AppState | null>(null);
export function AppProvider({ children }: { children: React.ReactNode }) {
  const value = useAppState();
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useApp() {
  const value = useContext(Context);
  if (!value) throw new Error("AppProvider required");
  return value;
}
