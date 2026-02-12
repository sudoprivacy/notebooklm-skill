#!/usr/bin/env python3
"""
Setup script for NotebookLM skill environment
Creates virtual environment and installs dependencies
"""

import os
import sys
import subprocess
from pathlib import Path


def main():
    """Set up the virtual environment"""
    skill_dir = Path(__file__).parent.parent
    venv_dir = skill_dir / ".venv"
    requirements_file = skill_dir / "requirements.txt"

    try:
        # Create virtual environment
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        # Get pip executable
        if os.name == 'nt':  # Windows
            pip_executable = venv_dir / "Scripts" / "pip"
            python_executable = venv_dir / "Scripts" / "python"
        else:  # Unix/Linux/Mac
            pip_executable = venv_dir / "bin" / "pip"
            python_executable = venv_dir / "bin" / "python"

        # Upgrade pip
        print("⬆️  Upgrading pip...")
        subprocess.run([str(python_executable), "-m", "pip", "install", "--upgrade", "pip"], check=True)

        # Install requirements
        print("📥 Installing dependencies...")
        subprocess.run([str(pip_executable), "install", "-r", str(requirements_file)], check=True)

        # Install patchright browser
        print("🌐 Installing browser...")
        subprocess.run([str(python_executable), "-m", "patchright", "install", "chromium"], check=True)

        print("✅ Setup complete!")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"❌ Setup failed: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
