import csv
import json
import os
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


CSV_FILE = "emotion_log.csv"
HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8001"))


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def read_logs(limit=50):
    if not os.path.exists(CSV_FILE):
        return []

    rows = []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows[-limit:]


HTML_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Classroom Live Monitor</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { font-family: -apple-system, Arial, sans-serif; margin: 16px; background: #0f172a; color: #e2e8f0; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
    .card { background: #1e293b; border-radius: 10px; padding: 14px; }
    h1 { font-size: 20px; margin: 0 0 8px; }
    h2 { font-size: 16px; margin: 0 0 10px; color: #bfdbfe; }
    .kpi-title { color: #94a3b8; font-size: 12px; margin-bottom: 6px; }
    .kpi-value { font-size: 26px; font-weight: 700; }
    .muted { color: #94a3b8; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { padding: 8px; border-bottom: 1px solid #334155; text-align: left; }
    th { color: #93c5fd; }
    .pill { padding: 2px 8px; border-radius: 999px; background: #334155; }
    .charts { display: grid; grid-template-columns: 1fr; gap: 12px; }
    .chart-box { min-height: 300px; }
    @media (min-width: 980px) {
      .charts { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>
  <div class="grid">
    <div class="card">
      <h1>AI Classroom Live Monitor</h1>
      <div class="muted">Auto-refresh every 2s | Large-scale analytics view</div>
    </div>

    <div class="kpi-grid">
      <div class="card">
        <div class="kpi-title">Concentration Score</div>
        <div class="kpi-value" id="focusScore">0%</div>
      </div>
      <div class="card">
        <div class="kpi-title">Focused Probability</div>
        <div class="kpi-value" id="focusProb">0%</div>
      </div>
      <div class="card">
        <div class="kpi-title">Distracted Probability</div>
        <div class="kpi-value" id="distractProb">0%</div>
      </div>
      <div class="card">
        <div class="kpi-title">Samples Analysed</div>
        <div class="kpi-value" id="sampleCount">0</div>
      </div>
    </div>

    <div class="charts">
      <div class="card">
        <h2>Emotion Histogram (Counts)</h2>
        <div id="emotionHistogram" class="chart-box"></div>
      </div>
      <div class="card">
        <h2>Confidence Histogram</h2>
        <div id="confidenceHistogram" class="chart-box"></div>
      </div>
      <div class="card">
        <h2>Confidence Boxplot by Emotion</h2>
        <div id="confidenceBoxplot" class="chart-box"></div>
      </div>
      <div class="card">
        <h2>Emotion Probability Distribution</h2>
        <div id="emotionProbabilities" class="chart-box"></div>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top: 12px;">
    <h2>Latest Events</h2>
    <table>
      <thead>
        <tr>
          <th>Student</th>
          <th>Time</th>
          <th>Emotion</th>
          <th>Confidence</th>
          <th>Lecture</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <script>
    const focusedEmotions = new Set(['happy', 'neutral', 'surprise']);
    const distractedEmotions = new Set(['sad', 'angry', 'fear', 'disgust']);

    function toNumber(v) {
      const n = Number(v);
      return Number.isFinite(n) ? n : 0;
    }

    function mean(arr) {
      if (!arr.length) return 0;
      return arr.reduce((a, b) => a + b, 0) / arr.length;
    }

    function classifyEmotion(emotion) {
      const e = (emotion || '').toLowerCase();
      if (focusedEmotions.has(e)) return 'focused';
      if (distractedEmotions.has(e)) return 'distracted';
      return 'neutral';
    }

    function computeFocusMetrics(rows) {
      let focusedWeight = 0;
      let distractedWeight = 0;
      let neutralWeight = 0;

      rows.forEach((row) => {
        const conf = toNumber(row.Confidence);
        const cls = classifyEmotion(row.Emotion);
        if (cls === 'focused') focusedWeight += conf;
        else if (cls === 'distracted') distractedWeight += conf;
        else neutralWeight += conf;
      });

      const total = focusedWeight + distractedWeight + neutralWeight;
      if (total === 0) {
        return { score: 0, focusedProb: 0, distractedProb: 0 };
      }

      const focusedProb = (focusedWeight / total) * 100;
      const distractedProb = (distractedWeight / total) * 100;
      const score = Math.max(0, Math.min(100, focusedProb));
      return { score, focusedProb, distractedProb };
    }

    function renderEmotionHistogram(rows) {
      const counts = {};
      rows.forEach((r) => {
        const e = (r.Emotion || 'Unknown').toLowerCase();
        counts[e] = (counts[e] || 0) + 1;
      });
      const emotions = Object.keys(counts);
      const values = emotions.map((e) => counts[e]);
      Plotly.newPlot('emotionHistogram', [{
        x: emotions, y: values, type: 'bar', marker: { color: '#60a5fa' }
      }], {
        paper_bgcolor: '#1e293b',
        plot_bgcolor: '#1e293b',
        font: { color: '#e2e8f0' },
        margin: { l: 40, r: 20, t: 20, b: 40 }
      }, {displayModeBar: false, responsive: true});
    }

    function renderConfidenceHistogram(rows) {
      const conf = rows.map((r) => toNumber(r.Confidence) * 100);
      Plotly.newPlot('confidenceHistogram', [{
        x: conf,
        type: 'histogram',
        nbinsx: 10,
        marker: { color: '#34d399' }
      }], {
        xaxis: { title: 'Confidence %' },
        yaxis: { title: 'Frequency' },
        paper_bgcolor: '#1e293b',
        plot_bgcolor: '#1e293b',
        font: { color: '#e2e8f0' },
        margin: { l: 50, r: 20, t: 20, b: 45 }
      }, {displayModeBar: false, responsive: true});
    }

    function renderConfidenceBoxplot(rows) {
      const perEmotion = {};
      rows.forEach((r) => {
        const e = (r.Emotion || 'Unknown').toLowerCase();
        perEmotion[e] = perEmotion[e] || [];
        perEmotion[e].push(toNumber(r.Confidence) * 100);
      });

      const traces = Object.entries(perEmotion).map(([emotion, vals]) => ({
        y: vals,
        name: emotion,
        type: 'box',
        boxpoints: 'outliers'
      }));

      Plotly.newPlot('confidenceBoxplot', traces, {
        yaxis: { title: 'Confidence %' },
        paper_bgcolor: '#1e293b',
        plot_bgcolor: '#1e293b',
        font: { color: '#e2e8f0' },
        margin: { l: 50, r: 20, t: 20, b: 40 }
      }, {displayModeBar: false, responsive: true});
    }

    function renderEmotionProbabilities(rows) {
      const counts = {};
      rows.forEach((r) => {
        const e = (r.Emotion || 'Unknown').toLowerCase();
        counts[e] = (counts[e] || 0) + 1;
      });
      const labels = Object.keys(counts);
      const values = labels.map((k) => counts[k]);
      Plotly.newPlot('emotionProbabilities', [{
        labels, values, type: 'pie', textinfo: 'label+percent'
      }], {
        paper_bgcolor: '#1e293b',
        font: { color: '#e2e8f0' },
        margin: { l: 10, r: 10, t: 20, b: 20 }
      }, {displayModeBar: false, responsive: true});
    }

    function renderTable(rows) {
      const tbody = document.getElementById('rows');
      tbody.innerHTML = '';
      for (const row of rows.slice().reverse()) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${row.Student_ID || ''}</td>
          <td>${row.Time || ''}</td>
          <td><span class="pill">${row.Emotion || ''}</span></td>
          <td>${row.Confidence || ''}</td>
          <td>${row.Lecture_ID || ''}</td>
        `;
        tbody.appendChild(tr);
      }
    }

    function updateKpis(rows) {
      const { score, focusedProb, distractedProb } = computeFocusMetrics(rows);
      document.getElementById('focusScore').textContent = `${score.toFixed(1)}%`;
      document.getElementById('focusProb').textContent = `${focusedProb.toFixed(1)}%`;
      document.getElementById('distractProb').textContent = `${distractedProb.toFixed(1)}%`;
      document.getElementById('sampleCount').textContent = `${rows.length}`;
    }

    async function refresh() {
      const r = await fetch('/api/logs?limit=300');
      const data = await r.json();
      updateKpis(data);
      renderEmotionHistogram(data);
      renderConfidenceHistogram(data);
      renderConfidenceBoxplot(data);
      renderEmotionProbabilities(data);
      renderTable(data.slice(-40));
    }
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, HTML_PAGE.encode("utf-8"))
            return

        if parsed.path == "/api/logs":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["50"])[0])
            payload = json.dumps(read_logs(limit=limit)).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return

        self._send(404, b"Not Found", "text/plain; charset=utf-8")


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Dashboard running at http://127.0.0.1:{PORT}")
    print(f"Open on phone: http://{local_ip()}:{PORT}")
    server.serve_forever()
