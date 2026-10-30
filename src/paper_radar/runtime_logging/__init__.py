"""显式注入的诊断事件;不接入任何 Python logger。"""

from paper_radar.runtime_logging.events import NullSink, RuntimeLog, Sink
from paper_radar.runtime_logging.files import FileSink

__all__ = ["FileSink", "NullSink", "RuntimeLog", "Sink"]
