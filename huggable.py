#!/usr/bin/env python3
"""
Huggable - An enhanced CLI tool that uses Claude 4 Opus to create beautiful web applications
"""

import os
import sys
import json
import time
import argparse
import subprocess
import webbrowser
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import anthropic
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import signal
from functools import partial

# Try to import optional dependencies for better UX
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.panel import Panel
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

@dataclass
class AppConfig:
    """Configuration for generated app"""
    name: str
    description: str
    style: str
    created_at: str
    version: int = 1
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class ColoredOutput:
    """Fallback for colored output when rich is not available"""
    COLORS = {
        'green': '\033[92m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'yellow': '\033[93m',
        'purple': '\033[95m',
        'cyan': '\033[96m',
        'reset': '\033[0m',
        'bold': '\033[1m'
    }
    
    @staticmethod
    def print(message: str, color: str = None, bold: bool = False):
        if RICH_AVAILABLE and console:
            style = ""
            if color:
                style = color
            if bold:
                style = f"bold {style}"
            console.print(message, style=style)
        else:
            prefix = ""
            if color and color in ColoredOutput.COLORS:
                prefix += ColoredOutput.COLORS[color]
            if bold:
                prefix += ColoredOutput.COLORS['bold']
            suffix = ColoredOutput.COLORS['reset'] if prefix else ""
            print(f"{prefix}{message}{suffix}")

class TemplateManager:
    """Manages prompt templates for different app types"""
    
    DEFAULT_TEMPLATES = {
        "default": {
            "name": "Default",
            "prompt": """Create a complete, beautiful, and modern web application based on this description:

{description}

Requirements:
1. Create a single HTML file with embedded CSS and JavaScript
2. Use modern, responsive design with animations and transitions
3. Include interactive elements and smooth user experience
4. Use contemporary design trends (gradients, shadows, glassmorphism, etc.)
5. Ensure the app is fully functional, not just a mockup
6. Include proper semantic HTML and accessibility features
7. Make it visually stunning with attention to detail

Style preferences: {style}

Please provide ONLY the complete HTML code without any explanations or markdown formatting."""
        },
        "game": {
            "name": "Game",
            "prompt": """Create a complete, interactive web-based game based on this description:

{description}

Requirements:
1. Create a single HTML file with embedded CSS and JavaScript
2. Focus on smooth gameplay and responsive controls
3. Include score tracking, game states (start, play, game over)
4. Add sound effects using Web Audio API or simple audio elements
5. Ensure it works well on both desktop and mobile
6. Include instructions on how to play
7. Make it fun and engaging with polished animations

Style preferences: {style}

Please provide ONLY the complete HTML code without any explanations or markdown formatting."""
        },
        "dashboard": {
            "name": "Dashboard",
            "prompt": """Create a complete, data-rich dashboard application based on this description:

{description}

Requirements:
1. Create a single HTML file with embedded CSS and JavaScript
2. Use modern dashboard design with cards, charts, and metrics
3. Include interactive data visualizations (use Chart.js from CDN)
4. Add filtering and sorting capabilities where appropriate
5. Responsive grid layout that works on all screen sizes
6. Dark/light mode toggle
7. Clean, professional appearance with smooth transitions

Style preferences: {style}

Please provide ONLY the complete HTML code without any explanations or markdown formatting."""
        },
        "landing": {
            "name": "Landing Page",
            "prompt": """Create a stunning, conversion-focused landing page based on this description:

{description}

Requirements:
1. Create a single HTML file with embedded CSS and JavaScript
2. Eye-catching hero section with clear call-to-action
3. Smooth scrolling and parallax effects
4. Testimonials or social proof section
5. Contact form or email capture
6. Mobile-first responsive design
7. SEO-friendly structure
8. Engaging micro-animations and hover effects

Style preferences: {style}

Please provide ONLY the complete HTML code without any explanations or markdown formatting."""
        }
    }
    
    def __init__(self, custom_templates_path: Optional[Path] = None):
        self.templates = self.DEFAULT_TEMPLATES.copy()
        self.custom_templates_path = custom_templates_path
        if custom_templates_path and custom_templates_path.exists():
            self.load_custom_templates()
    
    def load_custom_templates(self):
        """Load custom templates from JSON file"""
        try:
            with open(self.custom_templates_path, 'r') as f:
                custom = json.load(f)
                self.templates.update(custom)
        except Exception as e:
            ColoredOutput.print(f"Warning: Could not load custom templates: {e}", "yellow")
    
    def get_template(self, template_name: str = "default") -> str:
        """Get a template by name"""
        return self.templates.get(template_name, self.templates["default"])["prompt"]
    
    def list_templates(self) -> List[Tuple[str, str]]:
        """List all available templates"""
        return [(k, v["name"]) for k, v in self.templates.items()]

class AppHistory:
    """Manages history of generated apps"""
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """Load history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def add_entry(self, config: AppConfig, path: Path):
        """Add a new entry to history"""
        entry = asdict(config)
        entry['path'] = str(path)
        self.history.append(entry)
        self._save_history()
    
    def _save_history(self):
        """Save history to file"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Get recent entries"""
        return self.history[-limit:][::-1]
    
    def search(self, query: str) -> List[Dict]:
        """Search history by name or description"""
        query_lower = query.lower()
        return [
            entry for entry in self.history
            if query_lower in entry['name'].lower() or 
               query_lower in entry['description'].lower()
        ]

class EnhancedServer(SimpleHTTPRequestHandler):
    """Enhanced HTTP server with hot reload capability"""
    
    def __init__(self, *args, watch_file: Path = None, **kwargs):
        self.watch_file = watch_file
        self.last_modified = watch_file.stat().st_mtime if watch_file else None
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests with auto-reload script injection"""
        if self.path == '/' and self.watch_file:
            # Inject auto-reload script
            with open(self.watch_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add auto-reload script before </body>
            reload_script = """
<script>
(function() {
    let lastModified = null;
    setInterval(async () => {
        try {
            const response = await fetch('/check-reload');
            const data = await response.json();
            if (lastModified && data.modified !== lastModified) {
                location.reload();
            }
            lastModified = data.modified;
        } catch (e) {}
    }, 1000);
})();
</script>
</body>"""
            content = content.replace('</body>', reload_script)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        elif self.path == '/check-reload':
            # Check if file has been modified
            current_mtime = self.watch_file.stat().st_mtime if self.watch_file else None
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'modified': current_mtime}).encode('utf-8'))
        else:
            super().do_GET()
    
    def log_message(self, format, *args):
        """Suppress server logs"""
        pass

class Huggable:
    def __init__(self, api_key: str, config_dir: Optional[Path] = None):
        """Initialize the enhanced Claude Frontend Builder"""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-opus-4-20250514"
        
        # Setup directories
        self.config_dir = config_dir or Path.home() / ".huggable"
        self.config_dir.mkdir(exist_ok=True)
        self.output_dir = Path("generated_apps")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.template_manager = TemplateManager(self.config_dir / "templates.json")
        self.history = AppHistory(self.config_dir / "history.json")
        
        # Server management
        self.server = None
        self.server_thread = None
    
    def generate_prompt(self, app_description: str, style_preferences: str = "", 
                       template: str = "default", additional_requirements: str = "") -> str:
        """Create a detailed prompt using templates"""
        template_prompt = self.template_manager.get_template(template)
        
        # Add any additional requirements
        if additional_requirements:
            template_prompt += f"\n\nAdditional requirements:\n{additional_requirements}"
        
        return template_prompt.format(
            description=app_description,
            style=style_preferences if style_preferences else "Modern, clean, and engaging"
        )
    
    def call_claude_api(self, prompt: str, retry_count: int = 3) -> str:
        """Call Claude API with retry logic"""
        for attempt in range(retry_count):
            try:
                if RICH_AVAILABLE:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Calling Claude 4 Opus...", total=None)
                        
                        message = self.client.messages.create(
                            model=self.model,
                            max_tokens=8192,
                            temperature=0.7,
                            messages=[{"role": "user", "content": prompt}]
                        )
                else:
                    ColoredOutput.print("🤖 Calling Claude 4 Opus to generate your web app...", "blue")
                    message = self.client.messages.create(
                        model=self.model,
                        max_tokens=8192,
                        temperature=0.7,
                        messages=[{"role": "user", "content": prompt}]
                    )
                
                return message.content[0].text
                
            except anthropic.RateLimitError:
                ColoredOutput.print(f"Rate limit hit. Waiting 60 seconds... (Attempt {attempt + 1}/{retry_count})", "yellow")
                time.sleep(60)
            except Exception as e:
                if attempt == retry_count - 1:
                    ColoredOutput.print(f"❌ Error calling Claude API: {str(e)}", "red", bold=True)
                    sys.exit(1)
                else:
                    ColoredOutput.print(f"Retry {attempt + 1}/{retry_count}: {str(e)}", "yellow")
                    time.sleep(5)
    
    def clean_html_response(self, response: str) -> str:
        """Clean and validate HTML response"""
        # Remove markdown code blocks if present
        if "```html" in response:
            start = response.find("```html") + 7
            end = response.rfind("```")
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.rfind("```")
            response = response[start:end].strip()
        
        # Ensure it starts with proper HTML
        if not response.strip().startswith("<!DOCTYPE html>") and not response.strip().startswith("<html"):
            response = "<!DOCTYPE html>\n" + response
        
        # Basic validation
        if "<html" not in response or "</html>" not in response:
            ColoredOutput.print("⚠️  Warning: Generated HTML might be incomplete", "yellow")
        
        return response.strip()
    
    def save_app(self, html_content: str, config: AppConfig) -> Path:
        """Save the generated HTML and metadata"""
        # Create app directory
        app_dir = self.output_dir / config.name.replace(" ", "_").lower()
        
        # Handle versioning
        if app_dir.exists():
            config.version = len(list(app_dir.glob("v*"))) + 1
        
        version_dir = app_dir / f"v{config.version}"
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Save HTML file
        html_file = version_dir / "index.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Save metadata
        meta_file = version_dir / "metadata.json"
        with open(meta_file, "w") as f:
            json.dump(asdict(config), f, indent=2)
        
        # Create symlink to latest version
        latest_link = app_dir / "latest"
        if latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(version_dir)
        
        # Add to history
        self.history.add_entry(config, html_file)
        
        ColoredOutput.print(f"✅ App saved to: {html_file}", "green", bold=True)
        return html_file
    
    def export_app(self, app_path: Path, export_path: Optional[Path] = None) -> Path:
        """Export app as a zip file"""
        if not export_path:
            export_path = app_path.parent / f"{app_path.parent.name}.zip"
        
        with zipfile.ZipFile(export_path, 'w') as zipf:
            for file in app_path.parent.rglob('*'):
                if file.is_file():
                    zipf.write(file, file.relative_to(app_path.parent.parent))
        
        ColoredOutput.print(f"📦 App exported to: {export_path}", "green")
        return export_path
    
    def run_server(self, app_path: Path, port: int = 8080, hot_reload: bool = True):
        """Run a local HTTP server with hot reload"""
        os.chdir(app_path.parent)
        
        # Setup server with hot reload
        if hot_reload:
            handler = partial(EnhancedServer, watch_file=app_path)
        else:
            handler = EnhancedServer
        
        self.server = HTTPServer(('localhost', port), handler)
        
        ColoredOutput.print(f"🚀 Server running at http://localhost:{port}", "green", bold=True)
        if hot_reload:
            ColoredOutput.print("♻️  Hot reload enabled - changes will auto-refresh", "cyan")
        ColoredOutput.print("Press Ctrl+C to stop the server", "yellow")
        
        # Open browser
        webbrowser.open(f'http://localhost:{port}')
        
        # Handle graceful shutdown
        def signal_handler(signum, frame):
            ColoredOutput.print("\n👋 Shutting down server...", "yellow")
            self.server.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            ColoredOutput.print("\n👋 Server stopped", "yellow")
            self.server.shutdown()
    
    def show_preview(self, html_content: str):
        """Show a preview of the generated HTML"""
        if RICH_AVAILABLE:
            # Extract title and first few style rules
            title_match = html_content.find("<title>")
            if title_match != -1:
                title_end = html_content.find("</title>", title_match)
                title = html_content[title_match+7:title_end]
                console.print(Panel(f"[bold cyan]Title:[/bold cyan] {title}", title="Preview"))
            
            # Show syntax highlighted snippet
            snippet = html_content[:500] + "..."
            syntax = Syntax(snippet, "html", theme="monokai", line_numbers=False)
            console.print(syntax)
        else:
            ColoredOutput.print("\n--- Preview ---", "cyan", bold=True)
            print(html_content[:500] + "...")
            ColoredOutput.print("--- End Preview ---\n", "cyan", bold=True)
    
    def interactive_mode(self):
        """Run in interactive mode with prompts"""
        ColoredOutput.print("\n🎨 Welcome to Huggable Interactive Mode!", "purple", bold=True)
        
        while True:
            try:
                # Get app details
                if RICH_AVAILABLE:
                    name = Prompt.ask("\n[bold cyan]App name[/bold cyan]")
                    description = Prompt.ask("[bold cyan]Description[/bold cyan]")
                    
                    # Show template options
                    table = Table(title="Available Templates")
                    table.add_column("Key", style="cyan")
                    table.add_column("Name", style="green")
                    
                    for key, name_str in self.template_manager.list_templates():
                        table.add_row(key, name_str)
                    
                    console.print(table)
                    template = Prompt.ask("[bold cyan]Template[/bold cyan]", default="default")
                    
                    style = Prompt.ask("[bold cyan]Style preferences[/bold cyan]", default="")
                    tags = Prompt.ask("[bold cyan]Tags (comma separated)[/bold cyan]", default="").split(",")
                    
                    preview = Confirm.ask("Show preview before saving?", default=True)
                    auto_run = Confirm.ask("Run server after creation?", default=True)
                else:
                    name = input("\nApp name: ")
                    description = input("Description: ")
                    
                    print("\nAvailable templates:")
                    for key, name_str in self.template_manager.list_templates():
                        print(f"  {key}: {name_str}")
                    
                    template = input("Template (default): ") or "default"
                    style = input("Style preferences: ")
                    tags_input = input("Tags (comma separated): ")
                    tags = [t.strip() for t in tags_input.split(",") if t.strip()]
                    
                    preview = input("Show preview before saving? (y/n): ").lower() == 'y'
                    auto_run = input("Run server after creation? (y/n): ").lower() == 'y'
                
                # Create app
                config = AppConfig(
                    name=name,
                    description=description,
                    style=style,
                    created_at=datetime.now().isoformat(),
                    tags=tags
                )
                
                prompt = self.generate_prompt(description, style, template)
                response = self.call_claude_api(prompt)
                html_content = self.clean_html_response(response)
                
                if preview:
                    self.show_preview(html_content)
                    if RICH_AVAILABLE:
                        if not Confirm.ask("Save this app?", default=True):
                            continue
                    else:
                        if input("Save this app? (y/n): ").lower() != 'y':
                            continue
                
                app_path = self.save_app(html_content, config)
                
                if auto_run:
                    self.run_server(app_path)
                
                # Ask if user wants to create another
                if RICH_AVAILABLE:
                    if not Confirm.ask("\nCreate another app?", default=True):
                        break
                else:
                    if input("\nCreate another app? (y/n): ").lower() != 'y':
                        break
                        
            except KeyboardInterrupt:
                ColoredOutput.print("\n\n👋 Goodbye!", "yellow")
                break
            except Exception as e:
                ColoredOutput.print(f"\n❌ Error: {str(e)}", "red")
                continue
    
    def create_app(self, description: str, name: str, style: str = "", 
                   template: str = "default", tags: List[str] = None,
                   auto_run: bool = True, hot_reload: bool = True,
                   show_preview: bool = False):
        """Main method to create a web app"""
        ColoredOutput.print(f"\n🎨 Creating web app: {name}", "purple", bold=True)
        ColoredOutput.print(f"📝 Description: {description}", "blue")
        ColoredOutput.print(f"🎯 Template: {template}", "cyan")
        
        # Create config
        config = AppConfig(
            name=name,
            description=description,
            style=style,
            created_at=datetime.now().isoformat(),
            tags=tags or []
        )
        
        # Generate prompt and call API
        prompt = self.generate_prompt(description, style, template)
        response = self.call_claude_api(prompt)
        
        # Clean and preview if requested
        html_content = self.clean_html_response(response)
        
        if show_preview:
            self.show_preview(html_content)
        
        # Save the app
        app_path = self.save_app(html_content, config)
        
        ColoredOutput.print(f"\n✨ Web app successfully created!", "green", bold=True)
        
        if auto_run:
            self.run_server(app_path, hot_reload=hot_reload)
        
        return app_path
    
    def list_apps(self, limit: int = 10):
        """List recently created apps"""
        recent = self.history.get_recent(limit)
        
        if not recent:
            ColoredOutput.print("No apps created yet!", "yellow")
            return
        
        if RICH_AVAILABLE:
            table = Table(title="Recent Apps")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="green", max_width=40)
            table.add_column("Created", style="yellow")
            table.add_column("Version", style="magenta")
            table.add_column("Path", style="blue", max_width=30)
            
            for entry in recent:
                table.add_row(
                    entry['name'],
                    entry['description'][:40] + "..." if len(entry['description']) > 40 else entry['description'],
                    entry['created_at'][:10],
                    str(entry.get('version', 1)),
                    "..." + entry['path'][-27:] if len(entry['path']) > 30 else entry['path']
                )
            
            console.print(table)
        else:
            ColoredOutput.print("\n=== Recent Apps ===", "cyan", bold=True)
            for i, entry in enumerate(recent, 1):
                print(f"\n{i}. {entry['name']}")
                print(f"   Description: {entry['description'][:50]}...")
                print(f"   Created: {entry['created_at'][:10]}")
                print(f"   Path: {entry['path']}")

def main():
    parser = argparse.ArgumentParser(
        description="Huggable - Enhanced web app generator using Claude 4 Opus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name "Todo App" --description "A modern todo list with dark mode"
  %(prog)s --name "Portfolio" --description "Personal portfolio site" --template landing
  %(prog)s --interactive  # Run in interactive mode
  %(prog)s --list  # List recent apps
  %(prog)s --name "Game" --description "Snake game" --template game --tags "game,retro"
        """
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env variable)",
        default=os.environ.get("ANTHROPIC_API_KEY")
    )
    
    # Mode arguments
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    mode_group.add_argument(
        "--list", "-l",
        action="store_true",
        help="List recently created apps"
    )
    
    # App creation arguments
    parser.add_argument(
        "--name", "-n",
        type=str,
        help="Name of the web app to create"
    )
    
    parser.add_argument(
        "--description", "-d",
        type=str,
        help="Description of what the web app should do"
    )
    
    parser.add_argument(
        "--style", "-s",
        type=str,
        default="",
        help="Style preferences (e.g., 'Dark mode, neon colors, cyberpunk')"
    )
    
    parser.add_argument(
        "--template", "-t",
        type=str,
        default="default",
        help="Template to use (default, game, dashboard, landing)"
    )
    
    parser.add_argument(
        "--tags",
        type=str,
        help="Comma-separated tags for the app"
    )
    
    # Server options
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Don't automatically run the server after creation"
    )
    
    parser.add_argument(
        "--no-hot-reload",
        action="store_true",
        help="Disable hot reload in development server"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to run the local server on (default: 8080)"
    )
    
    # Other options
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show preview of generated HTML before saving"
    )
    
    parser.add_argument(
        "--export", "-e",
        type=str,
        help="Export the app as a zip file to the specified path"
    )
    
    args = parser.parse_args()
    
    # Check for API key
    if not args.api_key:
        ColoredOutput.print("❌ Error: No API key provided!", "red", bold=True)
        ColoredOutput.print("Please set ANTHROPIC_API_KEY environment variable or use --api-key flag", "yellow")
        sys.exit(1)
    
    # Create the builder
    builder = Huggable(args.api_key)
    
    try:
        if args.interactive:
            # Run interactive mode
            builder.interactive_mode()
        elif args.list:
            # List recent apps
            builder.list_apps()
        elif args.name and args.description:
            # Create app from command line
            tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
            
            app_path = builder.create_app(
                description=args.description,
                name=args.name,
                style=args.style,
                template=args.template,
                tags=tags,
                auto_run=not args.no_run,
                hot_reload=not args.no_hot_reload,
                show_preview=args.preview
            )
            
            if args.export:
                builder.export_app(app_path, Path(args.export))
            
            if args.no_run:
                ColoredOutput.print(f"\n📁 App created at: {app_path}", "green")
                ColoredOutput.print(f"Run 'python -m http.server {args.port}' in {app_path.parent} to serve it", "yellow")
        else:
            # Show help if no valid mode selected
            parser.print_help()
            ColoredOutput.print("\n💡 Tip: Try running with --interactive for a guided experience!", "cyan")
            
    except KeyboardInterrupt:
        ColoredOutput.print("\n\n👋 Goodbye!", "yellow")
        sys.exit(0)
    except Exception as e:
        ColoredOutput.print(f"\n❌ Unexpected error: {str(e)}", "red", bold=True)
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
