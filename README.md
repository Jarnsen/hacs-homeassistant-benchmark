# Home Assistant Benchmark

A Home Assistant **custom integration** that measures and reports the real-world performance of your HA installation. It collects hardware info, measures Core & I/O latency, service-call performance, state-change throughput, template rendering speed, and more—then exposes all results as entities and computes a unified **Benchmark-Score** (0–10 000) so you can compare different systems.

---

## Features

- 🚀 **Uniform test suite** (always the same sequence of measurements)
- 🖥️ **Hardware info**  
  - Installations-methode (Core/OS/Supervised/etc.)  
  - CPU-Cores, Architektur, Virtualisierung, RAM, Speichermedium  
  - OS-Version & Uptime, HA-Version & Uptime, System-User  
- 📊 **Performance measurements**  
  - State-change throughput (ops/s)  
  - Disk-Read/Write (50 MB payload)  
  - EventBus P95 latency  
  - Automation P95 latency  
  - API P50/P95 latency  
  - Ping P50/P95 to Supervisor  
  - Service-Call P95 latency  
  - Recorder commit time  
  - Main-loop P95 latency  
  - Template rendering time  
- 🌟 **Unified Benchmark-Score** (0–10 000)  
- 🔄 **“Start Benchmark”** button in the Device page  
- 📜 **Logbook entries** for each run  
- 📈 Persisted history in `/.benchmark_history.json`

---

## Installation

1. Copy the `benchmark` folder into  
   ```text
   /config/custom_components/benchmark
