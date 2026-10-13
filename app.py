
import re
import requests
import gradio as gr
from collections import Counter
from urllib.parse import urlparse

API = "https://api.github.com"
SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv",
    "__pycache__", "dist", "build", ".next", "vendor"
}
MAX_FILES = 80
MAX_FILE_CHARS = 30000

LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java",
    ".cpp": "C++", ".c": "C", ".cs": "C#", ".go": "Go",
    ".rs": "Rust", ".php": "PHP", ".rb": "Ruby",
    ".html": "HTML", ".css": "CSS", ".sql": "SQL", ".sh": "Shell"
}

CODE_EXTENSIONS = set(LANGUAGES) | {
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt"
}

def github_get(path, params=None):
    response = requests.get(
        API + path,
        params=params,
        headers={"Accept": "application/vnd.github+json"},
        timeout=25
    )

    if response.status_code == 404:
        raise ValueError(
            "Repository or branch not found. Check that the repository is public."
        )
    if response.status_code == 403:
        raise ValueError(
            "GitHub API rate limit reached. Please wait and try again."
        )

    response.raise_for_status()
    return response.json()


def parse_url(url):
    parsed = urlparse((url or "").strip())

    if parsed.scheme not in ("https", "http"):
        raise ValueError("Enter a complete GitHub URL starting with https://")

    if parsed.hostname != "github.com":
        raise ValueError("Please enter a URL from github.com.")

    parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(parts) != 2:
        raise ValueError(
            "Use this format: https://github.com/owner/repository"
        )

    owner, repo = parts
    repo = repo.removesuffix(".git")

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner):
        raise ValueError("Invalid GitHub owner name.")

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository name.")

    return owner, repo


def fetch_file(owner, repo, branch, path):
    from urllib.parse import quote

    url = (
        f"https://raw.githubusercontent.com/{owner}/{repo}/"
        f"{quote(branch, safe='/')}/{quote(path, safe='/')}"
    )

    response = requests.get(url, timeout=20)

    if response.status_code != 200:
        return ""

    return response.text[:MAX_FILE_CHARS]


def analyze_repository(url, progress=gr.Progress()):
    owner, repo = parse_url(url)

    progress(0.1, desc="Fetching repository information")

    metadata = github_get(f"/repos/{owner}/{repo}")

    if metadata.get("private"):
        raise ValueError("Only public repositories are supported.")

    branch = metadata.get("default_branch", "main")

    progress(0.25, desc="Discovering repository files")

    tree_data = github_get(
        f"/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"}
    )

    entries = tree_data.get("tree", [])

    if tree_data.get("truncated"):
        progress(0.35, desc="Repository is large; using available file listing")

    all_files = [
        item["path"] for item in entries
        if item.get("type") == "blob"
        and not any(
            part in SKIP_DIRS
            for part in item["path"].split("/")[:-1]
        )
    ]

    if not all_files:
        raise ValueError("No repository files were found.")

    selected = all_files[:MAX_FILES]
    counts = Counter()
    for path in all_files:
        name = path.rsplit("/", 1)[-1]
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if ext in LANGUAGES:
            counts[LANGUAGES[ext]] += 1

    progress(0.4, desc="Reading README and source files")

    readme_path = next(
        (p for p in all_files if p.lower() in ("readme.md", "readme")),
        None
    )
    readme = (
        fetch_file(owner, repo, branch, readme_path)
        if readme_path else ""
    )

    source_files = {}

    for i, path in enumerate(selected):
        name = path.rsplit("/", 1)[-1]
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""

        if ext not in CODE_EXTENSIONS and name not in {
            "Dockerfile", "Makefile", "requirements.txt"
        }:
            continue

        try:
            content = fetch_file(owner, repo, branch, path)
            if content:
                source_files[path] = content
        except requests.RequestException:
            continue

        progress(
            0.4 + 0.5 * (i + 1) / len(selected),
            desc=f"Reading files ({i + 1}/{len(selected)})"
        )

    if not source_files and not readme:
        raise ValueError("Unable to read source files or README.")

    purpose = metadata.get("description") or "No repository description provided."

    if not metadata.get("description") and readme:
        for line in readme.splitlines():
            line = line.strip().lstrip("#").strip()
            if len(line) > 30 and not line.startswith("http"):
                purpose = line[:500]
                break

    tree_lines = []
    for path in all_files[:150]:
        depth = path.count("/")
        tree_lines.append("  " * depth + "├── " + path.split("/")[-1])

    if len(all_files) > 150:
        tree_lines.append(f"... {len(all_files) - 150} more files")

    important_names = {
        "app.py", "main.py", "server.py", "index.js", "index.ts",
        "manage.py", "routes.py", "models.py", "auth.py",
        "requirements.txt", "package.json", "dockerfile"
    }

    modules = [
        p for p in all_files
        if p.rsplit("/", 1)[-1].lower() in important_names
    ][:20]

    overview = f"""# {metadata.get('full_name', repo)}

{metadata.get('description') or 'Repository overview'}

**Default branch:** `{branch}`  
**Stars:** {metadata.get('stargazers_count', 0)}  
**Files discovered:** {len(all_files)}  
**Files loaded:** {len(source_files)}

## Project purpose

{purpose}

## Technologies detected

""" + (
        "\n".join(
            f"- **{language}** — {count} file(s)"
            for language, count in counts.most_common(12)
        ) or "- No supported programming languages detected."
    )

    overview += "\n\n## Main modules\n\n"
    overview += (
        "\n".join(f"- `{p}`" for p in modules)
        if modules else "Inspect the file tree to identify main modules."
    )

    overview += "\n\n## File structure\n\n```text\n"
    overview += "\n".join(tree_lines)
    overview += "\n```\n"

    overview += """
## Execution flow

This is a preliminary overview. The actual execution flow requires tracing
entry points, imports and function calls. Use the source explorer to inspect
the loaded files.
"""

    if readme:
        overview += "\n## README preview\n\n" + readme[:4000]

    data = {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "files": source_files,
        "metadata": metadata
    }

    progress(1, desc="Repository analysis completed")

    status = (
        f"### Analysis successful\n"
        f"Loaded **{len(source_files)} source/configuration files**. "
        f"[Open GitHub repository]({metadata['html_url']})"
    )

    details = {
        "repository": metadata.get("full_name"),
        "description": metadata.get("description"),
        "default_branch": branch,
        "stars": metadata.get("stargazers_count"),
        "languages_detected": dict(counts),
        "total_files": len(all_files),
        "loaded_files": len(source_files)
    }

    return (
        overview, data, status,
        gr.update(choices=list(source_files), value=None),
        details,
        "Repository ready. Ask a question about its code.",
        ""
    )


def ask_question(question, data):
    if not data:
        return "Analyze a repository first.", ""

    if not (question or "").strip():
        return "Enter a question first.", ""

    files = data["files"]
    terms = set(
        re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,}", question.lower())
    )

    ranked = []

    for path, content in files.items():
        path_lower = path.lower()
        content_lower = content.lower()

        score = sum(4 for t in terms if t in path_lower)
        score += sum(
            min(content_lower.count(t), 10)
            for t in terms
        )

        if score:
            ranked.append((score, path, content))

    ranked.sort(key=lambda x: x[0], reverse=True)
    ranked = ranked[:3]

    if not ranked:
        return (
            "No strong keyword matches were found in the loaded files. "
            "Try a function name, filename, or technology.",
            ""
        )

    explanation = [
        "## Relevant repository evidence",
        "",
        "This prototype uses keyword-based retrieval, not an LLM. "
        "Review the evidence below to understand which files may answer "
        "your question."
    ]

    code_sections = []

    for score, path, content in ranked:
        explanation.append(f"\n### `{path}`")
        explanation.append(f"Keyword relevance score: **{score}**")

        lines = content.splitlines()
        matched = [
            i for i, line in enumerate(lines)
            if any(t in line.lower() for t in terms)
        ]

        selected_lines = set()
        for i in matched[:5]:
            selected_lines.update(
                range(max(0, i - 2), min(len(lines), i + 3))
            )

        if selected_lines:
            snippet = "\n".join(
                f"{i+1}: {lines[i]}"
                for i in sorted(selected_lines)[:35]
            )
        else:
            snippet = "\n".join(
                f"{i+1}: {line}" for i, line in enumerate(lines[:25])
            )

        code_sections.append(
            f"### `{path}`\n\n```text\n{snippet}\n```"
        )

    return "\n".join(explanation), "\n\n".join(code_sections)


def show_source(path, data):
    if not data or not path:
        return "# Analyze a repository and select a source file."

    return data["files"].get(path, "File content is unavailable.")


CSS = """
.gradio-container {max-width: 1250px !important; margin: auto !important;}
#hero {
    padding: 24px; border-radius: 16px; color: white;
    background: linear-gradient(120deg, #172554, #1e3a5f, #164e63);
    margin-bottom: 16px;
}
#hero h1 {color: white;}
"""

with gr.Blocks(
    theme=gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate"
    ),
    css=CSS,
    title="Codewalk Navigator"
) as demo:

    gr.HTML("""
    <div id="hero">
        <h1>⌘ Codewalk Navigator</h1>
        <p>Understand your codebase without manually reading every file.</p>
        <p>Repository intelligence · Source exploration · Code search</p>
    </div>
    """)

    state = gr.State(None)

    with gr.Row():
        url_input = gr.Textbox(
            label="Public GitHub repository URL",
            placeholder="https://github.com/owner/repository",
            scale=5
        )
        analyze_btn = gr.Button(
            "Analyze Repository",
            variant="primary",
            scale=1
        )

    status = gr.Markdown(
        "Paste a public repository URL and click Analyze Repository."
    )

    with gr.Tabs():
        with gr.Tab("Repository Overview"):
            overview = gr.Markdown("Your repository overview will appear here.")

        with gr.Tab("Ask Codewalk"):
            gr.Markdown(
                "Ask about functions, files, dependencies or application flow."
            )

            question = gr.Textbox(
                label="Your question",
                placeholder="How does this project work?",
                lines=2
            )

            ask_btn = gr.Button("Find Relevant Code", variant="primary")
            answer = gr.Markdown()
            snippets = gr.Markdown()

        with gr.Tab("Source Explorer"):
            file_choice = gr.Dropdown(
                label="Select source file",
                choices=[],
                interactive=True
            )
            source = gr.Code(label="Source code", lines=24)

        with gr.Tab("Repository Details"):
            details = gr.JSON(label="Repository metadata")

    def run_analysis(url):
        try:
            return analyze_repository(url)
        except Exception as exc:
            message = f"## Analysis failed\n\n{type(exc).__name__}: {exc}"
            return (
                message, None, f"**Error:** {exc}",
                gr.update(choices=[], value=None), {},
                "Analysis failed. Correct the URL or try again.", ""
            )

    analyze_btn.click(
        run_analysis,
        inputs=[url_input],
        outputs=[
            overview, state, status, file_choice, details, answer, snippets
        ]
    )

    ask_btn.click(
        ask_question,
        inputs=[question, state],
        outputs=[answer, snippets]
    )

    question.submit(
        ask_question,
        inputs=[question, state],
        outputs=[answer, snippets]
    )

    file_choice.change(
        show_source,
        inputs=[file_choice, state],
        outputs=[source]
    )

demo.queue().launch(share=True, debug=False)
