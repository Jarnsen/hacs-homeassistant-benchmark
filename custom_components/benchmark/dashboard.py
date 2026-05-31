def build_dashboard_yaml():
    return '''title: Home Assistant Benchmark
views:
  - title: Benchmark
    path: benchmark
    icon: mdi:speedometer
    cards:
      - type: entities
        title: Benchmark Steuerung
        entities:
          - sensor.benchmark_score
          - sensor.benchmark_progress
          - sensor.benchmark_status
          - sensor.benchmark_last_run
          - sensor.benchmark_active_profile
          - button.benchmark_start_light
          - button.benchmark_start_normal
          - button.benchmark_start_heavy

      - type: custom:mini-graph-card
        name: Benchmark Score
        entities:
          - sensor.benchmark_score

      - type: entities
        title: Einzelwerte
        entities:
          - sensor.benchmark_cpu_performance
          - sensor.benchmark_disk_write
          - sensor.benchmark_disk_read
          - sensor.benchmark_template_render
          - sensor.benchmark_restart_time
'''
