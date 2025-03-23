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
    for root, dirs, files in os.walk(root_dir):
        if ".git" in dirs:
            dirs.remove(".git")  # Exclude the .git directory
        level = root.replace(root_dir, "").count(os.sep)
        indent = " " * 4 * level
        lines.append(f"{indent}├── {os.path.basename(root)}/")
        subindent = " " * 4 * (level + 1)
        for file in files:
            lines.append(f"{subindent}├── {file}")
    return "\n".join(lines)

def save_to_file(repo_name, content):
    """Save repository details to a text file."""
    file_path = f"{repo_name}_details.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
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
        
        # Get directory structure
        directory_structure = get_directory_structure(clone_dir)
        
        # Save details to a file
        file_path = save_to_file(repo_name, directory_structure)

        # Send the file as a response
        return send_file(file_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cleanup(clone_dir, file_path)  # Ensure cleanup after request is processed

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
