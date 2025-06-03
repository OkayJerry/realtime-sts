import pprint
import datetime
from enum import Enum, auto


class LogLevel(Enum):
    """Defines the supported log levels."""
    CRITICAL = auto()
    WARNING = auto()
    INFO = auto()

class TerminalColors:
    """A class to hold ANSI escape codes for terminal colors."""
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    ORANGE = '\033[34m'
    PURPLE = '\033[35m'
    BLUE = '\033[36m'
    ENDC = '\033[0m'  # Resets the color

def log(level: LogLevel, message: str):
    """
    Logs a message with a specified level and color.

    Args:
        level (LogLevel): The log level, must be a member of the LogLevel enum.
        message (any): The message to log. Can be a string, dict, list, etc.
    """
    if not isinstance(level, LogLevel):
        # You could also raise a TypeError for stricter checking
        print(f"{TerminalColors.ORANGE}[WARNING]{TerminalColors.ENDC} Invalid log level provided. Must be a LogLevel enum member.")
        return

    if level == LogLevel.CRITICAL:
        color = TerminalColors.RED
    elif level == LogLevel.WARNING:
        color = TerminalColors.ORANGE
    else:
        color = TerminalColors.BLUE

    # Format the message using pprint for readability
    formatted_message = pprint.pformat(message, indent=2)

    header = f'{color}{level.name}{TerminalColors.ENDC}: '
    print(f"{header}{formatted_message:>10}")

if __name__ == "__main__":
    log(LogLevel.INFO, "test")