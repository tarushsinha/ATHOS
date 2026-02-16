# Deferred Engineering & Scaling To-Dos

Legend:
🏗 Before GCP  
📈 Before 1K Users  
🚀 Before 10K Users  

---

## 🧱 Data & Database Layer

| Area | Current State (MVP) | Later Upgrade | Why It Matters | When |
|------|-------------------|--------------|---------------|------|
| updated_at handling | SQLAlchemy/app-managed | Postgres trigger-based updates | Enforces correctness across all writers | 🏗 |
| Deletes | Hard deletes | Soft deletes (deleted_at) | Auditability & recovery | 📈 |
| User isolation | App-layer filters | Postgres Row-Level Security (RLS) | Zero-trust multi-tenant security | 🏗 |
| Indexing | Minimal | Composite/workload indexes | Performance at scale | 📈 |
| Migrations safety | Manual | CI checks + zero-downtime strategy | Prevent prod breakage | 🏗 |
| Data versioning | Overwrites | Versioned audit tables | Track edits & rollback | 🚀 |

---

## 🔐 Auth & Security

| Area | Current State | Later Upgrade | Why It Matters | When |
|------|-------------|-------------|---------------|------|
| Password recovery | Not implemented | Reset tokens + expiry | Account safety | 📈 |
| JWT sessions | Access token only | Refresh tokens + revocation | Secure long sessions | 📈 |
| Rate limiting | None | Per-IP/user throttles | Abuse protection | 📈 |
| Secrets | .env | GCP Secret Manager | Prevent leaks | 🏗 |
| MFA | None | Optional MFA | Enterprise security | 🚀 |

---

## 🔄 Integrations & Data Ingestion

| Area | Current State | Later Upgrade | Why It Matters | When |
|------|-------------|-------------|---------------|------|
| OAuth token storage | DB | Secret Manager + encryption | Credential safety | 🏗 |
| Data imports | Synchronous | Async pipelines | Reliability | 📈 |
| Deduplication | Basic | Idempotency keys | Prevent duplicates | 📈 |
| Retries | None | Backoff jobs | Resilience | 📈 |

---

## ⚙️ Infrastructure & Scaling

| Area | Current State | Later Upgrade | Why It Matters | When |
|------|-------------|-------------|---------------|------|
| Database | Docker Postgres | Cloud SQL | Reliability | 🏗 |
| Connections | Direct | PgBouncer/pool tuning | Prevent overload | 📈 |
| Caching | None | Redis | Performance | 📈 |
| Background jobs | Inline | Workers/queues | Non-blocking ops | 📈 |
| Observability | Basic logs | Metrics + tracing | Debuggability | 📈 |
| API versioning | Informal | Strict /v1, /v2 | Compatibility | 📈 |

---

## 📊 Product & Analytics

| Area | Current State | Later Upgrade | Why It Matters | When |
|------|-------------|-------------|---------------|------|
| Recommendations | Inline logic | Versioned engine | Evolution + A/B testing | 🚀 |
| Muscle taxonomy | Static | Extensible/versioned | Custom workouts | 🚀 |
| Analytics | Live queries | Precomputed views | Speed | 📈 |
| Reporting | Minimal | Dashboards + exports | UX | 📈 |

---

## 🚀 Deployment & Ops

| Area | Current State | Later Upgrade | Why It Matters | When |
|------|-------------|-------------|---------------|------|
| Deployments | Manual | CI/CD pipelines | Safe releases | 🏗 |
| Backups | None | Automated snapshots | Disaster recovery | 🏗 |
| Rollbacks | Manual | Versioned infra + migrations | Safety | 🏗 |