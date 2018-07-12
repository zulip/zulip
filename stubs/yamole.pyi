from typing import Any, TextIO

class YamoleParser:
  data: Any  # A blob of data parsed from YAML.

  def __init__(self, file: TextIO) -> None:
      ...
