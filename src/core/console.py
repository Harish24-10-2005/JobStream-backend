"""
Rich Console Output Utilities for JobAI Agents.
Provides colorful, structured terminal output formatting.
"""

import os
import sys
from typing import List, Optional, Dict, Any
from datetime import datetime

# ANSI Color Codes
class Colors:
    # Basic Colors
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Foreground Colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Background Colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


class Console:
    """
    Rich console output handler for JobAI.
    """
    
    # Box drawing characters
    BOX_TOP_LEFT = "╭"
    BOX_TOP_RIGHT = "╮"
    BOX_BOTTOM_LEFT = "╰"
    BOX_BOTTOM_RIGHT = "╯"
    BOX_HORIZONTAL = "─"
    BOX_VERTICAL = "│"
    BOX_CROSS = "┼"
    BOX_T_DOWN = "┬"
    BOX_T_UP = "┴"
    BOX_T_RIGHT = "├"
    BOX_T_LEFT = "┤"
    
    # Double box characters
    DBOX_TOP_LEFT = "╔"
    DBOX_TOP_RIGHT = "╗"
    DBOX_BOTTOM_LEFT = "╚"
    DBOX_BOTTOM_RIGHT = "╝"
    DBOX_HORIZONTAL = "═"
    DBOX_VERTICAL = "║"
    
    # Status symbols
    SYMBOL_SUCCESS = "✅"
    SYMBOL_ERROR = "❌"
    SYMBOL_WARNING = "⚠️"
    SYMBOL_INFO = "ℹ️"
    SYMBOL_SEARCH = "🔍"
    SYMBOL_BRAIN = "🧠"
    SYMBOL_ROCKET = "🚀"
    SYMBOL_STAR = "⭐"
    SYMBOL_CHECK = "✓"
    SYMBOL_CROSS = "✗"
    SYMBOL_ARROW = "→"
    SYMBOL_BULLET = "•"
    SYMBOL_SPARKLE = "✨"
    SYMBOL_TARGET = "🎯"
    SYMBOL_CHART = "📊"
    SYMBOL_LINK = "🔗"
    SYMBOL_CLOCK = "🕐"
    SYMBOL_USER = "👤"
    SYMBOL_COMPANY = "🏢"
    SYMBOL_MONEY = "💰"
    SYMBOL_SKILLS = "🛠️"
    SYMBOL_MATCH = "🎯"
    SYMBOL_SKIP = "⏭️"
    SYMBOL_CELEBRATE = "🎉"
    
    def __init__(self, width: int = 80):
        self.width = width
        self._enable_colors()
    
    def _enable_colors(self):
        """Enable ANSI colors on Windows."""
        if sys.platform == "win32":
            os.system("")  # Enable ANSI escape sequences on Windows
            # Try to set UTF-8 encoding for Windows console
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, Exception):
                pass
    
    def _safe_print(self, text: str):
        """Print text with safe encoding handling."""
        try:
            print(text)
        except UnicodeEncodeError:
            # Fallback: remove or replace non-ASCII characters
            safe_text = text.encode('ascii', errors='replace').decode('ascii')
            print(safe_text)
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text."""
        return f"{color}{text}{Colors.RESET}"
    
    def _center(self, text: str, width: int = None) -> str:
        """Center text within given width."""
        if width is None:
            width = self.width
        return text.center(width)
    
    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI codes for length calculation."""
        import re
        return re.sub(r'\033\[[0-9;]*m', '', text)
    
    def _visible_len(self, text: str) -> int:
        """Get visible length of text (excluding ANSI codes)."""
        return len(self._strip_ansi(text))
    
    # =========================================================================
    # BANNERS & HEADERS
    # =========================================================================
    
    def banner(self, title: str, subtitle: str = "", style: str = "double"):
        """Print a prominent banner."""
        if style == "double":
            tl, tr, bl, br = self.DBOX_TOP_LEFT, self.DBOX_TOP_RIGHT, self.DBOX_BOTTOM_LEFT, self.DBOX_BOTTOM_RIGHT
            h, v = self.DBOX_HORIZONTAL, self.DBOX_VERTICAL
        else:
            tl, tr, bl, br = self.BOX_TOP_LEFT, self.BOX_TOP_RIGHT, self.BOX_BOTTOM_LEFT, self.BOX_BOTTOM_RIGHT
            h, v = self.BOX_HORIZONTAL, self.BOX_VERTICAL
        
        inner_width = self.width - 2
        
        print()
        print(self._colorize(f"{tl}{h * inner_width}{tr}", Colors.BRIGHT_CYAN))
        print(self._colorize(f"{v}", Colors.BRIGHT_CYAN) + 
              self._colorize(self._center(title, inner_width), Colors.BOLD + Colors.BRIGHT_WHITE) + 
              self._colorize(f"{v}", Colors.BRIGHT_CYAN))
        
        if subtitle:
            print(self._colorize(f"{v}", Colors.BRIGHT_CYAN) + 
                  self._colorize(self._center(subtitle, inner_width), Colors.DIM + Colors.WHITE) + 
                  self._colorize(f"{v}", Colors.BRIGHT_CYAN))
        
        print(self._colorize(f"{bl}{h * inner_width}{br}", Colors.BRIGHT_CYAN))
        print()
    
    def header(self, title: str, icon: str = ""):
        """Print a section header."""
        prefix = f"{icon} " if icon else ""
        line = self.BOX_HORIZONTAL * (self.width - len(prefix) - len(title) - 4)
        print()
        print(self._colorize(f"{prefix}{title} ", Colors.BOLD + Colors.BRIGHT_YELLOW) + 
              self._colorize(line, Colors.DIM))
    
    def subheader(self, title: str):
        """Print a subsection header."""
        print(self._colorize(f"  {self.SYMBOL_ARROW} {title}", Colors.CYAN))
    
    def divider(self, char: str = "─", color: str = Colors.DIM):
        """Print a divider line."""
        print(self._colorize(char * self.width, color))
    
    # =========================================================================
    # STATUS MESSAGES
    # =========================================================================
    
    def success(self, message: str):
        """Print a success message."""
        self._safe_print(self._colorize(f"  {self.SYMBOL_SUCCESS} {message}", Colors.BRIGHT_GREEN))
    
    def error(self, message: str):
        """Print an error message."""
        self._safe_print(self._colorize(f"  {self.SYMBOL_ERROR} {message}", Colors.BRIGHT_RED))
    
    def warning(self, message: str):
        """Print a warning message."""
        self._safe_print(self._colorize(f"  {self.SYMBOL_WARNING} {message}", Colors.BRIGHT_YELLOW))
    
    def info(self, message: str):
        """Print an info message."""
        self._safe_print(self._colorize(f"  {self.SYMBOL_INFO} {message}", Colors.BRIGHT_BLUE))
    
    def step(self, number: int, total: int, message: str):
        """Print a step indicator."""
        progress = f"[{number}/{total}]"
        self._safe_print(self._colorize(f"  {progress} ", Colors.BRIGHT_MAGENTA) + 
              self._colorize(message, Colors.WHITE))
    
    # =========================================================================
    # BOXES & PANELS
    # =========================================================================
    
    def box(self, title: str, content: List[str], color: str = Colors.CYAN, icon: str = ""):
        """Print content in a bordered box."""
        inner_width = self.width - 4
        prefix = f"{icon} " if icon else ""
        
        # Top border with title
        title_display = f" {prefix}{title} "
        padding = inner_width - len(title_display)
        left_pad = padding // 2
        right_pad = padding - left_pad
        
        print(self._colorize(
            f"{self.BOX_TOP_LEFT}{self.BOX_HORIZONTAL * left_pad}{title_display}{self.BOX_HORIZONTAL * right_pad}{self.BOX_TOP_RIGHT}",
            color
        ))
        
        # Content lines
        for line in content:
            visible_len = self._visible_len(line)
            padding = inner_width - visible_len
            print(self._colorize(f"{self.BOX_VERTICAL} ", color) + 
                  line + " " * padding + 
                  self._colorize(f" {self.BOX_VERTICAL}", color))
        
        # Bottom border
        print(self._colorize(
            f"{self.BOX_BOTTOM_LEFT}{self.BOX_HORIZONTAL * (inner_width + 2)}{self.BOX_BOTTOM_RIGHT}",
            color
        ))
    
    def status_box(self, agent_name: str, status: str, details: Dict[str, Any], 
                   color: str = Colors.CYAN, icon: str = "🤖"):
        """Print a status box for an agent."""
        content = [
            self._colorize(f"Status: ", Colors.DIM) + self._colorize(status, Colors.BRIGHT_WHITE),
        ]
        
        for key, value in details.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value[:3])
                if len(details[key]) > 3:
                    value += f" (+{len(details[key]) - 3} more)"
            content.append(
                self._colorize(f"{key}: ", Colors.DIM) + self._colorize(str(value), Colors.WHITE)
            )
        
        self.box(agent_name, content, color, icon)
    
    # =========================================================================
    # TABLES
    # =========================================================================
    
    def table(self, headers: List[str], rows: List[List[str]], title: str = ""):
        """Print a formatted table."""
        if not rows:
            return
        
        # Calculate column widths
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(header)
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, self._visible_len(str(row[i])))
            col_widths.append(min(max_width + 2, 40))  # Cap at 40 chars
        
        # Print title
        if title:
            print()
            print(self._colorize(f"  {title}", Colors.BOLD + Colors.BRIGHT_WHITE))
        
        # Print header separator
        header_line = self.BOX_T_DOWN.join(self.BOX_HORIZONTAL * w for w in col_widths)
        print(self._colorize(f"  {self.BOX_TOP_LEFT}{header_line}{self.BOX_TOP_RIGHT}", Colors.DIM))
        
        # Print headers
        header_cells = []
        for i, header in enumerate(headers):
            cell = header.center(col_widths[i])
            header_cells.append(self._colorize(cell, Colors.BOLD + Colors.BRIGHT_CYAN))
        print(self._colorize(f"  {self.BOX_VERTICAL}", Colors.DIM) + 
              self._colorize(self.BOX_VERTICAL, Colors.DIM).join(header_cells) + 
              self._colorize(f"{self.BOX_VERTICAL}", Colors.DIM))
        
        # Print separator
        sep_line = self.BOX_CROSS.join(self.BOX_HORIZONTAL * w for w in col_widths)
        print(self._colorize(f"  {self.BOX_T_RIGHT}{sep_line}{self.BOX_T_LEFT}", Colors.DIM))
        
        # Print rows
        for row in rows:
            cells = []
            for i, cell in enumerate(row):
                cell_str = str(cell)
                if self._visible_len(cell_str) > col_widths[i] - 2:
                    cell_str = cell_str[:col_widths[i] - 5] + "..."
                padding = col_widths[i] - self._visible_len(cell_str)
                cells.append(" " + cell_str + " " * (padding - 1))
            print(self._colorize(f"  {self.BOX_VERTICAL}", Colors.DIM) + 
                  self._colorize(self.BOX_VERTICAL, Colors.DIM).join(cells) + 
                  self._colorize(f"{self.BOX_VERTICAL}", Colors.DIM))
        
        # Print bottom border
        bottom_line = self.BOX_T_UP.join(self.BOX_HORIZONTAL * w for w in col_widths)
        print(self._colorize(f"  {self.BOX_BOTTOM_LEFT}{bottom_line}{self.BOX_BOTTOM_RIGHT}", Colors.DIM))
    
    # =========================================================================
    # PROGRESS & METRICS
    # =========================================================================
    
    def progress_bar(self, current: int, total: int, label: str = "", width: int = 40):
        """Print a progress bar."""
        filled = int(width * current / total) if total > 0 else 0
        empty = width - filled
        bar = "█" * filled + "░" * empty
        percentage = int(100 * current / total) if total > 0 else 0
        
        color = Colors.BRIGHT_GREEN if percentage >= 70 else Colors.BRIGHT_YELLOW if percentage >= 40 else Colors.BRIGHT_RED
        
        print(f"  {label}" if label else "", end="")
        print(self._colorize(f"  {bar} ", Colors.DIM) + 
              self._colorize(f"{percentage}%", color))
    
    def score_display(self, score: int, label: str = "Match Score"):
        """Display a score with visual indicator."""
        if score >= 80:
            color = Colors.BRIGHT_GREEN
            indicator = "🟢 EXCELLENT"
        elif score >= 70:
            color = Colors.GREEN
            indicator = "🟢 GOOD"
        elif score >= 50:
            color = Colors.BRIGHT_YELLOW
            indicator = "🟡 MODERATE"
        else:
            color = Colors.BRIGHT_RED
            indicator = "🔴 LOW"
        
        bar_width = 20
        filled = int(bar_width * score / 100)
        bar = "▓" * filled + "░" * (bar_width - filled)
        
        print(self._colorize(f"  {label}: ", Colors.DIM) + 
              self._colorize(f"{score}%", color + Colors.BOLD) + 
              self._colorize(f" {bar} ", Colors.DIM) + 
              self._colorize(indicator, color))
    
    # =========================================================================
    # AGENT-SPECIFIC OUTPUTS
    # =========================================================================
    
    def scout_header(self):
        """Print ScoutAgent header."""
        self.header("SCOUT AGENT", self.SYMBOL_SEARCH)
        print(self._colorize("  Finding job opportunities on major ATS platforms...", Colors.DIM))
    
    def scout_results(self, query: str, location: str, urls: List[str]):
        """Print ScoutAgent results."""
        self.subheader(f"Search: \"{query}\" in \"{location}\"")
        print()
        
        if not urls:
            self.warning("No matching jobs found.")
            return
        
        self.success(f"Found {len(urls)} job listings")
        print()
        
        # Display URLs in a table
        rows = []
        for i, url in enumerate(urls[:10], 1):  # Show max 10
            # Extract domain and path
            domain = url.split("/")[2] if len(url.split("/")) > 2 else url
            path = "/".join(url.split("/")[3:])[:30] + "..." if len("/".join(url.split("/")[3:])) > 30 else "/".join(url.split("/")[3:])
            rows.append([str(i), domain, path])
        
        self.table(["#", "Platform", "Job Path"], rows, f"{self.SYMBOL_LINK} Job Listings")
        
        if len(urls) > 10:
            print(self._colorize(f"  ... and {len(urls) - 10} more jobs", Colors.DIM))
    
    def analyst_header(self, url: str):
        """Print AnalystAgent header."""
        self.header("ANALYST AGENT", self.SYMBOL_BRAIN)
        domain = url.split("/")[2] if len(url.split("/")) > 2 else url
        print(self._colorize(f"  Analyzing job posting from {domain}...", Colors.DIM))
    
    def analyst_results(self, role: str, company: str, salary: str, 
                        match_score: int, tech_stack: List[str], 
                        matching_skills: List[str], missing_skills: List[str],
                        analysis: str):
        """Print AnalystAgent results in a formatted panel."""
        print()
        
        # Job info box
        content = [
            self._colorize(f"{self.SYMBOL_USER} Role: ", Colors.DIM) + 
            self._colorize(role, Colors.BOLD + Colors.BRIGHT_WHITE),
            
            self._colorize(f"{self.SYMBOL_COMPANY} Company: ", Colors.DIM) + 
            self._colorize(company, Colors.BRIGHT_CYAN),
            
            self._colorize(f"{self.SYMBOL_MONEY} Salary: ", Colors.DIM) + 
            self._colorize(salary, Colors.BRIGHT_GREEN),
        ]
        
        if tech_stack:
            tech_display = ", ".join(tech_stack[:5])
            if len(tech_stack) > 5:
                tech_display += f" (+{len(tech_stack) - 5})"
            content.append(
                self._colorize(f"{self.SYMBOL_SKILLS} Tech: ", Colors.DIM) + 
                self._colorize(tech_display, Colors.BRIGHT_MAGENTA)
            )
        
        self.box("JOB DETAILS", content, Colors.BRIGHT_BLUE, self.SYMBOL_TARGET)
        print()
        
        # Match score
        self.score_display(match_score)
        print()
        
        # Skills comparison
        if matching_skills or missing_skills:
            skills_content = []
            if matching_skills:
                skills_content.append(
                    self._colorize(f"{self.SYMBOL_CHECK} Matching: ", Colors.GREEN) + 
                    self._colorize(", ".join(matching_skills[:5]), Colors.WHITE)
                )
            if missing_skills:
                skills_content.append(
                    self._colorize(f"{self.SYMBOL_CROSS} Missing: ", Colors.RED) + 
                    self._colorize(", ".join(missing_skills[:5]), Colors.DIM)
                )
            
            self.box("SKILLS ANALYSIS", skills_content, Colors.YELLOW, self.SYMBOL_CHART)
            print()
        
        # Analysis reasoning
        if analysis:
            print(self._colorize(f"  {self.SYMBOL_BULLET} Analysis: ", Colors.DIM) + 
                  self._colorize(analysis[:100] + "..." if len(analysis) > 100 else analysis, Colors.WHITE))
        
        print()
    
    def applier_header(self, url: str):
        """Print ApplierAgent header."""
        self.header("APPLIER AGENT", self.SYMBOL_ROCKET)
        print(self._colorize(f"  Starting browser automation for application...", Colors.DIM))
    
    def applier_status(self, status: str, detail: str = ""):
        """Print ApplierAgent status update."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(self._colorize(f"  [{timestamp}] ", Colors.DIM) + 
              self._colorize(f"{self.SYMBOL_ARROW} ", Colors.CYAN) + 
              self._colorize(status, Colors.WHITE) + 
              (self._colorize(f" - {detail}", Colors.DIM) if detail else ""))
    
    def applier_human_input(self, question: str):
        """Print human input prompt."""
        print()
        print(self._colorize(f"  {self.SYMBOL_WARNING} HUMAN INPUT REQUIRED", Colors.BOLD + Colors.BRIGHT_YELLOW))
        self.divider("·", Colors.YELLOW)
        print(self._colorize(f"  {question}", Colors.BRIGHT_WHITE))
        self.divider("·", Colors.YELLOW)
    
    def applier_complete(self, success: bool, message: str = ""):
        """Print ApplierAgent completion status."""
        print()
        if success:
            self.success(f"Application process completed! {self.SYMBOL_CELEBRATE}")
        else:
            self.error(f"Application failed: {message}")
    
    # =========================================================================
    # WORKFLOW OUTPUTS
    # =========================================================================
    
    def workflow_start(self, query: str, location: str):
        """Print workflow start banner."""
        self.banner(
            f"{self.SYMBOL_ROCKET} JobAI - Career Command Center {self.SYMBOL_ROCKET}",
            f"Autonomous Job Research & Auto-Apply Agent"
        )
        
        print(self._colorize("  Configuration:", Colors.BOLD))
        print(self._colorize(f"    {self.SYMBOL_SEARCH} Query:    ", Colors.DIM) + 
              self._colorize(query, Colors.BRIGHT_WHITE))
        print(self._colorize(f"    🌍 Location: ", Colors.DIM) + 
              self._colorize(location, Colors.BRIGHT_WHITE))
        print(self._colorize(f"    {self.SYMBOL_CLOCK} Started:  ", Colors.DIM) + 
              self._colorize(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), Colors.BRIGHT_WHITE))
        print()
        self.divider("═", Colors.BRIGHT_CYAN)
    
    def workflow_job_progress(self, current: int, total: int, url: str):
        """Print job processing progress."""
        print()
        self.divider("─", Colors.DIM)
        domain = url.split("/")[2] if len(url.split("/")) > 2 else url
        print(self._colorize(f"  {self.SYMBOL_TARGET} Processing Job ", Colors.BOLD) + 
              self._colorize(f"{current}/{total}", Colors.BRIGHT_MAGENTA) + 
              self._colorize(f" • {domain}", Colors.DIM))
        self.divider("─", Colors.DIM)
    
    def workflow_skip(self, reason: str, company: str, role: str, score: int):
        """Print job skip notification."""
        print(self._colorize(f"  {self.SYMBOL_SKIP} Skipping: ", Colors.YELLOW) + 
              self._colorize(f"{company} - {role}", Colors.WHITE) + 
              self._colorize(f" (Score: {score})", Colors.DIM))
    
    def workflow_match(self, company: str, role: str, score: int):
        """Print job match notification."""
        print(self._colorize(f"  {self.SYMBOL_MATCH} MATCH FOUND! ", Colors.BOLD + Colors.BRIGHT_GREEN) + 
              self._colorize(f"{company} - {role}", Colors.WHITE) + 
              self._colorize(f" (Score: {score})", Colors.BRIGHT_GREEN))
    
    def workflow_summary(self, total_jobs: int, analyzed: int, applied: int, skipped: int):
        """Print workflow completion summary."""
        print()
        self.divider("═", Colors.BRIGHT_CYAN)
        self.banner(f"{self.SYMBOL_SPARKLE} Workflow Complete {self.SYMBOL_SPARKLE}", "")
        
        rows = [
            ["Total Jobs Found", str(total_jobs), self.SYMBOL_SEARCH],
            ["Jobs Analyzed", str(analyzed), self.SYMBOL_BRAIN],
            ["Applications Submitted", str(applied), self.SYMBOL_ROCKET],
            ["Jobs Skipped", str(skipped), self.SYMBOL_SKIP],
        ]
        
        self.table(["Metric", "Count", ""], rows, f"{self.SYMBOL_CHART} Session Summary")
        print()
        
        print(self._colorize(f"  {self.SYMBOL_CLOCK} Completed: ", Colors.DIM) + 
              self._colorize(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), Colors.WHITE))
        print()
    
    def workflow_no_jobs(self):
        """Print no jobs found message."""
        print()
        self.warning("No matching jobs found for your search criteria.")
        print(self._colorize("  Try adjusting your search query or location.", Colors.DIM))
        print()


# Global console instance
console = Console()
