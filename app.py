import os
import shutil
import subprocess
import tempfile
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

def clone_repo(repo_url, clone_dir):
    """Clone the GitHub repository into the specified directory."""
    repo_url = repo_url.split("/tree/")[0]  # Ensure the URL does not contain '/tree/main'
    subprocess.run(["git", "clone", repo_url, clone_dir], check=True)

def extract_repo_name_from_url(repo_url):
    """Extract the repository name from the GitHub URL, handling '/tree/main' and similar cases."""
    repo_url = repo_url.split("/tree/")[0]  # Remove anything after '/tree/'
    repo_url = repo_url.split("/blob/")[0]  # Also handle '/blob/main' if needed
    repo_name = repo_url.rstrip("/").split("/")[-1]
    return repo_name.split(".")[0] if "." in repo_name else repo_name

def get_directory_structure(root_dir):
    """Get the directory structure in a tree format, ignoring .git directory."""
    lines = []
    for root, dirs, files in os.walk(root_dir):
        if ".git" in dirs:
            dirs.remove(".git")  # Avoid walking into .git directory

        level = root.replace(root_dir, "").count(os.sep)
        indent = " " * 4 * level
        lines.append(f"{indent}├── {os.path.basename(root)}/")

        subindent = " " * 4 * (level + 1)
        for file in files:
            lines.append(f"{subindent}├── {file}")
    return "\n".join(lines)

def read_file_contents(file_path):
    """Read the contents of a file, ignore if in .git directory."""
    if ".git" in file_path:
        return "[Ignored .git directory]"

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except (UnicodeDecodeError, OSError) as e:
        return f"[Error reading file: {e}]"

def extract_all_files_contents(root_dir):
    """Extract contents of all files in the directory, ignoring .git directory."""
    file_contents = {}
    for root, _, files in os.walk(root_dir):
        if ".git" in root:
            continue
        for file_name in files:
            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, root_dir)
            file_contents[relative_path] = read_file_contents(file_path)
    return file_contents

def generate_repo_analysis(repo_url):
    """Generate repository analysis and return as a string."""
    # Create a temporary directory for cloning
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            repo_name = extract_repo_name_from_url(repo_url)
            clone_dir = os.path.join(temp_dir, repo_name)
            
            # Clone the repository
            clone_repo(repo_url, clone_dir)
            
            # Get directory structure and file contents
            directory_structure = get_directory_structure(clone_dir)
            file_contents = extract_all_files_contents(clone_dir)
            
            # Count total lines and characters
            total_lines = directory_structure.count("\n") + sum(
                content.count("\n") for content in file_contents.values()
            )
            total_chars = len(directory_structure) + sum(
                len(content) for content in file_contents.values()
            )
            
            # Generate the output text
            output_text = f"Lines: {total_lines}\nCharacters: {total_chars}\n\n"
            output_text += "Directory Structure:\n```\n"
            output_text += directory_structure
            output_text += "\n```\n"
            
            for file_path, content in file_contents.items():
                output_text += f"\nContents of {file_path}:\n```\n"
                output_text += content
                output_text += "\n```\n"
                
            return output_text, None
        
        except Exception as e:
            return None, str(e)

@app.route('/analyze', methods=['GET', 'POST'])
def analyze_repo():
    """Endpoint to analyze a GitHub repository from a URL."""
    if request.method == 'POST':
        # Get URL from POST request
        data = request.get_json()
        if not data or 'repo_url' not in data:
            return jsonify({'error': 'Missing repo_url parameter'}), 400
        repo_url = data['repo_url']
    else:
        # Get URL from query parameter
        repo_url = request.args.get('repo_url')
        if not repo_url:
            return jsonify({'error': 'Missing repo_url parameter'}), 400
    
    # Validate the URL (basic check)
    if not repo_url.startswith('https://github.com/'):
        return jsonify({'error': 'Invalid GitHub URL'}), 400
    
    # Generate the repository analysis
    output_text, error = generate_repo_analysis(repo_url)
    
    if error:
        return jsonify({'error': f'Error analyzing repository: {error}'}), 500
    
    # Determine if the client wants a download or JSON response
    download = request.args.get('download', 'false').lower() == 'true'
    
    if download:
        # Return as a downloadable file
        repo_name = extract_repo_name_from_url(repo_url)
        return Response(
            output_text,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename={repo_name}_analysis.txt'}
        )
    else:
        # Return JSON response with the text content
        return jsonify({'content': output_text})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
