#!/usr/bin/env python3
"""
Huggable - A single file CLI tool that uses Claude 4 Opus to create beautiful web applications
"""

import os
import sys
import json
import time
import argparse
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, Optional
import anthropic
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

class Huggable:
    def __init__(self, api_key: str):
        """Initialize the Claude Frontend Builder with API key"""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-opus-4-20250514"
        self.output_dir = Path("generated_apps")
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_prompt(self, app_description: str, style_preferences: str = "") -> str:
        """Create a detailed prompt for Claude to generate a web app"""
        base_prompt = f"""Create a complete, beautiful, and modern web application based on this description:

{app_description}

Requirements:
1. Create a single HTML file with embedded CSS and JavaScript
2. Use modern, responsive design with animations and transitions
3. Include interactive elements and smooth user experience
4. Use contemporary design trends (gradients, shadows, glassmorphism, etc.)
5. Ensure the app is fully functional, not just a mockup
6. Include proper semantic HTML and accessibility features
7. Make it visually stunning with attention to detail

Style preferences: {style_preferences if style_preferences else "Modern, clean, and engaging"}

Please provide ONLY the complete HTML code without any explanations or markdown formatting."""
        
        return base_prompt
    
    def call_claude_api(self, prompt: str) -> str:
        """Call Claude API to generate the web app code"""
        try:
            print("🤖 Calling Claude 4 Opus to generate your web app...")
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"❌ Error calling Claude API: {str(e)}")
            sys.exit(1)
    
    def clean_html_response(self, response: str) -> str:
        """Clean the response to extract only HTML code"""
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
            
        return response.strip()
    
    def save_app(self, html_content: str, app_name: str) -> Path:
        """Save the generated HTML to a file"""
        # Create app directory
        app_dir = self.output_dir / app_name.replace(" ", "_").lower()
        app_dir.mkdir(exist_ok=True)
        
        # Save HTML file
        html_file = app_dir / "index.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"✅ App saved to: {html_file}")
        return html_file
    
    def run_server(self, app_path: Path, port: int = 8080):
        """Run a local HTTP server to serve the app"""
        os.chdir(app_path.parent)
        
        class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress server logs
        
        server = HTTPServer(('localhost', port), QuietHTTPRequestHandler)
        
        print(f"🚀 Server running at http://localhost:{port}")
        print("Press Ctrl+C to stop the server")
        
        # Open browser
        webbrowser.open(f'http://localhost:{port}')
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped")
            server.shutdown()
    
    def create_app(self, description: str, name: str, style: str = "", auto_run: bool = True):
        """Main method to create a web app"""
        print(f"\n🎨 Creating web app: {name}")
        print(f"📝 Description: {description}\n")
        
        # Generate prompt and call API
        prompt = self.generate_prompt(description, style)
        response = self.call_claude_api(prompt)
        
        # Clean and save the response
        html_content = self.clean_html_response(response)
        app_path = self.save_app(html_content, name)
        
        print(f"\n✨ Web app successfully created!")
        
        if auto_run:
            self.run_server(app_path)
        
        return app_path

def main():
    parser = argparse.ArgumentParser(
        description="Claude Frontend Builder - Create beautiful web apps using Claude 4 Opus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name "Todo App" --description "A modern todo list with dark mode"
  %(prog)s --name "Portfolio" --description "Personal portfolio site" --style "Minimalist, monochrome"
  %(prog)s --name "Game" --description "Simple puzzle game" --no-run
        """
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env variable)",
        default=os.environ.get("ANTHROPIC_API_KEY")
    )
    
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Name of the web app to create"
    )
    
    parser.add_argument(
        "--description",
        type=str,
        required=True,
        help="Description of what the web app should do"
    )
    
    parser.add_argument(
        "--style",
        type=str,
        default="",
        help="Style preferences (e.g., 'Dark mode, neon colors, cyberpunk')"
    )
    
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Don't automatically run the server after creation"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to run the local server on (default: 8080)"
    )
    
    args = parser.parse_args()
    
    # Check for API key
    if not args.api_key:
        print("❌ Error: No API key provided!")
        print("Please set ANTHROPIC_API_KEY environment variable or use --api-key flag")
        sys.exit(1)
    
    # Create the builder and generate app
    builder = Huggable(args.api_key)
    
    try:
        app_path = builder.create_app(
            description=args.description,
            name=args.name,
            style=args.style,
            auto_run=not args.no_run
        )
        
        if args.no_run:
            print(f"\n📁 App created at: {app_path}")
            print(f"Run 'python -m http.server {args.port}' in {app_path.parent} to serve it")
            
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()