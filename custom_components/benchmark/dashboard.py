def build_dashboard_yaml():
    return '''title: Home Assistant Real World Benchmark
views:
  - title: Real World Benchmark
    path: real-world-benchmark
    icon: mdi:speedometer
    type: sections
    max_columns: 3
    sections:
      - type: grid
        cards:
          - type: heading
            heading: Real World Score
            icon: mdi:speedometer
          - type: gauge
            entity: sensor.benchmark_score
            name: Real World Score
            min: 0
            max: 10000
            severity:
              red: 0
              yellow: 3500
              green: 7000
          - type: tile
            entity: sensor.benchmark_status
            name: Status
          - type: tile
            entity: sensor.benchmark_progress
            name: Fortschritt
          - type: tile
            entity: button.benchmark_start_real_world_benchmark
            name: Start Real World Benchmark

      - type: grid
        cards:
          - type: heading
            heading: Ergebnisse
            icon: mdi:chart-box-outline
          - type: tile
            entity: sensor.benchmark_cpu_performance
            name: CPU Performance
          - type: tile
            entity: sensor.benchmark_disk_write
            name: Disk Schreiben
          - type: tile
            entity: sensor.benchmark_disk_read
            name: Disk Lesen
          - type: tile
            entity: sensor.benchmark_template_render
            name: Template Rendering
          - type: tile
            entity: sensor.benchmark_restart_time
            name: Restart Zeit

      - type: grid
        cards:
          - type: heading
            heading: System & Lastklasse
            icon: mdi:server
          - type: tile
            entity: sensor.benchmark_entity_count
            name: Entitäten
          - type: tile
            entity: sensor.benchmark_load_class
            name: Load Class
          - type: tile
            entity: sensor.benchmark_architecture
            name: Architektur
          - type: tile
            entity: sensor.benchmark_cpu_cores
            name: CPU Kerne
          - type: tile
            entity: sensor.benchmark_ram_total
            name: RAM

      - type: grid
        cards:
          - type: heading
            heading: Ranking & Export
            icon: mdi:trophy
          - type: tile
            entity: sensor.benchmark_local_ranking
            name: Lokaler Bestwert
          - type: tile
            entity: sensor.benchmark_worldlist_export
            name: Worldlist Export Status
          - type: tile
            entity: sensor.benchmark_ranking_issue
            name: Ranking Issue Status
          - type: tile
            entity: button.benchmark_export_worldlist
            name: Export Worldlist
          - type: tile
            entity: button.benchmark_create_ranking_issue
            name: Ranking Issue erstellen
          - type: tile
            entity: button.benchmark_create_issue
            name: Support Issue erstellen

  - title: Worldlist
    path: benchmark-worldlist
    icon: mdi:earth
    cards:
      - type: markdown
        title: Worldlist / Ranking
        content: >
          ## 🌍 Home Assistant Real World Benchmark Worldlist

          Die globale Liste wird später aus GitHub-Ranking-Issues oder einer öffentlichen JSON-Datei erzeugt.

          In Home Assistant siehst du bereits deine lokale Rankingliste über `sensor.benchmark_local_ranking`.

          **Ablauf:**

          1. Benchmark starten
          2. Worldlist exportieren
          3. Ranking Issue erstellen
          4. Inhalt aus `/config/benchmark_worldlist_export.json` in GitHub einfügen

      - type: picture
        image: https://raw.githubusercontent.com/Jarnsen/hacs-homeassistant-benchmark/main/images/worldmap-ranking.svg
        alt_text: Home Assistant Benchmark Worldmap

      - type: entities
        title: Lokales Ranking & Systemdaten
        entities:
          - sensor.benchmark_local_ranking
          - sensor.benchmark_score
          - sensor.benchmark_entity_count
          - sensor.benchmark_load_class
          - sensor.benchmark_architecture
          - sensor.benchmark_cpu_cores
          - sensor.benchmark_ram_total

      - type: entities
        title: Ranking Aktionen
        entities:
          - button.benchmark_start_real_world_benchmark
          - button.benchmark_export_worldlist
          - button.benchmark_create_ranking_issue
          - button.benchmark_create_issue
          - sensor.benchmark_worldlist_export
          - sensor.benchmark_ranking_issue

      - type: entities
        title: Aktuelles Ergebnis
        entities:
          - sensor.benchmark_cpu_performance
          - sensor.benchmark_disk_write
          - sensor.benchmark_disk_read
          - sensor.benchmark_template_render
          - sensor.benchmark_restart_time
          - sensor.benchmark_last_run
          - sensor.benchmark_active_profile
'''
