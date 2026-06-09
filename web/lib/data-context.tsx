"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";

// ── Types ──
export interface ScoreEntry {
  userId: string; username: string; avatarUrl: string | null;
  activePoints: number; sharerPoints: number;
  researcherPoints: number; collaboratorPoints: number;
  dragonBalls: number; totalPoints: number;
  dragonBallReason?: string;
}
export interface ScoresData {
  scores: ScoreEntry[]; dragonBallCount: number;
}
export interface Member {
  name: string; total: number; last_1month: number;
  last_3month: number; last_6month: number;
  last_seen: string | null; tag: string;
}
export interface Stats {
  total_messages: number; total_speakers: number;
  total_members: number; never_spoken: number;
  active_1month: number; tag_distribution: Record<string, number>;
  members: Member[]; myWxid: string | null; generated_at?: string;
}
export interface GroupInfo { id: string; name: string; }
export interface RewardItem {
  id: string; name: string; type: "merch" | "physical" | "lottery";
  costPoints: number; stock: number; description: string | null; imageUrl: string | null;
}
export interface RedemptionItem {
  id: string; rewardName: string; rewardType: string; pointsSpent: number; status: string; createdAt: string;
}

type DataContextType = {
  scores: ScoresData | null;
  stats: Stats | null;
  groups: GroupInfo[];
  groupId: string;
  setGroupId: (id: string) => void;
  loading: boolean;
  refresh: () => void;
  // Rewards
  rewards: RewardItem[];
  myPoints: number;
  redemptions: RedemptionItem[];
  rewardsLoading: boolean;
  refreshRewards: () => void;
};

const DataContext = createContext<DataContextType>({
  scores: null, stats: null, groups: [], groupId: "", setGroupId: () => {},
  loading: true, refresh: () => {},
  rewards: [], myPoints: 0, redemptions: [], rewardsLoading: true, refreshRewards: () => {},
});

export function DataProvider({ children }: { children: ReactNode }) {
  const [scores, setScores] = useState<ScoresData | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [groups, setGroups] = useState<GroupInfo[]>([]);
  const [groupId, setGroupId] = useState("");
  const [loading, setLoading] = useState(true);
  const [fetched, setFetched] = useState(false);

  // Rewards state
  const [rewards, setRewards] = useState<RewardItem[]>([]);
  const [myPoints, setMyPoints] = useState(0);
  const [redemptions, setRedemptions] = useState<RedemptionItem[]>([]);
  const [rewardsLoading, setRewardsLoading] = useState(true);
  const [rewardsFetched, setRewardsFetched] = useState(false);

  const fetchAll = useCallback(async (gid?: string) => {
    const g = gid || groupId;
    if (!g && !fetched) {
      try {
        const gr = await fetch("/api/stats");
        const gd = await gr.json();
        if (gd.groups?.length > 0) {
          setGroups(gd.groups);
          const firstId = gd.groups[0].id;
          setGroupId(firstId);
          const [sr, mr] = await Promise.all([
            fetch("/api/scores"),
            fetch(`/api/stats?groupId=${firstId}`),
          ]);
          setScores(await sr.json());
          setStats(await mr.json());
        }
      } catch (e) { console.error("Data fetch failed", e); }
      setLoading(false);
      setFetched(true);

      // Also fetch rewards
      try {
        const [rr, dr] = await Promise.all([
          fetch("/api/rewards"),
          fetch("/api/redemptions"),
        ]);
        const [rd, dd] = await Promise.all([rr.json(), dr.json()]);
        setRewards(rd.rewards || []);
        setMyPoints(rd.myPoints || 0);
        setRedemptions(dd.redemptions || []);
      } catch (e) { console.error("Rewards fetch failed", e); }
      setRewardsLoading(false);
      setRewardsFetched(true);
      return;
    }

    setLoading(true);
    try {
      const targetGid = gid || g;
      const [sr, mr] = await Promise.all([
        fetch("/api/scores"),
        fetch(`/api/stats?groupId=${targetGid}`),
      ]);
      const [scoresJson, statsJson] = await Promise.all([sr.json(), mr.json()]);
      setScores(scoresJson);
      setStats(statsJson);
      if (statsJson.groups) setGroups(statsJson.groups);
    } catch (e) { console.error("Data refresh failed", e); }
    setLoading(false);
    setFetched(true);
  }, [groupId, fetched]);

  const fetchRewards = useCallback(async () => {
    setRewardsLoading(true);
    try {
      const [rr, dr] = await Promise.all([
        fetch("/api/rewards"),
        fetch("/api/redemptions"),
      ]);
      const [rd, dd] = await Promise.all([rr.json(), dr.json()]);
      setRewards(rd.rewards || []);
      setMyPoints(rd.myPoints || 0);
      setRedemptions(dd.redemptions || []);
    } catch (e) { console.error("Rewards refresh failed", e); }
    setRewardsLoading(false);
    setRewardsFetched(true);
  }, []);

  useEffect(() => { fetchAll(); }, []);

  const refresh = useCallback(() => {
    setFetched(false);
    fetchAll();
  }, [fetchAll]);

  const refreshRewards = useCallback(() => {
    setRewardsFetched(false);
    fetchRewards();
  }, [fetchRewards]);

  return (
    <DataContext.Provider value={{
      scores, stats, groups, groupId, setGroupId, loading, refresh,
      rewards, myPoints, redemptions, rewardsLoading, refreshRewards,
    }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData() { return useContext(DataContext); }
