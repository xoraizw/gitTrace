import os
import shutil
import subprocess
import tempfile
import json
import urllib.request
import urllib.error
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

def get_repo_size(repo_url):
    """Get the size of a GitHub repository in MB using GitHub API."""
    # Extract owner and repo name from URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 5 or parts[2] != 'github.com':
        return None, "Invalid GitHub URL format"
    
    owner = parts[3]
    repo = parts[4].split('.')[0]  # Remove .git extension if present
    
    # Handle tree or blob paths
    if '/tree/' in repo or '/blob/' in repo:
        repo = repo.split('/')[0]
    
    # Use GitHub API to get repo information
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        # Using urllib from standard library instead of requests
        headers = {'User-Agent': 'Repository-Size-Checker/1.0'}
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            # Size is returned in KB, convert to MB
            size_mb = data.get('size', 0) / 1024
            return size_mb, None
    except urllib.error.HTTPError as e:
        return None, f"GitHub API error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return None, f"Connection error: {e.reason}"
    except Exception as e:
        return None, f"Error fetching repository size: {str(e)}"

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
    # Check repository size before cloning
    repo_size, size_error = get_repo_size(repo_url)
    
    if size_error:
        return None, size_error
    
    # Check if repository is too large (over 100MB)
    if repo_size > 100:
        return None, f"Repository size ({repo_size:.2f} MB) exceeds the 100 MB limit"
    
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
            
            # Generate the output text with the repository size
            output_text = f"Repository Size: {repo_size:.2f} MB\n"
            output_text += f"Lines: {total_lines}\nCharacters: {total_chars}\n\n"
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
            response = jsonify({'error': 'Missing repo_url parameter'})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400
        repo_url = data['repo_url']
    else:
        # Get URL from query parameter
        repo_url = request.args.get('repo_url')
        if not repo_url:
            response = jsonify({'error': 'Missing repo_url parameter'})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400

    # Validate the URL (basic check)
    if not repo_url.startswith('https://github.com/'):
        response = jsonify({'error': 'Invalid GitHub URL'})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 400

    # First check the repository size
    repo_size, size_error = get_repo_size(repo_url)
    
    if size_error:
        response = jsonify({'error': size_error})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 400
    
    # Check if repository is too large
    if repo_size > 100:
        response = jsonify({
            'error': f"Repository size ({repo_size:.2f} MB) exceeds the 100 MB limit",
            'repo_size': repo_size
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 413  # 413 Payload Too Large

    # Generate the repository analysis
    output_text, error = generate_repo_analysis(repo_url)

    if error:
        response = jsonify({'error': f'Error analyzing repository: {error}'})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

    # Determine if the client wants a download or JSON response
    download = request.args.get('download', 'false').lower() == 'true'

    if download:
        # Return as a downloadable file
        repo_name = extract_repo_name_from_url(repo_url)
        response = Response(
            output_text,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename={repo_name}_analysis.txt'}
        )
    else:
        # Return JSON response with the text content and repo size
        response = jsonify({
            'content': output_text,
            'repo_size': repo_size
        })

    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
