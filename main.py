"""main.py - run the whole system:  python main.py

Gradebook DB -> MCP server (read-only) -> 4 analyst agents (swarm, in parallel) -> Report Writer -> dashboard -> human
"""
# time measures how long a run takes
import time
# ThreadPoolExecutor runs the four agents at the same time
from concurrent.futures import ThreadPoolExecutor
# Path for file paths
from pathlib import Path

# builds the database on first run; DATABASE_PATH is where it lives
from data.generate_data import generate_gradebook, DATABASE_PATH
# the MCP client every agent uses
from agents.mcp_client import GradebookClient
# the four analysts and the report writer
from agents.pattern_analyst import PatternAnalyst
from agents.profile_analyst import ProfileAnalyst  # imports agents.profile_analyst: ProfileAnalyst
from agents.distribution_analyst import DistributionAnalyst  # imports agents.distribution_analyst: DistributionAnalyst
from memory.semester_memory import SemesterMemoryAnalyst  # imports memory.semester_memory: SemesterMemoryAnalyst
from agents.report_writer import ReportWriter  # imports agents.report_writer: ReportWriter
# the append-only audit log
from audit.audit_log import AuditLogger
# builds the HTML dashboard
from dashboard.generate_dashboard import build_dashboard

# file paths for the two logs and the dashboard
AUDIT_PATH = Path(__file__).parent / "audit" / "audit_log.jsonl"
MCP_ACCESS_PATH = Path(__file__).parent / "audit" / "mcp_access_log.jsonl"  # store a value in MCP_ACCESS_PATH
DASHBOARD_PATH = Path(__file__).parent / "dashboard" / "dashboard.html"  # store a value in DASHBOARD_PATH
# the term under review and the earlier terms used as memory
CURRENT_SEMESTER = "Current"
HISTORY_SEMESTERS = ["2024", "2025", "2026"]  # store a value in HISTORY_SEMESTERS


def ensure_database():  # Builds the gradebook database on the very first run
    """Builds the gradebook database on the very first run."""
    # missing -> build it from the real Kaggle CSV
    if not Path(DATABASE_PATH).exists():
        # tell the user
        print("[main] No gradebook database found - building it from the real Kaggle CSV...")
        # build
        generate_gradebook()
    else:
        # already there
        print(f"[main] Using gradebook database {DATABASE_PATH}")


def run_agent(agent, semester, history=None):  # One swarm member: opens ITS OWN MCP connection, runs the agent, closes the connection
    """One swarm member: opens ITS OWN MCP connection, runs the agent, closes the connection."""
    # open a private MCP client (this starts a private MCP server process)
    with GradebookClient(agent.name, db_path=DATABASE_PATH, access_log=MCP_ACCESS_PATH) as client:
        # the memory agent also needs the history terms; the others do not
        findings = agent.analyze(client, semester) if history is None else agent.analyze(client, semester, history)
        # return name, findings, number of MCP calls, tools discovered
        return agent.name, findings, client.calls_made, client.list_tool_names()


def run_swarm(audit_logger):  # Runs the four analyst agents in PARALLEL (the swarm)
    """Runs the four analyst agents in PARALLEL (the swarm)."""
    # (agent, history) pairs
    jobs = [(PatternAnalyst(audit_logger), None), (ProfileAnalyst(audit_logger), None),
            (DistributionAnalyst(audit_logger), None), (SemesterMemoryAnalyst(audit_logger), HISTORY_SEMESTERS)]  # continues the statement above
    # one worker thread per agent
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        # start every agent
        futures = [pool.submit(run_agent, agent, CURRENT_SEMESTER, hist) for agent, hist in jobs]
        # wait for all of them
        results = [f.result() for f in futures]
    # {agent name: (findings, calls, tools)}
    return {name: (findings, calls, tools) for name, findings, calls, tools in results}


def print_terminal_summary(report):  # Prints a readable summary (this is what the output screenshot shows)
    """Prints a readable summary (this is what the output screenshot shows)."""
    # shortcut
    s = report["summary"]
    # header
    print("\n" + "=" * 70 + "\nEXAM INTEGRITY & ACADEMIC ANALYTICS AGENT - RUN SUMMARY\n" + "=" * 70)
    # headline numbers
    print(f"Students checked               : {s['students_checked']}")
    print(f"Total checks performed         : {s['total_checks']}")  # run this step
    print(f"Students for a person to review: {s['students_to_review']}")  # run this step
    # per-type flag counts
    print("\nFlagged by check type:")
    for kind, count in s["flagged_by_type"].items():  # repeat for every item
        print(f"  - {kind}: {count}")  # run this step
    # the review list
    print("\nStudents to look at (by USN):")
    for item in report["review_list"]:  # repeat for every item
        # mark students flagged by two different checks
        print(f"  {item['usn']}" + ("  [two checks agree]" if item["both_checks_agree"] else ""))
        # the plain-language reasons
        for reason in item["reasons"]:
            print(f"      [FLAGGED] {reason['sentence']}")  # run this step
    # MCP facts
    mcp = report["mcp"]
    print(f"\nMCP gradebook server: {mcp['access']}, {mcp['write_tools']} write tools, {mcp['total_calls']} calls by {len(mcp['calls_by_agent'])} agents")  # run this step
    # where outputs are
    print(f"Audit log      : {AUDIT_PATH}\nMCP access log : {MCP_ACCESS_PATH}\nDashboard      : {DASHBOARD_PATH}\n" + "=" * 70 + "\n")


def main():  # Entry point
    """Entry point."""
    # start the stopwatch
    start = time.time()
    # make sure the database exists
    ensure_database()
    # one shared, thread-safe audit logger
    audit_logger = AuditLogger(AUDIT_PATH)
    # announce the swarm
    print("[main] Starting the agent swarm (4 agents, each connected to the MCP server)...")
    # run the four agents in parallel
    swarm = run_swarm(audit_logger)
    # per-agent progress lines
    for name, (findings, calls, _) in swarm.items():
        print(f"[main]   {name}: {len(findings)} checks via {calls} MCP calls")  # run this step
    # tools discovered over MCP (same for every agent)
    tools = next(iter(swarm.values()))[2]
    # facts about MCP use, for the report and dashboard
    mcp_info = {"server": "gradebook-readonly (Model Context Protocol, stdio)", "access": "read-only", "write_tools": 0, "tools": tools,
                "calls_by_agent": {n: c for n, (_, c, _) in swarm.items()}, "total_calls": sum(c for _, c, _ in swarm.values())}  # more fields of the dictionary being built above
    # the Report Writer merges everything
    report = ReportWriter().compile_report(swarm["Pattern Analyst"][0], swarm["Distribution Analyst"][0],
                                           swarm["Semester Memory Analyst"][0], swarm["Profile Analyst"][0], mcp_info)  # continues the statement above
    # print the terminal summary
    print_terminal_summary(report)
    # build the HTML dashboard
    build_dashboard(report, DASHBOARD_PATH)
    # finish
    print(f"[main] Dashboard written to {DASHBOARD_PATH} - open it in any web browser. (run took {time.time() - start:.0f}s)")


# run only when executed directly
if __name__ == "__main__":
    # go
    main()
