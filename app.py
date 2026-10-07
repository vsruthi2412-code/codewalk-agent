import gradio as gr
import requests
import re

repo_data = {}


def analyze_repository(repo_url):

    global repo_data

    if not repo_url.strip():
        return (
            "❌ Please enter a GitHub repository URL.",
            "",
            "",
            "",
            "",
            ""
        )

    match = re.match(
        r"https://github\.com/([^/]+)/([^/#]+)",
        repo_url.strip()
    )

    if not match:
        return (
            "❌ Invalid GitHub repository URL.",
            "",
            "",
            "",
            "",
            ""
        )

    owner = match.group(1)
    repo = match.group(2).replace(".git", "")

    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    response = requests.get(api_url)

    if response.status_code != 200:
        return (
            "❌ Repository not found or is not public.",
            "",
            "",
            "",
            "",
            ""
        )

    data = response.json()

    contents_url = (
        f"https://api.github.com/repos/{owner}/{repo}/contents"
    )

    contents_response = requests.get(contents_url)

    if contents_response.status_code != 200:
        return (
            "❌ Unable to analyze repository.",
            "",
            "",
            "",
            "",
            ""
        )

    contents = contents_response.json()

    files = []
    folders = []

    for item in contents:

        if item["type"] == "file":
            files.append(item["name"])

        elif item["type"] == "dir":
            folders.append(item["name"])

    languages_url = (
        f"https://api.github.com/repos/{owner}/{repo}/languages"
    )

    languages_response = requests.get(languages_url)

    languages = languages_response.json()

    technologies = ", ".join(languages.keys())

    purpose = data.get("description")

    if not purpose:
        purpose = "Project purpose is not available."

    file_structure = "\n".join(
        [f"📁 {folder}/" for folder in folders] +
        [f"📄 {file}" for file in files]
    )

    main_modules = ", ".join(folders)

    execution_flow = """
Repository URL
      ↓
Repository Analysis
      ↓
File & Module Identification
      ↓
Developer Question
      ↓
Relevant Code Retrieval
      ↓
Code Explanation
"""

    repo_data = {
        "owner": owner,
        "repo": repo,
        "files": files,
        "folders": folders
    }

    return (
        "✅ Repository analyzed successfully.",
        purpose,
        file_structure,
        main_modules,
        technologies,
        execution_flow
    )


def ask_question(question):

    if not repo_data:
        return (
            "⚠️ Please analyze a repository first.",
            "",
            ""
        )

    if not question.strip():
        return (
            "⚠️ Please enter a question.",
            "",
            ""
        )

    files = repo_data["files"]

    relevant_files = []

    question_lower = question.lower()

    for file in files:

        filename = file.lower()

        if any(word in filename for word in [
            "auth",
            "login",
            "user",
            "database",
            "api",
            "route",
            "service"
        ]):

            relevant_files.append(file)

    if not relevant_files:
        relevant_files = files[:5]

    answer = f"""
### Codewalk Answer

**Question:** {question}

The Codewalk Agent analyzed the repository structure and identified the most relevant files for this question.

The next stage is to retrieve the actual source code and use an LLM to generate a detailed explanation.
"""

    relevant = "\n".join(
        [f"📄 `{file}`" for file in relevant_files]
    )

    source_code = "\n\n".join(
        [
            f"""
<details>
<summary>📄 {file}</summary>

Source code will be displayed here.

</details>
"""
            for file in relevant_files
        ]
    )

    return answer, relevant, source_code


with gr.Blocks(
    title="Codewalk Navigators"
) as demo:

    gr.Markdown(
        """
        # CODEWALK NAVIGATORS

        ### Interactive Repository Understanding Agent

        Understand the codebase. Ask questions. Trace the execution flow.
        """
    )

    with gr.Row():

        repo_url = gr.Textbox(
            label="GitHub Repository URL",
            placeholder="https://github.com/user/repository"
        )

        analyze_button = gr.Button(
            "🔍 Analyze Repository",
            variant="primary"
        )

    status = gr.Markdown()

    gr.Markdown("## Repository Overview")

    with gr.Row():

        with gr.Column():

            purpose = gr.Markdown(
                label="Project Purpose"
            )

            technologies = gr.Markdown(
                label="Technologies"
            )

            modules = gr.Markdown(
                label="Main Modules"
            )

        with gr.Column():

            execution = gr.Markdown(
                label="Execution Flow"
            )

    gr.Markdown("### File Structure")

    file_structure = gr.Code(
    label="Repository Files"
    )

    gr.Markdown("---")

    gr.Markdown("## Ask About the Repository")

    question = gr.Textbox(
        label="Developer Question",
        placeholder="Example: How does authentication work?"
    )

    ask_button = gr.Button(
        "💬 Ask Question",
        variant="primary"
    )

    answer = gr.Markdown()

    gr.Markdown("### Relevant Files")

    relevant_files = gr.Markdown()

    gr.Markdown("### Relevant Source Code")

    source_code = gr.Markdown()

    analyze_button.click(
        fn=analyze_repository,
        inputs=repo_url,
        outputs=[
            status,
            purpose,
            file_structure,
            modules,
            technologies,
            execution
        ]
    )

    ask_button.click(
        fn=ask_question,
        inputs=question,
        outputs=[
            answer,
            relevant_files,
            source_code
        ]
    )


demo.launch()
