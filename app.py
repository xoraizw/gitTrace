from flask import Flask, request, jsonify, send_file
import os
import shutil
import subprocess

app = Flask(__name__)

def clone_repo(repo_url, clone_dir):
    """Clone the GitHub repository into the specified directory."""
    repo_url = repo_url.split("/tree/")[0]  # Remove any tree/blob paths
    subprocess.run(["git", "clone", repo_url, clone_dir], check=True)

def extract_repo_name_from_url(repo_url):
    """Extract the repository name from the GitHub URL."""
    repo_url = repo_url.split("/tree/")[0]
    repo_url = repo_url.split("/blob/")[0]
    repo_name = repo_url.rstrip("/").split("/")[-1]
    return repo_name.split(".")[0] if "." in repo_name else repo_name

def get_directory_structure(root_dir):
    """Get the directory structure."""
    lines = []
    file_count = 0
    for root, dirs, files in os.walk(root_dir):
        if ".git" in dirs:
            dirs.remove(".git")  # Exclude .git directory
        
        level = root.replace(root_dir, "").count(os.sep)
        indent = " " * 4 * level
        lines.append(f"{indent}├── {os.path.basename(root)}/")

        subindent = " " * 4 * (level + 1)
        for file in files:
            file_count += 1
            lines.append(f"{subindent}├── {file}")

    return "\n".join(lines), file_count

def read_file_contents(file_path):
    """Read the contents of a file while handling errors."""
    if ".git" in file_path:
        return "[Ignored .git directory]"
    
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except (UnicodeDecodeError, OSError):
        return "[Error reading file]"

def extract_all_files_contents(root_dir):
    """Extract contents of all files in the directory."""
    file_contents = {}
    total_lines = 0
    total_chars = 0

    for root, _, files in os.walk(root_dir):
        if ".git" in root:
            continue
        for file_name in files:
            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, root_dir)
            content = read_file_contents(file_path)

            total_lines += content.count("\n")
            total_chars += len(content)

            file_contents[relative_path] = content

    return file_contents, total_lines, total_chars

def save_to_file(repo_name, directory_structure, file_contents, total_files, total_lines, total_chars):
    """Save repository details to a text file."""
    file_path = f"{repo_name}_details.txt"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"Total Files: {total_files}\n")
        f.write(f"Total Lines: {total_lines}\n")
        f.write(f"Total Characters: {total_chars}\n\n")
        f.write("Directory Structure:\n")
        f.write(directory_structure)
        f.write("\n\nFile Contents:\n")

        for file_path, content in file_contents.items():
            f.write(f"\nContents of {file_path}:\n")
            f.write("```\n")
            f.write(content)
            f.write("\n```\n")

    return file_path

def cleanup(clone_dir, file_path):
    """Remove the cloned repository directory and the generated file."""
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)
    if os.path.exists(file_path):
        os.remove(file_path)

@app.route("/extract", methods=["POST"])
def analyze_repo():
    data = request.get_json()
    repo_url = data.get("repo_url")

    if not repo_url:
        return jsonify({"error": "Repository URL is required"}), 400

    repo_name = extract_repo_name_from_url(repo_url)
    clone_dir = repo_name

    try:
        # Clone the repository
        clone_repo(repo_url, clone_dir)
        
        # Get directory structure and file count
        directory_structure, total_files = get_directory_structure(clone_dir)
        
        # Extract all file contents and count lines/characters
        file_contents, total_lines, total_chars = extract_all_files_contents(clone_dir)

        # Save details to a file
        file_path = save_to_file(repo_name, directory_structure, file_contents, total_files, total_lines, total_chars)

        # Send the file as a response
        return send_file(file_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cleanup(clone_dir, file_path)  # Ensure cleanup after request is processed

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
