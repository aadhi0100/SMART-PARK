_REQUIRED = {
    'reportlab': 'reportlab',
    'qrcode': 'qrcode[pil]',
    'authlib': 'authlib',
    'requests': 'requests',
    'dotenv': 'python-dotenv',
    'bcrypt': 'bcrypt',
}


def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def install_requirements() -> None:
    missing = [pkg for mod, pkg in _REQUIRED.items() if not _can_import(mod)]
    if missing:
        print("Missing packages detected. Please run:")
        print("  pip install " + " ".join(missing))
    else:
        print("All dependencies are satisfied.")
