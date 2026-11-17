# Exam Integrity & Academic Analytics Agent  (Project 5, AURA Track 8)

Team 16, Div B - Srushti Savadi, Rakshita Janadri, Abhishek E. Guide: Dr. Sharada Shiragudikar.
Principle: **AI assists, humans decide.** The system only flags results for a person to look at. It never concludes a cause and never changes a mark.

## What it does
Reads exam marks of 1,000 students (each with a KLE-style USN such as `01FE24BCS047`) **only through a read-only MCP server**,
runs four analyst agents at the same time (a swarm), and writes a plain-language report and an HTML dashboard.

```
Gradebook DB (SQLite, read-only) -> MCP server (10 tools, 0 write tools) -> 4 agents in parallel -> Report Writer -> dashboard -> a person
```

| Agent | MCP tool it calls | Question |
|---|---|---|
| Pattern Analyst | `check_outlier` | Is one mark far from the others? |
| Profile Analyst | `check_profile` | Is the whole set of a student's marks uncommon? |
| Distribution Analyst | `compare_sections` | Do two sections differ clearly? |
| Semester Memory Analyst | `compare_with_history` | Does this term differ from earlier terms? |
| Report Writer | (none) | Puts every finding into plain words |

## Requirements
Python 3.10+ (tested on 3.13). Install: `pip install -r requirements.txt`  (pandas, numpy, scipy, mcp>=2.0)

## Run (3 commands)
```
pip install -r requirements.txt
python main.py                      # builds the database on first run, runs the swarm, writes dashboard/dashboard.html (about 25 s)
python tests/test_full_system.py    # 23 tests, all should print PASS
```
Open `dashboard/dashboard.html` in any browser (no server needed). Optional: `python evaluation/evaluate.py`.

## Folder map
- `main.py` - entry point (swarm + report + dashboard)
- `mcp_server/gradebook_server.py` - **the MCP server** (10 read-only tools, access log)
- `agents/mcp_client.py` - **the MCP client** every agent uses (stdio transport)
- `agents/` - pattern, profile, distribution analysts and the report writer; `memory/semester_memory.py` - memory agent
- `tools/stats_tools.py` - the maths (Z-score, Welch t-test + Cohen's d, Mahalanobis profile check)
- `report/language.py` - careful-language templates and forbidden-word guard
- `audit/audit_log.py` - append-only audit log; logs are `audit/audit_log.jsonl` and `audit/mcp_access_log.jsonl`
- `data/` - real Kaggle CSV, database builder, `gradebook.db`
- `dashboard/` - HTML dashboard generator and template
- `tests/`, `evaluation/` - 23 tests and the label-free evaluation

## Honest limits
No ground-truth labels exist (so no "accuracy" is claimed); earlier terms are simulated by resampling; thresholds are textbook conventions
(|Z|>=3, p<0.05, d>=0.8, profile p<0.001); agents are rule-based, not LLM; USNs are synthetic.
