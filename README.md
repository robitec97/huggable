# 🧸 Huggable
Huggable is a free and open-source project inspired by Lovable, designed as a fun and educational experiment in low-code app development.

It’s a command-line tool powered by Claude 4 Opus (from Anthropic) that instantly transforms a short text description into a visually appealing, modern web application. The result is a complete, standalone HTML file—fully styled with CSS and JavaScript—without the need for frameworks or boilerplate code.

## ✨ Features

* Generates fully functional, single-page HTML apps
* Automatically applies modern design trends (glassmorphism, gradients, etc.)
* Responsive layout with animations and interactive elements
* Optionally runs a local server and opens the app in your browser

---

## 🚀 Installation

Make sure you have **Python 3.7+** installed.

1. Clone the repo or copy the `huggable.py` file.
2. Install the required Python package:

```bash
pip install anthropic
```

3. Get an API key from [Anthropic](https://www.anthropic.com/) and export it:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

---

## 🧪 Usage

Run the script using Python and provide a name and description for your app:

```bash
python huggable.py --name "Portfolio" --description "A personal portfolio site with a contact form"
```

You can also customize the style:

```bash
python huggable.py --name "Weather App" --description "Real-time weather app" --style "Futuristic, glassmorphism"
```

Or skip launching the server:

```bash
python huggable.py --name "Notes App" --description "A minimalist note-taking app" --no-run
```

To specify a different port (default is 8080):

```bash
python huggable.py --name "Music Player" --description "A web-based audio player" --port 3000
```

---

## 📁 Output

Generated apps are saved in the `generated_apps/` folder with this structure:

```
generated_apps/
└── portfolio/
    └── index.html
```

You can open `index.html` directly in your browser or run a local server:

```bash
cd generated_apps/portfolio
python -m http.server 8080
```

---

## 💬 Example Prompt

```
--name "Todo App"
--description "A responsive and animated todo list with light/dark mode toggle and persistent storage"
--style "Neon colors, floating elements, clean design"
```

---

## 🛑 Notes

* You must have an Anthropic API key to use Huggable.
* Only HTML output is supported (no external CSS/JS files).
* Claude's response is automatically cleaned from markdown formatting.

---

## 📜 License

This project is free to use under the MIT License.
