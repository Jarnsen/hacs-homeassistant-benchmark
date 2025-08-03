class BenchmarkPanel extends HTMLElement {
  set hass(hass) {
    if (this._inited) return;
    this._inited = true;
    this._hass = hass;
    this._conn = hass.connection;
    this._loadHistory();
    this._render();
  }

  _loadHistory() {
    this._conn.sendMessage({ type: "benchmark/get_history" })
      .then(r => { this._history = r.result || []; this._render(); });
  }

  _start() {
    this._conn.sendMessage({ type: "benchmark/start" })
      .then(r => {
        this._history = this._history || [];
        this._history.push(r.result);
        this._render();
      });
  }

  _render() {
    const hist = this._history || [];
    this.innerHTML = `
      <ha-card>
        <div class="card-content">
          <h1>Benchmark</h1>
          <mwc-button @click="${() => this._start()}">Benchmark starten</mwc-button>
          <h2>Verlauf</h2>
          <table>
            <tr><th>Datum</th><th>Cores</th><th>RAM (MB)</th></tr>
            ${hist.map(h => `
              <tr>
                <td>${h.timestamp}</td>
                <td>${h.hardware.cpu_cores}</td>
                <td>${h.hardware.total_ram_mb}</td>
              </tr>`).join('')}
          </table>
        </div>
      </ha-card>
    `;
  }
}

customElements.define('benchmark-panel', BenchmarkPanel);
