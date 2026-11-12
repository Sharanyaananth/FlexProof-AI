import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiRequest } from "../api";

type LivePoint = {
  time: string;
  mode: string;
  reading: { battery_soc: number; flexible_compute_mw: number; critical_load_mw: number; grid_import_mw: number; source: string };
  decision: { rafc_v_promise_mw: number; rafc_v_proven_reliability: number | null; baseline_promise_mw: number; requested_mw: number };
};

type Mode = "realtime" | "demo";

const MAX_POINTS = 60;
const UPDATE_SECONDS: Record<Mode, number> = { realtime: 10, demo: 2 };
const MODE_TEXT: Record<Mode, string> = {
  realtime: "real clock time, a new reading every 10 seconds",
  demo: "fast-forward, each update = 15 minutes (a full day in about 3 minutes)",
};

export default function LiveDashboard() {
  const [mode, setMode] = useState<Mode>("realtime");
  const [points, setPoints] = useState<LivePoint[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);

  async function start(selected: Mode = mode) {
    setError("");
    try {
      await apiRequest(`/live/start?mode=${selected}`, { method: "POST" });
      setPoints([]);
      setRunning(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reach the API.");
    }
  }

  function changeMode(selected: Mode) {
    setMode(selected);
    setRunning(false);
    setPoints([]);
  }

  useEffect(() => {
    if (!running) return;
    const tick = async () => {
      if (busy.current) return;
      busy.current = true;
      try {
        const point = await apiRequest<LivePoint>("/live/next");
        setPoints((old) => [...old, point].slice(-MAX_POINTS));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Live feed error.");
        setRunning(false);
      } finally {
        busy.current = false;
      }
    };
    tick();
    const timer = setInterval(tick, UPDATE_SECONDS[mode] * 1000);
    return () => clearInterval(timer);
  }, [running, mode]);

  const latest = points[points.length - 1];
  const previous = points[points.length - 2];
  const trend = latest && previous
    ? latest.decision.rafc_v_promise_mw > previous.decision.rafc_v_promise_mw ? " ▲"
      : latest.decision.rafc_v_promise_mw < previous.decision.rafc_v_promise_mw ? " ▼" : ""
    : "";
  const chartData = points.map((p) => ({
    time: p.time,
    rafc: p.decision.rafc_v_promise_mw,
    baseline: p.decision.baseline_promise_mw,
    requested: p.decision.requested_mw,
    soc: Math.round(p.reading.battery_soc * 1000) / 10,
    flexible: p.reading.flexible_compute_mw,
  }));

  return <div className="planner-page">
    <p className="eyebrow">REAL-TIME</p>
    <h1>Live Commitment Dashboard</h1>
    <p className="subtitle">Facility readings arrive continuously; with every reading RAFC-V re-decides the largest promise it can prove at 95% reliability, including safe recovery.</p>

    <section className="panel planner-panel">
      <div className="panel-header">
        <div><h2>Live feed</h2><p>Source: {latest?.reading.source ?? "simulated facility telemetry"} · {MODE_TEXT[mode]}</p></div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 600 }}>Mode
            <select value={mode} onChange={(e) => changeMode(e.target.value as Mode)} style={{ padding: "8px 10px", borderRadius: 8 }}>
              <option value="realtime">Real time</option>
              <option value="demo">Fast-forward (demo)</option>
            </select>
          </label>
          {running
            ? <button type="button" className="primary-button" onClick={() => setRunning(false)}>Pause</button>
            : <button type="button" className="primary-button" onClick={points.length ? () => setRunning(true) : () => start()}>{points.length ? "Resume" : "Start live feed"}</button>}
          {points.length > 0 && <button type="button" className="primary-button" onClick={() => start()}>Restart</button>}
        </div>
      </div>
      {error && <div className="notice" role="alert">{error}</div>}
      {!latest && !error && <div className="notice">Choose a mode and press “Start live feed” to begin.</div>}
      {latest && <div className="simulation-metrics">
        <Metric label={mode === "realtime" ? "Time (live)" : "Time (simulated)"} value={latest.time} />
        <Metric label="Battery charge" value={`${(latest.reading.battery_soc * 100).toFixed(1)} %`} />
        <Metric label="Flexible compute" value={`${latest.reading.flexible_compute_mw.toFixed(2)} MW`} />
        <Metric label="RAFC-V safe promise" value={`${latest.decision.rafc_v_promise_mw.toFixed(1)} MW${trend}`} />
        <Metric label="Proven reliability" value={latest.decision.rafc_v_proven_reliability == null ? "N/A" : `${(latest.decision.rafc_v_proven_reliability * 100).toFixed(1)} %`} />
        <Metric label="Baseline promise" value={`${latest.decision.baseline_promise_mw.toFixed(1)} MW`} />
      </div>}
    </section>

    {chartData.length > 0 && <section className="panel planner-results">
      <div className="simulation-chart"><h3>Promise to the grid (MW)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis domain={[0, 6]} />
            <Tooltip />
            <Legend />
            <Line type="stepAfter" dataKey="requested" name="Grid request" stroke="#94a3b8" strokeDasharray="5 5" dot={false} isAnimationActive={false} />
            <Line type="stepAfter" dataKey="baseline" name="Baseline promise" stroke="#5b7fbf" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="stepAfter" dataKey="rafc" name="RAFC-V safe promise" stroke="#2e8b6e" strokeWidth={3} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="simulation-chart"><h3>Battery charge (%) and flexible compute (MW)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis yAxisId="soc" domain={[15, 50]} />
            <YAxis yAxisId="flex" orientation="right" domain={[0, 5]} />
            <Tooltip />
            <Legend />
            <Line yAxisId="soc" type="monotone" dataKey="soc" name="Battery charge (%)" stroke="#2563eb" strokeWidth={3} dot={false} isAnimationActive={false} />
            <Line yAxisId="flex" type="stepAfter" dataKey="flexible" name="Flexible compute (MW)" stroke="#d5a728" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="simulation-disclaimer">Readings are simulated until a real data source is connected. Promises are calibration evidence, not utility certification.</p>
    </section>}
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="simulation-metric"><span>{label}</span><strong>{value}</strong></div>;
}