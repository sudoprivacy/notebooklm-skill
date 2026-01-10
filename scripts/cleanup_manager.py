#!/usr/bin/env python3
"""
Cleanup Manager for NotebookLM Skill
Cleans up browser state and authentication data
"""

import shutil
import argparse
from pathlib import Path


def get_data_dir() -> Path:
    """Get the data directory path"""
    return Path(__file__).parent.parent / "data"


def format_size(size: int) -> str:
    """Format size in human-readable form"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_dir_size(path: Path) -> int:
    """Get total size of a directory"""
    total = 0
    try:
        for item in path.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
    except Exception:
        pass
    return total


def preview_cleanup():
    """Show what will be cleaned up"""
    data_dir = get_data_dir()

    print("\n🔍 Cleanup Preview")
    print("=" * 50)

    total_size = 0
    items = []

    # Browser state
    browser_state = data_dir / "browser_state"
    if browser_state.exists():
        size = get_dir_size(browser_state)
        total_size += size
        items.append(("📂 browser_state/", size, "Browser profile, cookies, cache"))

    # Auth info
    auth_file = data_dir / "auth_info.json"
    if auth_file.exists():
        size = auth_file.stat().st_size
        total_size += size
        items.append(("📄 auth_info.json", size, "Authentication status"))

    # Config (last notebook)
    config_file = data_dir / "config.json"
    if config_file.exists():
        size = config_file.stat().st_size
        total_size += size
        items.append(("📄 config.json", size, "Last used notebook"))

    if items:
        for name, size, desc in items:
            print(f"  {name:<25} {format_size(size):>10}  ({desc})")
        print("=" * 50)
        print(f"  Total: {format_size(total_size)}")
    else:
        print("  Nothing to clean up!")

    return items, total_size


def perform_cleanup():
    """Actually delete the files"""
    data_dir = get_data_dir()
    deleted = []

    # Delete browser_state directory
    browser_state = data_dir / "browser_state"
    if browser_state.exists():
        shutil.rmtree(browser_state)
        deleted.append("browser_state/")
        print("  ✅ Deleted browser_state/")

    # Delete auth_info.json
    auth_file = data_dir / "auth_info.json"
    if auth_file.exists():
        auth_file.unlink()
        deleted.append("auth_info.json")
        print("  ✅ Deleted auth_info.json")

    # Delete config.json
    config_file = data_dir / "config.json"
    if config_file.exists():
        config_file.unlink()
        deleted.append("config.json")
        print("  ✅ Deleted config.json")

    # Recreate browser_state dir
    browser_state.mkdir(parents=True, exist_ok=True)

    return deleted


def main():
    parser = argparse.ArgumentParser(
        description='Clean up NotebookLM skill data (browser state, auth)',
        epilog="""
Examples:
  python cleanup_manager.py           # Preview what will be deleted
  python cleanup_manager.py --confirm # Actually delete
        """
    )
    parser.add_argument('--confirm', action='store_true', help='Actually perform cleanup')
    args = parser.parse_args()

    items, total_size = preview_cleanup()

    if not items:
        return

    if args.confirm:
        print("\n🗑️  Performing cleanup...")
        deleted = perform_cleanup()
        print(f"\n✅ Cleanup complete! Deleted {len(deleted)} items.")
        print("\n💡 Run 'python auth_manager.py setup' to re-authenticate")
    else:
        print("\n💡 Use --confirm to actually delete these files")


if __name__ == "__main__":
    main()
