class BenchmarkPanel extends HTMLElement {
  set hass(hass) {
    if (!this._init) {
      this._init = true;
      this._hass = hass;
      this._conn = hass.connection;
      this._loadSettings();
      this._loadHistory();
    }
  }

  _loadSettings() {
    this._conn.sendMessage({ type: "benchmark/get_settings" }).then(r => {
      this._settings = r.result;
      this._render();
    });
  }

  _loadHistory() {
    this._conn.sendMessage({ type: "benchmark/get_history" }).then(r => {
      this._history = r.result;
      this._render();
    });
  }

  _startBenchmark() {
    this._conn.sendMessage({ type: "benchmark/start" }).then(r => {
      this._history.push(r.result);
      this._render();
    });
  }

  _saveSettings() {
    this._conn.sendMessage({
      type: "benchmark/update_settings",
      options: this._settings
    }).then(r => {
      this._settings = r.result;
      this._render();
    });
  }

  _render() {
    if (!this._settings || !this._history) return;
    const sorted = [...this._history]
      .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, 10);

    this.innerHTML = `
      <ha-card>
        <div class="card-content">
          <h1>Home Assistant Benchmark</h1>
          <mwc-button @click="${() => this._startBenchmark()}">
            Benchmark starten
          </mwc-button>

          <h2>UUID anzeigen</h2>
          <ha-form
            .schema=${[
              { name: "show_uuid", selector: { boolean: {} } }
            ]}
            .data=${this._settings}
            @value-changed=${e => this._settings = e.detail.value}
          ></ha-form>
          <mwc-button @click="${() => this._saveSettings()}">
            Speichern
          </mwc-button>

          <h2>Globale Bestenliste</h2>
          <table>
            <tr>
              <th>Rang</th><th>Hardware</th><th>P95 EventBus (ms)</th><th>Score</th>
            </tr>
            ${sorted.map((e, i) => `
              <tr data-index="${i}">
                <td>${i+1}</td>
                <td>${e.hardware.model}</td>
                <td>${(e.results?.eventbus_p95_ms||0).toFixed(1)}</td>
                <td>${(e.score||0).toFixed(1)}</td>
              </tr>`).join('')}
          </table>
        </div>
      </ha-card>
    `;

    this.querySelectorAll("tr[data-index]").forEach(row =>
      row.addEventListener("click", () => this._showDetail(sorted[row.dataset.index]))
    );
  }

  _showDetail(entry) {
    const items = Object.entries(entry.results||{})
      .map(([k,v]) => `<tr><td>${k}</td><td>${v.toFixed(2)}</td></tr>`).join("");
    this._hass.ui.dialog.open({
      title: `Details für ${entry.hardware.model}`,
      content: `
        <p><b>Timestamp:</b> ${entry.timestamp}</p>
        <p><b>HA-Version:</b> ${entry.ha_version}</p>
        <table>${items}</table>
      `
    });
  }
}

customElements.define("benchmark-panel", BenchmarkPanel);
