"""根级物理条目集合;嵌套description不能成为Feed身份。"""

from xml.etree import ElementTree as ET

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
ATOM = "http://www.w3.org/2005/Atom"


def physical_feed_items(root: ET.Element) -> tuple[ET.Element, ...]:
    name = root.tag.rsplit("}", 1)[-1]
    if name == "rss":
        channels = [
            child for child in root if child.tag.rsplit("}", 1)[-1] == "channel"
        ]
        if len(channels) != 1:
            raise ValueError("feed_shape")
        return tuple(
            child for child in channels[0] if child.tag.rsplit("}", 1)[-1] == "item"
        )
    if root.tag in {"feed", "{" + ATOM + "}feed"}:
        return tuple(child for child in root if child.tag.rsplit("}", 1)[-1] == "entry")
    if root.tag == "{" + RDF + "}RDF":
        return tuple(child for child in root if child.tag.rsplit("}", 1)[-1] == "item")
    raise ValueError("feed_shape")
