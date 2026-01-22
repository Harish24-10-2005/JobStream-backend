"""
JobAI - Command Line Interface
Provides access to all agents via CLI commands
"""
import asyncio
import sys
import argparse
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.core.console import console


def create_parser():
    """Create argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="jobai",
        description="🚀 JobAI - AI-Powered Job Application Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli search "Python Developer" "Remote"
  python -m src.cli interview "SWE" "Google" --tech Python,Django
  python -m src.cli salary "Software Engineer" "San Francisco" --offer 150000
  python -m src.cli company "Google" --role "SDE"
  python -m src.cli track --report
  python -m src.cli track --add "Google" "SWE"
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ============================================
    # SEARCH - Full pipeline
    # ============================================
    search_parser = subparsers.add_parser(
        "search",
        help="🔍 Search and apply to jobs (full pipeline)"
    )
    search_parser.add_argument("query", help="Job title/keywords")
    search_parser.add_argument("location", help="Location (e.g., 'Remote', 'NYC')")
    search_parser.add_argument(
        "--min-score", type=int, default=70,
        help="Minimum match score (default: 70)"
    )
    search_parser.add_argument(
        "--no-resume", action="store_true",
        help="Skip resume tailoring"
    )
    search_parser.add_argument(
        "--no-cover", action="store_true",
        help="Skip cover letter generation"
    )
    
    # ============================================
    # INTERVIEW - Interview prep
    # ============================================
    interview_parser = subparsers.add_parser(
        "interview",
        help="🎯 Prepare for interviews"
    )
    interview_parser.add_argument("role", help="Job role")
    interview_parser.add_argument("company", help="Company name")
    interview_parser.add_argument(
        "--tech", default="",
        help="Tech stack (comma-separated)"
    )
    
    # ============================================
    # SALARY - Salary research
    # ============================================
    salary_parser = subparsers.add_parser(
        "salary",
        help="💰 Research salaries and negotiate"
    )
    salary_parser.add_argument("role", help="Job role")
    salary_parser.add_argument("location", help="Location")
    salary_parser.add_argument(
        "--offer", type=int, default=0,
        help="Current offer to negotiate"
    )
    
    # ============================================
    # COMPANY - Company research
    # ============================================
    company_parser = subparsers.add_parser(
        "company",
        help="🏢 Research companies"
    )
    company_parser.add_argument("name", help="Company name")
    company_parser.add_argument(
        "--role", default="",
        help="Target role for context"
    )
    
    # ============================================
    # RESUME - Resume tailoring
    # ============================================
    resume_parser = subparsers.add_parser(
        "resume",
        help="📄 Tailor resume for a job"
    )
    resume_parser.add_argument("role", help="Job role")
    resume_parser.add_argument("company", help="Company name")
    resume_parser.add_argument(
        "--description", default="",
        help="Job description text"
    )
    
    # ============================================
    # TRACK - Application tracker
    # ============================================
    track_parser = subparsers.add_parser(
        "track",
        help="📊 Manage job applications"
    )
    track_parser.add_argument(
        "--report", action="store_true",
        help="Show application report"
    )
    track_parser.add_argument(
        "--add", nargs=2, metavar=("COMPANY", "ROLE"),
        help="Add new application"
    )
    track_parser.add_argument(
        "--update", nargs=2, metavar=("COMPANY", "STATUS"),
        help="Update application status"
    )
    track_parser.add_argument(
        "--list", dest="list_apps", action="store_true",
        help="List all applications"
    )
    
    return parser


async def run_search(args):
    """Run full job search pipeline."""
    from src.workflows.job_manager import JobApplicationWorkflow
    
    workflow = JobApplicationWorkflow(
        use_resume_tailoring=not args.no_resume,
        use_cover_letter=not args.no_cover
    )
    
    await workflow.run(args.query, args.location, args.min_score)


async def run_interview(args):
    """Run interview prep."""
    from src.workflows.job_manager import StandaloneAgents
    
    tech_stack = [t.strip() for t in args.tech.split(",")] if args.tech else []
    await StandaloneAgents.interview_prep(args.role, args.company, tech_stack)


async def run_salary(args):
    """Run salary research."""
    from src.workflows.job_manager import StandaloneAgents
    
    await StandaloneAgents.salary_research(args.role, args.location, args.offer)


async def run_company(args):
    """Run company research."""
    from src.workflows.job_manager import StandaloneAgents
    
    await StandaloneAgents.company_research(args.name, args.role)


async def run_resume(args):
    """Run resume tailoring."""
    from src.workflows.job_manager import StandaloneAgents
    
    await StandaloneAgents.resume_tailor(args.role, args.company, args.description)


async def run_track(args):
    """Run tracker commands."""
    from src.workflows.job_manager import StandaloneAgents
    
    if args.report:
        await StandaloneAgents.tracker_report()
    elif args.add:
        company, role = args.add
        await StandaloneAgents.add_application(company, role)
    elif args.update:
        from src.agents.tracker_agent import update_application_status
        company, status = args.update
        update_application_status(company, new_status=status)
        console.success(f"Updated {company} to {status}")
    elif args.list_apps:
        from src.agents.tracker_agent import get_applications_by_status
        result = get_applications_by_status()
        apps = result.get("applications", [])
        console.header("📋 All Applications")
        for app in apps:
            status = app.get("status", "Unknown")
            console.info(f"• {app['company']} - {app['role']} [{status}]")
    else:
        # Default to report
        await StandaloneAgents.tracker_report()


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    console.header("🚀 JobAI")
    
    try:
        if args.command == "search":
            asyncio.run(run_search(args))
        elif args.command == "interview":
            asyncio.run(run_interview(args))
        elif args.command == "salary":
            asyncio.run(run_salary(args))
        elif args.command == "company":
            asyncio.run(run_company(args))
        elif args.command == "resume":
            asyncio.run(run_resume(args))
        elif args.command == "track":
            asyncio.run(run_track(args))
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        console.warning("\n🛑 Stopped by user")
    except Exception as e:
        console.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
