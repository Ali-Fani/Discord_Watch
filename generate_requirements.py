import sys
import toml
from pathlib import Path

def parse_pyproject(pyproject_path):
    """Parse pyproject.toml and extract dependencies."""
    with open(pyproject_path, 'r') as f:
        pyproject = toml.load(f)
    
    dependencies = {}
    project_deps = pyproject.get('project', {}).get('dependencies', [])
    
    for dep in project_deps:
        # Extract package name and version from dependency string
        # Format: "package>=version"
        package, version_spec = dep.split('>=')
        dependencies[package] = version_spec
    
    return dependencies

def parse_uv_lock(lock_path):
    """Parse uv.lock and extract exact package versions."""
    with open(lock_path, 'r') as f:
        content = f.read()
        # Parse TOML content
        lock_data = toml.loads(content)
    
    packages = {}
    # Extract packages from the lock file
    for package in lock_data.get('package', []):
        name = package.get('name')
        version = package.get('version')
        if name and version:
            packages[name] = version
    
    return packages

def generate_requirements(pyproject_path, lock_path, output_path):
    """Generate requirements.txt by combining pyproject.toml and uv.lock information."""
    # Get dependencies from pyproject.toml
    project_deps = parse_pyproject(pyproject_path)
    
    # Get exact versions from uv.lock
    locked_versions = parse_uv_lock(lock_path)
    
    # Combine information and write to requirements.txt
    with open(output_path, 'w') as f:
        for package, _ in project_deps.items():
            if package in locked_versions:
                f.write(f"{package}=={locked_versions[package]}\n")
            else:
                print(f"Warning: Package {package} not found in uv.lock")

def main():
    workspace_path = Path(__file__).parent
    pyproject_path = workspace_path / "pyproject.toml"
    lock_path = workspace_path / "uv.lock"
    output_path = workspace_path / "requirements.txt"
    
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        sys.exit(1)
    
    if not lock_path.exists():
        print("Error: uv.lock not found")
        sys.exit(1)
    
    generate_requirements(pyproject_path, lock_path, output_path)
    print("Generated requirements.txt successfully")

if __name__ == "__main__":
    main()
